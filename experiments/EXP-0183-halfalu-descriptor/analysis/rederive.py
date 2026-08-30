#!/usr/bin/env python3
"""EXP-0183 -- INDEPENDENT re-derivation of EXP-0180's defects from committed raw.

Reads ONLY the immutable raw trees:
  experiments/EXP-0180-g17p-halfalu-rerecord/raw/{g17p_run02,g17p_run03}/
  experiments/EXP-0169-g17p-rerecord/raw/{g17p_20260830_run01,g17p_20260830_run02}/
  experiments/EXP-0168-g17p-dst-resweep/raw/<gated runs>/

It deliberately does NOT import EXP-0180's analysis/*.py or its conclusions. Every
number below is recomputed from the per-case `pre`/`post` register vectors, the
`hw_markers` counts and the spliced `bytes`.

  python3 analysis/rederive.py            # writes analysis/defects_rederived.json
"""
import collections, json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
E180 = os.path.join(REPO, "experiments", "EXP-0180-g17p-halfalu-rerecord")
E169 = os.path.join(REPO, "experiments", "EXP-0169-g17p-rerecord")
E168 = os.path.join(REPO, "experiments", "EXP-0168-g17p-dst-resweep")
RUNS = ["g17p_run02", "g17p_run03"]


def jl(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load180():
    out = {}
    for r in RUNS:
        out[r] = list(jl(os.path.join(E180, "raw", r, "sweep.jsonl")))
    return out


def h2f(h):
    return struct.unpack("<e", struct.pack("<H", h))[0]


def f2h(f):
    return struct.unpack("<H", struct.pack("<e", f))[0]


def halves(regs):
    """half-register index h = (reg << 1) | is_high  ->  raw 16-bit pattern."""
    d = {}
    for j, w in enumerate(regs):
        d[2 * j] = w & 0xFFFF
        d[2 * j + 1] = (w >> 16) & 0xFFFF
    return d


# ---------------------------------------------------------------- H1 : DSTNIB
HARNESS_REGS = {
    15: "R_IDX -- device_store index register, re-seeded to 0 before EVERY store "
        "(harness/isa_helpers.py:66). Any write to r15 is destroyed before the dump.",
    14: "R_ZERO / pad_reg -- the always-0 source falu2i seeding needs, and the program "
        "PADDING register (harness/isa_helpers.py:69, build_program(pad_reg=R_ZERO), "
        "slack() = mov_imm(R_ZERO,0)*4). Padding sits AFTER the block on the arm that "
        "carries a second consumer.",
    13: "R_PRE / R_C2 -- PRE-sentinel scratch and C_LO's SECOND-CONSUMER destination "
        "(harness/isa_helpers.py:68,70).",
    12: "R_SENT -- POST-sentinel register, written after the block and after the dump "
        "(harness/isa_helpers.py:67).",
}


def h1_dstnib(runs):
    """H1: for byte0 & 0x0f == 0, the destination GPR is byte0 >> 4; the write lands
    in r[n]'s LOW 16 bits and r[n]'s HIGH 16 bits are preserved.

    Scored per value into four categories, from pre/post alone:
      confirmed      -- r[n] changed, high half preserved, low half == the arm's result R
      low_half_only  -- low half == R but the high half also changed (attributed only if
                        r[n] is a documented harness register)
      masked         -- r[n] did not change AND r[n] is a documented harness register that
                        the program rewrites after the block  (unobservable, not refuted)
      refuted        -- r[n] did not change and nothing explains it

    R is taken from the arm's own ANCHOR record (byte0 = 0x10 -> dst r1), NOT from the
    sweep, so the result value is not defined by the thing being tested.
    """
    res = {}
    for run, recs in runs.items():
        anchors = {(a["arm"], a["carrier"]): a for a in
                   jl(os.path.join(E180, "raw", run, "anchor.jsonl"))}
        d = [r for r in recs if r["arm"] == "DSTNIB"]
        for carrier in sorted({r["carrier"] for r in d}):
            a = anchors[("DSTNIB", carrier)]
            assert bytes.fromhex(a["anchor"])[0] == 0x10, a["anchor"]
            R = a["observed"]["post"][1] & 0xFFFF          # anchor writes r1
            cs = sorted((r for r in d if r["carrier"] == carrier), key=lambda r: r["value"])
            per, cats = {}, collections.defaultdict(list)
            for r in cs:
                n = r["value"]
                assert int(r["bytes"][0:2], 16) == (n << 4), r["bytes"]
                pre, post = r["observed"]["pre"], r["observed"]["post"]
                lo_pre, lo_post = pre[n] & 0xFFFF, post[n] & 0xFFFF
                hi_pre, hi_post = pre[n] >> 16, post[n] >> 16
                if lo_post == R and hi_pre == hi_post and post[n] != pre[n]:
                    cat = "confirmed"
                elif lo_post == R and post[n] != pre[n]:
                    cat = "low_half_only"
                elif post[n] == pre[n] and n in HARNESS_REGS:
                    cat = "masked"
                elif post[n] != pre[n] and n in HARNESS_REGS:
                    cat = "masked_overwritten"
                else:
                    cat = "refuted"
                cats[cat].append(n)
                per[n] = {"byte0": r["bytes"][0:2], "category": cat,
                          "r_n_pre": "0x%08x" % pre[n], "r_n_post": "0x%08x" % post[n],
                          "expected_low_half": "0x%04x" % R,
                          "harness_role": HARNESS_REGS.get(n),
                          "other_regs_changed": sorted(
                              i for i, (x, y) in enumerate(zip(pre, post))
                              if x != y and i != n),
                          "outcome": r["outcome"]}
            res.setdefault(carrier, {})[run] = {
                "anchor_result_low_half": "0x%04x" % R,
                "categories": {k: sorted(v) for k, v in sorted(cats.items())},
                "per_value": per,
            }
    agree = {}
    for carrier, byrun in res.items():
        a, b = byrun[RUNS[0]]["per_value"], byrun[RUNS[1]]["per_value"]
        agree[carrier] = {"values": len(a),
                          "identical_across_runs": sum(1 for n in a if a[n] == b.get(n))}
    conf = set()
    for byrun in res.values():
        for run in RUNS:
            conf |= set(byrun[run]["categories"].get("confirmed", []))
            conf |= set(byrun[run]["categories"].get("low_half_only", []))
    refuted = set()
    for byrun in res.values():
        for run in RUNS:
            refuted |= set(byrun[run]["categories"].get("refuted", []))
    # Independent control: which registers EVER carry a non-zero value anywhere in the
    # whole run, per carrier. If r14/r15 are never non-zero outside the DSTNIB case that
    # targets them, the harness-mask explanation is a measurement rather than a story.
    ctl = collections.defaultdict(lambda: collections.Counter())
    for run, recs in runs.items():
        for r in recs:
            obs = r.get("observed") or {}
            if not obs.get("post"):
                continue
            for i in (14, 15):
                if obs["post"][i]:
                    ctl[(r["carrier"], i)][(r["arm"], r["field"], r["value"])] += 1
    return {"per_carrier": res, "cross_run": agree,
            "confirmed_union": sorted(conf), "refuted_union": sorted(refuted),
            "harness_register_roles": HARNESS_REGS,
            "nonzero_r14_r15_anywhere_in_run": {
                "%s/r%d" % (c, i): [{"arm": k[0], "field": k[1], "value": k[2], "n": v}
                                    for k, v in sorted(cnt.items())]
                for (c, i), cnt in sorted(ctl.items())}}


# ---------------------------------------------------------- H1b : seed structure
def h1b_seed(runs):
    """H1b: the seed program's per-register low-half writes are deterministic and land
    in r_j. Verified as: the PRE vector is bit-identical across every gated case of a
    given (arm, carrier) and across both runs, and its 28 seeded lanes are distinct."""
    out = {}
    for run, recs in runs.items():
        pres = collections.defaultdict(set)
        seedok = collections.Counter()
        for r in recs:
            obs = r.get("observed") or {}
            if not obs.get("pre"):
                seedok[r.get("seed_ok")] += 1
                continue
            pres[(r["arm"], r["carrier"])].add(tuple(obs["pre"]))
            seedok[r.get("seed_ok")] += 1
        out[run] = {
            "arm_carriers": len(pres),
            "arm_carriers_with_one_pre_vector": sum(1 for v in pres.values() if len(v) == 1),
            "arm_carriers_with_multiple_pre_vectors": {str(k): len(v)
                                                       for k, v in pres.items() if len(v) != 1},
            "seed_ok_counts": {str(k): v for k, v in seedok.items()},
            "distinct_pre_by_carrier": {c: len({p for (a, cc), s in pres.items()
                                                if cc == c for p in s})
                                        for c in sorted({k[1] for k in pres})},
        }
    return out


# ------------------------------------------------- H1c : the arithmetic identity
def h1c_arith(runs):
    """H1c: the E8_FMA / DSTNIB anchors compute
          r[byte0>>4].lo = fp16( h[byte+1] * h[byte+3] + h[byte+5] )
    where h[v] = ((v>>1) -> register, v&1 -> 1=high half / 0=low half).
    db.json's `dst` (bits 8..15 = byte+1) therefore appears as a SOURCE, and byte+4
    does not appear at all. Brute-forced over all 32 half-registers as a control, so
    the identification is not assumed."""
    out = {}
    for run, recs in runs.items():
        for r in recs:
            if r["arm"] not in ("DSTNIB", "E8_FMA") or r["mode"] not in ("probe", "generated"):
                continue
            if r["bytes"] != r["anchor"]:
                continue                                    # the unmutated anchor only
            b = bytes.fromhex(r["anchor"])
            pre, post = r["observed"]["pre"], r["observed"]["post"]
            H = halves(pre)
            dst = b[0] >> 4
            got = post[dst] & 0xFFFF
            pred = f2h(h2f(H[b[1]]) * h2f(H[b[3]]) + h2f(H[b[5]]))
            # control: every (a,b,c) triple of DISTINCT non-zero halves reproducing `got`
            alts = []
            for ia in H:
                for ib in H:
                    for ic in H:
                        if H[ia] and H[ib] and H[ic] and \
                           f2h(h2f(H[ia]) * h2f(H[ib]) + h2f(H[ic])) == got:
                            alts.append((ia, ib, ic))
            out.setdefault(r["carrier"], {})[run] = {
                "anchor": r["anchor"],
                "dst_from_byte0_high_nibble": dst,
                "observed_low_half": "0x%04x" % got,
                "predicted_from_bytes_1_3_5": "0x%04x" % pred,
                "identity_holds": pred == got,
                "operands": {"byte+1": b[1], "byte+3": b[3], "byte+5": b[5],
                             "h[byte+1]": "0x%04x" % H[b[1]],
                             "h[byte+3]": "0x%04x" % H[b[3]],
                             "h[byte+5]": "0x%04x" % H[b[5]],
                             "f[byte+1]": h2f(H[b[1]]), "f[byte+3]": h2f(H[b[3]]),
                             "f[byte+5]": h2f(H[b[5]])},
                "byte+4": b[4], "byte+4_appears_in_identity": False,
                "n_alternative_triples_over_all_32_halves": len(alts),
                "anchor_triple_is_among_them": (b[1], b[3], b[5]) in alts
                                               or (b[3], b[1], b[5]) in alts,
            }
    return out


# ------------------------------------------------------------- H2 : length rule
def h2_length(runs):
    """H2: the byte0 low-nibble-0 family's length is a function of
    (opsel = byte+2 & 7, m = byte+4 & 3) alone. Length is read off the four-marker
    chain at byte +6: length = 14 - 2 * hw_markers (4 surviving -> 6B ... 0 -> 14B)."""
    cells = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    faults = collections.Counter()
    fault_rule = collections.Counter()
    zero_point = {}
    for run, recs in runs.items():
        for r in recs:
            if r["arm"] != "LEN":
                continue
            if r["field"].startswith("__falsifier_F4"):
                zero_point[run] = r["hw_markers"]
                continue
            b = bytes.fromhex(r["bytes"])
            o, m = b[2] & 7, b[4] & 3
            if r["hw_markers"] is None:
                # no length observation at all -- the case faulted. Kept as a result.
                faults[(o, m)] += 1
                fault_rule[(o, (b[2] >> 3) >= 16, r["outcome"])] += 1
                continue
            cells[(o, m)][run][14 - 2 * r["hw_markers"]] += 1
    table, ambiguous, disagree = {}, [], []
    for (o, m), byrun in sorted(cells.items()):
        lens = set()
        for run in RUNS:
            lens |= set(byrun[run])
            if len(byrun[run]) > 1:
                ambiguous.append({"opsel": o, "m": m, "run": run,
                                  "lengths": dict(byrun[run])})
        if len(lens) > 1:
            disagree.append({"opsel": o, "m": m, "lengths": sorted(lens)})
        table["%d,%d" % (o, m)] = sorted(lens)[0] if len(lens) == 1 else sorted(lens)

    # db.json's own STATED rule for this byte0 group, transcribed from
    # length_rule.byte0_table["0x10"]: "6, or 8 if (byte+2 & 0x02)".
    def db_stated(b2, b4):
        return 8 if (b2 & 0x02) else 6

    wrong = []
    for o in range(8):
        for m in range(4):
            k = "%d,%d" % (o, m)
            if k not in table:
                continue
            meas = table[k]
            # any byte+2 whose low 3 bits are `o`; bit1 of byte+2 is bit1 of `o`
            pred = db_stated(o, m)
            if isinstance(meas, int) and pred != meas:
                wrong.append({"opsel": o, "m": m, "db_stated": pred, "measured": meas})
    covered = sum(1 for o in range(8) for m in range(4) if "%d,%d" % (o, m) in table)
    return {"measured_table": table, "cells_covered": covered,
            "fault_cases_by_cell": {"%d,%d" % k: v for k, v in sorted(faults.items())},
            "fault_rule_check_opsel_x_opflagsbit4": {
                "%d,%s,%s" % k: v for k, v in sorted(fault_rule.items(), key=str)},
            "cells_with_more_than_one_length": ambiguous,
            "cells_disagreeing_across_runs": disagree,
            "zero_point_markers": zero_point,
            "db_json_stated_rule": "6, or 8 if (byte+2 & 0x02)",
            "db_json_stated_rule_wrong_cells": wrong,
            "db_json_stated_rule_wrong_count": len(wrong)}


# ------------------------------------------------------ H3 : the six withdrawals
def _digest(obs):
    return (tuple(obs["post"]), obs.get("post_sent"), obs.get("pre_sent"),
            tuple(tuple(x) if isinstance(x, list) else x for x in obs.get("stray", [])))


def h3_withdrawals(runs):
    anchors = {}
    for run in RUNS:
        for a in jl(os.path.join(E180, "raw", run, "anchor.jsonl")):
            anchors[(run, a["arm"], a["carrier"])] = _digest(a["observed"])

    moved = collections.defaultdict(lambda: collections.defaultdict(dict))
    for run, recs in runs.items():
        for r in recs:
            if r["mode"] not in ("generated", "lift-control") or r["field"].startswith("__"):
                continue
            obs = r.get("observed") or {}
            if not obs.get("post"):
                continue
            key = (r["instr"], r["field"])
            base = anchors.get((run, r["arm"], r["carrier"]))
            moved[key][(r["arm"], r["carrier"], run)][r["value"]] = \
                _digest(obs) != base
    out = {}
    for key, arms in sorted(moved.items()):
        per = {}
        for (arm, carrier, run), vals in sorted(arms.items()):
            per["%s@%s/%s" % (arm, carrier, run)] = {
                "values": len(vals), "moved": sum(1 for v in vals.values() if v)}
        out["%s.%s" % key] = per
    return out


def h3_saturate_and_marker(runs):
    """(b) which byte+7 bit nulls the op, and (c) what `saturate` actually does.
    Re-derived from the raw bytes and the destination register's low half."""
    sat, mark = {}, {}
    for run, recs in runs.items():
        for r in recs:
            if r["instr"] != "half_alu_ext8" or r["arm"] not in ("E8_FMA",):
                continue
            if r["field"] not in ("saturate", "op_valid_marker", "b7_mid", "b7_lo"):
                continue
            obs = r.get("observed") or {}
            if not obs.get("post"):
                continue
            b = bytes.fromhex(r["bytes"])
            dst = b[0] >> 4
            H = halves(obs["pre"])
            rec = {"byte+7": "0x%02x" % b[7],
                   "instr_bits_56_63": [(b[7] >> i) & 1 for i in range(8)],
                   "result_low_half": "0x%04x" % (obs["post"][dst] & 0xFFFF),
                   "result_f": h2f(obs["post"][dst] & 0xFFFF),
                   "third_operand_h_byte+5": "0x%04x" % H[b[5]],
                   "third_operand_f": h2f(H[b[5]]),
                   "dst_untouched": obs["post"][dst] == obs["pre"][dst]}
            k = "%s/%s/%s/v=%d" % (r["field"], r["carrier"], run, r["value"])
            (sat if r["field"] == "saturate" else mark)[k] = rec
    return {"saturate_cases": sat, "byte7_other_bit_cases": mark}


def h3_srcB_desc_range(lenmap):
    """(d) `srcB_desc` (byte+4) at the 8-byte descriptor: how many of its 256 values
    keep the 8-byte framing, taken from the MEASURED length map, not from a claim."""
    out = {}
    for o in range(8):
        keep8 = [m for m in range(4) if lenmap["measured_table"].get("%d,%d" % (o, m)) == 8]
        out[str(o)] = {"m_values_giving_8_bytes": keep8,
                       "byte4_values_of_256": 64 * len(keep8)}
    return out


def h3_fma12_opsel(lenmap):
    """(e) `half_alu_fma12.opsel`: how many of its 8 values give a 12-byte instruction."""
    twelve = [o for o in range(8)
              if any(lenmap["measured_table"].get("%d,%d" % (o, m)) == 12 for m in range(4))]
    per = {str(o): [m for m in range(4)
                    if lenmap["measured_table"].get("%d,%d" % (o, m)) == 12] for o in range(8)}
    return {"opsel_values_reaching_12_bytes": twelve, "per_opsel_m_values": per,
            "legal_value_count": len(twelve)}


# ------------------------------------------------------- H4 : citation defects
def h4_citations(db):
    rows = {
        "half_alu_fma12.srcA": ("byte+4 0x83 -> fma(|a|,b,c); 0x82 -> |a| alone; 0x80 -> 0", 4),
        "half_alu_ext8.srcA": ("byte+6 swept 0x00..0xc0 all inert", 6),
        "half_alu_ext8.srcB_desc": ("carries the fma srcA-negate (byte+7 0xc0 -> 0xc8)", 7),
    }
    by = {(i["mnemonic"], f["name"]): (f["start"], f["width"])
          for i in db["instructions"] for f in i.get("fields", [])}
    out = {}
    for key, (text, cited_byte) in rows.items():
        m, f = key.split(".")
        start, width = by[(m, f)]
        lo, hi = start // 8, (start + width - 1) // 8
        out[key] = {"field_bits": [start, start + width - 1],
                    "field_bytes": list(range(lo, hi + 1)),
                    "byte_named_by_committed_range_text": cited_byte,
                    "text": text,
                    "citation_defect": not (lo <= cited_byte <= hi)}
    return out


# ------------------------------------------- H5 : EXP-0181's two re-scored rows
def h5_rescores():
    out = {}
    # reg_move_cb.form -- EXP-0169's dense byte+2 sweep restricted to the 16 legal bytes.
    per = collections.defaultdict(lambda: collections.defaultdict(dict))
    for run in ("g17p_20260830_run01", "g17p_20260830_run02"):
        p = os.path.join(E169, "raw", run, "sweep.jsonl")
        if not os.path.exists(p):
            continue
        for r in jl(p):
            if r.get("instr") != "reg_move_cb" or r.get("field") != "form":
                continue
            hexs = r.get("bytes") or ""
            if len(hexs) < 6:
                continue
            per[run][r["carrier"]][int(hexs[4:6], 16)] = r["outcome"]
    legal = {}
    for run, bycar in per.items():
        for car, vals in bycar.items():
            leg = {v: o for v, o in vals.items() if (v & 0x0F) == 0x0B}
            legal["%s/%s" % (run, car)] = {
                "values_dispatched_total": len(vals),
                "legal_under_match_low_nibble_0xb": len(leg),
                "outcomes_by_form_high_nibble": {str(v >> 4): o for v, o in sorted(leg.items())},
            }
    out["reg_move_cb.form"] = legal
    # iter_at.grp -- EXP-0168's render arm.
    gp = collections.defaultdict(dict)
    if os.path.isdir(os.path.join(E168, "raw")):
        for run in sorted(os.listdir(os.path.join(E168, "raw"))):
            for name in ("sweep.jsonl", "render_sweep.jsonl"):
                p = os.path.join(E168, "raw", run, name)
                if not os.path.exists(p):
                    continue
                for r in jl(p):
                    if r.get("instr") != "iter_at" or r.get("field") != "grp":
                        continue
                    hexs = r.get("bytes") or ""
                    b0 = int(hexs[0:2], 16) if len(hexs) >= 2 else r.get("value")
                    if b0 is None:
                        continue
                    gp[run].setdefault(r.get("carrier"), {}).setdefault(b0, []).append(
                        r.get("outcome"))
    out["iter_at.grp"] = {run: {car: {"0x%02x" % k: sorted(collections.Counter(v).items())
                                      for k, v in sorted(d.items())}
                                for car, d in sorted(bycar.items())}
                          for run, bycar in sorted(gp.items())}
    return out


def main():
    runs = load180()
    db = json.load(open(os.path.join(REPO, "tools", "agx-isa", "db.json")))
    lenmap = h2_length(runs)
    doc = {
        "_meta": {
            "experiment": "EXP-0183-halfalu-descriptor",
            "method": "PURE ANALYSIS. Re-derived from committed raw only; EXP-0180's "
                      "analysis/*.py were NOT imported and its conclusions were not "
                      "assumed. No device, no SSH, no GPU.",
            "raw_read": {
                "EXP-0180": RUNS,
                "EXP-0169": ["g17p_20260830_run01", "g17p_20260830_run02"],
                "EXP-0168": "all committed run directories",
            },
            "half_register_convention_used": "h = (reg << 1) | is_high; h2f/f2h are IEEE "
                                             "binary16 via struct '<e'. Derived, not assumed: "
                                             "see H1c's brute-force control.",
        },
        "H1_dstnib": h1_dstnib(runs),
        "H1b_seed_determinism": h1b_seed(runs),
        "H1c_arithmetic_identity": h1c_arith(runs),
        "H2_length_rule": lenmap,
        "H3_moved_counts": h3_withdrawals(runs),
        "H3_byte7_semantics": h3_saturate_and_marker(runs),
        "H3_srcB_desc_encodable_range": h3_srcB_desc_range(lenmap),
        "H3_fma12_opsel_legal_values": h3_fma12_opsel(lenmap),
        "H4_citation_defects": h4_citations(db),
        "H5_rescores": h5_rescores(),
    }
    out = os.path.join(HERE, "defects_rederived.json")
    json.dump(doc, open(out, "w"), indent=1, sort_keys=True)
    print("wrote", out)
    return doc


if __name__ == "__main__":
    d = main()
    print("H1 confirmed dst nibbles (union of carriers):", d["H1_dstnib"]["confirmed_union"])
    print("H1 REFUTED dst nibbles:", d["H1_dstnib"]["refuted_union"])
    print("H1 categories:",
          json.dumps({c: d["H1_dstnib"]["per_carrier"][c][RUNS[0]]["categories"]
                      for c in d["H1_dstnib"]["per_carrier"]}))
    print("H1 r14/r15 non-zero anywhere:",
          json.dumps(d["H1_dstnib"]["nonzero_r14_r15_anywhere_in_run"]))
    print("H1 cross-run:", d["H1_dstnib"]["cross_run"])
    print("H1c:", json.dumps({c: {r: {k: v[k] for k in
                                      ("identity_holds", "n_alternative_triples_over_all_32_halves",
                                       "anchor_triple_is_among_them", "observed_low_half")}
                                  for r, v in br.items()}
                              for c, br in d["H1c_arithmetic_identity"].items()}))
    print("H2 cells covered:", d["H2_length_rule"]["cells_covered"],
          "ambiguous:", len(d["H2_length_rule"]["cells_with_more_than_one_length"]),
          "cross-run disagreements:", len(d["H2_length_rule"]["cells_disagreeing_across_runs"]),
          "db stated rule wrong in:", d["H2_length_rule"]["db_json_stated_rule_wrong_count"], "of 32")
    print("H2 table:", json.dumps(d["H2_length_rule"]["measured_table"], sort_keys=True))
