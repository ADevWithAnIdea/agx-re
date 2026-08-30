#!/usr/bin/env python3
"""EXP-0154 analysis: raw sweep records -> per-field verdicts (G17P).

  python3 analysis/verdicts.py raw/g17p_20260829_run01 raw/g17p_20260829_run02

Applies the promotion rule frozen in PRE_REGISTRATION.md section 7 and emits
`analysis/field_verdicts.json` in FIELD-SWEEP-PROTOCOL section 5 schema.

Nothing here re-runs hardware; it is a pure function of the committed raw logs.
"""
from __future__ import print_function

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H          # noqa: E402
import casematrix as CM          # noqa: E402

GOOD = ("hardware-run", "isolated-byte-diff")
RANKORD = {"hardware-run": 2, "isolated-byte-diff": 1, "untested": 0}


def load(rundir):
    recs = {}
    p = Path(rundir) / "sweep.jsonl"
    for ln in p.open():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        recs[r["idx"]] = r            # last write wins (resume-safe)
    return recs


def mask_rule(ok_vals, all_vals, width):
    """Smallest (MASK, V) such that every ok value satisfies (v & MASK) == V.
    Returns (mask, val, exact, exceptions)."""
    ok = set(ok_vals)
    if not ok:
        return (None, None, False, None)
    mask = 0
    val = 0
    for b in range(width):
        s = set((v >> b) & 1 for v in ok)
        if len(s) == 1:
            mask |= 1 << b
            val |= s.pop() << b
    pred = set(v for v in all_vals if (v & mask) == val)
    exceptions = len(pred ^ ok)
    return (mask, val, exceptions == 0, exceptions)


# Candidate descriptor->register-index models. `(reg<<1)|is32` is the
# project-standard packing (EXP-0099/0105/0113/0119); `reg<<2` is the packing
# EXP-0128/EXP-0139 HW-validated for iadd2's srcB_imm; the rest are the obvious
# alternatives, scored on the same data so the winner is chosen, not assumed.
REG_MODELS = {
    "reg = v>>1  ((reg<<1)|size)": lambda v: v >> 1,
    "reg = (v>>1)&63": lambda v: (v >> 1) & 63,
    "reg = v>>2  (reg<<2)": lambda v: v >> 2,
    "reg = v&127": lambda v: v & 127,
    "reg = v&15": lambda v: v & 15,
    "reg = v": lambda v: v,
}
MIN_MODEL_HITRATE = 0.90
MIN_MODEL_REGS = 6


def register_maps(recs_for_field, base_regs):
    """H3: which register did each swept value RELEASE (read-and-zero), and
    which register did it WRITE? Both are read straight out of the 16-register
    dump and are independent of the instruction's arithmetic, which is what
    makes them usable on families whose operation we have not modelled.

    Only r0..r15 are seeded and dumped, so a model value >= 16 names a register
    this carrier cannot observe; those cases are EXCLUDED from the model's
    denominator rather than scored as misses."""
    released, written = {}, {}
    for v, r in sorted(recs_for_field.items()):
        obs = r["observed"]["regs"]
        if not obs or r["outcome"] in ("fault", "hang", "undecodable"):
            continue
        released[v] = [i for i in range(H.N_REGS)
                       if base_regs[i] != 0 and obs[i] == 0]
        written[v] = [i for i in range(H.N_REGS)
                      if obs[i] != base_regs[i] and obs[i] != 0]

    def score(obsmap):
        """A value that produced NO observable release (or no observable write)
        is not a MISS -- release is gated by the descriptor's own size/last-use
        bits, so the honest denominator is `hits + wrong`: of the cases where a
        single register WAS identified, how many did the model predict?
        `silent` is reported alongside so a reader can see the coverage."""
        out = {}
        for name, f in REG_MODELS.items():
            hits = wrong = silent = multi = 0
            regs = set()
            for v, got in obsmap.items():
                pred = f(v)
                if pred >= H.N_REGS:
                    continue          # unobservable in this carrier
                if len(got) == 0:
                    silent += 1
                elif len(got) > 1:
                    multi += 1
                elif got[0] == pred:
                    hits += 1
                    regs.add(pred)
                else:
                    wrong += 1
            den = hits + wrong
            if den:
                out[name] = {"hits": hits, "wrong": wrong, "silent": silent,
                             "multi": multi, "identified": den,
                             "rate": round(hits / float(den), 3),
                             "distinct_regs": len(regs)}
        return out

    return released, written, {"released": score(released),
                               "written": score(written)}


def best_model(scoretab):
    """Prefer the model with the most confirmed distinct registers; break ties
    on hit count. Requires >=90% of identified registers predicted and >=6
    distinct registers confirmed, so a coincidence on one or two cannot win."""
    best = None
    for name, s in scoretab.items():
        if s["rate"] >= MIN_MODEL_HITRATE and s["distinct_regs"] >= MIN_MODEL_REGS:
            k = (s["distinct_regs"], s["hits"])
            if best is None or k > (best[1]["distinct_regs"], best[1]["hits"]):
                best = (name, s)
    return best


FTYPE = {}


def field_type(instr, field):
    if not FTYPE:
        import json as _j
        db = _j.loads((H.ISA_DIR / "db.json").read_text())
        for i in db["instructions"]:
            for f in i["fields"]:
                FTYPE[(i["mnemonic"], f["name"])] = f.get("type")
    return FTYPE.get((instr, field))


def main():
    runs = sys.argv[1:]
    if not runs:
        print("usage: verdicts.py <rundir> [<rundir2> ...]"); return 2
    loaded = [load(r) for r in runs]
    rep = json.loads((EXP / "work" / "anchor_report.json").read_text()) \
        if (EXP / "work" / "anchor_report.json").exists() else \
        json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases = {c["idx"]: c for c in CM.build_cases(rep)}

    # ---- cross-run gate --------------------------------------------------
    gated = {}
    disagree = Counter()
    victim_excluded = 0
    for idx, c in cases.items():
        rs = [L.get(idx) for L in loaded]
        rs = [r for r in rs if r is not None]
        if not rs:
            continue
        if any(r.get("victim") for r in rs):
            victim_excluded += 1
            continue
        ocs = set(r["outcome"] for r in rs)
        if len(ocs) > 1:
            disagree[(c["arm"], c["field"])] += 1
            continue
        r = dict(rs[0])
        r["n_runs"] = len(rs)
        gated[idx] = r

    # ---- baselines per arm ------------------------------------------------
    base_regs = {}
    for idx, r in gated.items():
        c = cases[idx]
        if c["field"] == "__falsifier_byte0":
            continue
        if r["oracle"]["digest"] and c["arm"] not in base_regs:
            d = r["oracle"]["digest"]
            base_regs[c["arm"]] = [int(d[i * 8:(i + 1) * 8], 16) for i in range(16)]

    # ---- falsifiers -------------------------------------------------------
    fals = {}
    for idx, r in gated.items():
        if cases[idx]["field"] == "__falsifier_byte0":
            fals[cases[idx]["arm"]] = r["outcome"]

    # ---- group by (arm, instr, field[, byte_index]) ----------------------
    groups = defaultdict(dict)
    for idx, r in gated.items():
        c = cases[idx]
        if c["field"].startswith("__"):
            continue
        key = (c["arm"], c["instr"], c["field"], c.get("byte_index"))
        groups[key][c["value"]] = r

    out = {}
    for (arm, instr, field, bidx), recs in sorted(groups.items()):
        vals = sorted(recs)
        width = cases_width(cases, arm, field, bidx)
        okv = [v for v in vals if recs[v]["outcome"] == "ok"]
        oc = Counter(recs[v]["outcome"] for v in vals)
        mask, mval, exact, exc = mask_rule(okv, vals, width)
        rel, wr, scores = register_maps(recs, base_regs.get(arm, [0] * 16))

        dense = (len(vals) == (1 << width))
        fal_ok = fals.get(arm) != "ok"
        # PRE_REGISTRATION section 7: promotion requires an identical per-value
        # outcome map in BOTH gated runs. A value only one run reached is not
        # gated evidence, so the whole field stays `untested`.
        two_runs = all(recs[v].get("n_runs", 1) >= 2 for v in vals)
        bm_rel = best_model(scores["released"])
        bm_wr = best_model(scores["written"])
        ftype = field_type(instr, field)

        if not fal_ok:
            label = "untested"
            why = ("arm %s FAILED its pre-registered falsifier: forcing byte0 of "
                   "the instruction under test to 0x00 still reproduced the full "
                   "baseline register state, so this arm cannot detect a "
                   "difference and nothing in it is promoted" % arm)
        elif not two_runs:
            label, why = "untested", ("not covered by both gated runs "
                                      "(%d/%d values have 2 runs)"
                                      % (sum(1 for v in vals
                                             if recs[v].get("n_runs", 1) >= 2), len(vals)))
        elif not okv:
            label, why = "untested", "no value reproduced the anchor"
        elif len(okv) == len(vals) and dense:
            label, why = "hardware-run", "INERT across the whole encodable range"
        elif len(okv) == len(vals):
            # inert over a SAMPLED set only: an emitter may not conclude the
            # field is a don't-care everywhere from ~30 of 2^w values.
            label, why = ("isolated-byte-diff",
                          "inert across the %d SAMPLED values only; the full "
                          "%d-value range was NOT swept" % (len(vals), 1 << width))
        elif exact and dense and fal_ok:
            label, why = "hardware-run", "exact rule (v & 0x%02x) == 0x%02x, 0 exceptions" % (mask, mval)
        elif exc is not None and exc <= 2 and dense and fal_ok:
            label, why = "isolated-byte-diff", "rule (v & 0x%02x) == 0x%02x with %d exception(s)" % (mask, mval, exc)
        else:
            label, why = "untested", "no exact rule; %d/%d values ok" % (len(okv), len(vals))
        # A REGISTER-typed field is not characterised by "which single value
        # reproduces the anchor" -- an emitter needs the value -> register-index
        # MAP. The 16-register dump supplies it directly (release-on-read for
        # sources, the written register for destinations), so where a model
        # explains the map that is the stronger verdict and it wins.
        # NOT gated on db.json's declared type: `iadd2.srcB_ext` is typed `mod`
        # and is in fact the srcA REGISTER SELECTOR (DEF-0154-4). Where the
        # 16-register dump yields a value -> register map, that map IS the
        # field's semantics whatever db.json calls it.
        # The register-map override is subject to the SAME falsifier gate as the
        # mask rule. PRE_REGISTRATION section 6 F0: if forcing byte0 to 0x00 still
        # reproduces the baseline, the arm cannot see a difference and NOTHING in
        # it may be promoted. (CARRY_GEN and MOV_ZEXT16 both failed F0 here.)
        if (bm_rel or bm_wr) and fal_ok and two_runs:
            if bm_wr and not bm_rel:
                pick, role = bm_wr, "destination (written)"
            elif field.startswith("dst"):
                # db.json names it a destination and the map confirms a
                # register; when the instruction's result is 0 a destination
                # write LOOKS like a release (both leave the register at 0), so
                # the zero heuristic alone cannot separate the two roles.
                pick = bm_wr or bm_rel
                role = ("destination (register identified; the result value is 0 "
                        "in this carrier, so destination-write and "
                        "release-on-read are not separated)")
            else:
                pick, role = bm_rel, "source (released-on-read)"
            if RANKORD[label] < RANKORD["hardware-run"]:
                label = "hardware-run"
            why = ("%s operand descriptor: %s, matched %d/%d identified over %d "
                   "distinct registers (%d values produced no observable "
                   "release/write); %s"
                   % (role, pick[0], pick[1]["hits"], pick[1]["identified"],
                      pick[1]["distinct_regs"], pick[1]["silent"], why))
            entry_extra = {"register_model": pick[0], "register_model_stats": pick[1],
                           "register_role": role}
        else:
            entry_extra = {}

        if bidx is not None and label == "hardware-run":
            # a byte of a wider raw field: the full multi-byte space is NOT claimed
            label = "isolated-byte-diff"
            why += "; swept BYTE-WISE only, full field space not claimed"

        key = "%s.%s" % (instr, field) + ("" if bidx is None else "@byte+%d" % bidx)
        entry = {
            "label": label,
            "range": "%d values tested (%s over %d-bit domain)"
                     % (len(vals), "dense" if dense else "sampled", width),
            "target": "G17P",
            "evidence": ["EXP-0154"],
            "semantics": why,
            "note": "carrier %s; outcomes %s; ok at %s"
                    % (recs[vals[0]]["carrier"], dict(oc), compact(okv)),
            "arm": arm,
            "falsifier_fired": fal_ok,
            "n_runs_gated": recs[vals[0]].get("n_runs", 1),
        }
        entry.update(entry_extra)
        if scores["released"] or scores["written"]:
            entry["register_model_scores"] = scores
        if bidx is None and width <= 8 and len(okv) <= 40:
            entry["released_reg_map"] = dict((str(v), rel.get(v)) for v in okv)
        out[key] = entry

    # ---- db.json defects (FIELD-SWEEP-PROTOCOL section 6) ----------------
    # RECORDED, NOT EDITED: db.json is the orchestrator's file.
    defects = {}

    # (1) half_pack: our length rule is gated on byte+1 == 0x05, but G17P's own
    # compiler emits a different byte+1 for the same instruction, so the DB
    # cannot tokenize our own G17P shader.
    hp = rep.get("k_half2", {})
    if hp.get("leftover"):
        lo = hp["leftover"]
        defects["DEF-0154-1_half_pack_length_rule_overconstrained"] = {
            "instruction": "half_pack",
            "observed": ("compiling our own `half2 add` (kernels/probes.metal::k_half2) on "
                         "G17P produced `_agc.main` = %s, which tools/agx-isa tokenizes as "
                         "get_sr + device_load + device_load + half_alu and then leaves "
                         "%d bytes UNDECODED: %s" % (hp.get("main_hex"), len(lo) // 2, lo)),
            "cause": ("isadb.py's length rule accepts byte0 == 0x18 as a 4-byte half_pack "
                      "only when byte+1 == 0x05 and (byte+2 & 0xf8) == 0x18. The G17P "
                      "instruction here is `18 03 18 05` -- byte+1 = 0x03 -- so the gate "
                      "rejects it and the remaining 22 bytes (half_pack + device_store + "
                      "stop) never tokenize."),
            "prior_record": ("EXP-0038 recorded the A18 form as `18 05 18 03`. The two "
                             "differ by swapping byte+1 and byte+3, i.e. by register "
                             "allocation, NOT by opcode -- so byte+1 is an operand "
                             "descriptor and must not be a length gate."),
            "impact": "an emitter following db.json cannot even round-trip a G17P half2 pack",
            "evidence": "work/anchor_report.json :: k_half2",
        }

    # (2) ilogic has NO destination field: byte0 is an 8-bit match constant, so
    # db.json gives an emitter no way to choose where the result lands.
    ilg = [f["name"] for f in
           [i for i in json.loads((H.ISA_DIR / "db.json").read_text())["instructions"]
            if i["mnemonic"] == "ilogic"][0]["fields"]]
    dstreg = None
    for k, v in out.items():
        if k.startswith("ilogic.") and v.get("register_role", "").startswith("destination"):
            dstreg = v.get("register_model")
    defects["DEF-0154-2_ilogic_has_no_destination_field"] = {
        "instruction": "ilogic",
        "observed": ("db.json models byte0 as a fixed 8-bit match (0x0b) and lists no "
                     "destination field at all: %s. An emitter therefore has no modelled "
                     "way to choose the result register." % ilg),
        "this_experiment": ("the 16-register dump locates the destination directly; see "
                            "analysis/crosscheck.json :: ilogic_lut.dst_register"),
        "register_model_found": dstreg,
        "evidence": "raw/*/sweep.jsonl arm ILOGIC",
    }

    # (3) data-driven: fields db types as `reg` whose behaviour this experiment
    # decoded, and fields db does NOT type as `reg` that behave like operand
    # descriptors anyway.
    mistyped = {}
    for k, v in out.items():
        if k.startswith("_") or "register_model" not in v:
            continue
        mn, fld = k.split("@")[0].split(".", 1)
        if field_type(mn, fld) != "reg":
            mistyped[k] = {"db_type": field_type(mn, fld),
                           "behaves_as": v["register_role"],
                           "model": v["register_model"],
                           "stats": v["register_model_stats"]}
    if mistyped:
        defects["DEF-0154-3_fields_that_behave_as_operand_descriptors"] = {
            "observed": ("these fields are not typed `reg` in db.json, but the 16-register "
                         "dump identifies a value -> register-index map for them"),
            "fields": mistyped,
        }
    # (4) iadd2.srcB_ext is the srcA REGISTER SELECTOR, not a modifier.
    se = out.get("iadd2.srcB_ext", {})
    defects["DEF-0154-4_iadd2_srcB_ext_is_the_srcA_register_selector"] = {
        "instruction": "iadd2",
        "db_says": "field `srcB_ext`, type `mod`, 7 bits at bit49",
        "hardware_says": ("it selects the srcA REGISTER in the reg<<2 packing: "
                          "d = r[srcB_ext>>2] + r[srcB_imm>>2]. Matched 128/128 "
                          "over the full dense 7-bit sweep on a 32-bit carrier, "
                          "confirming all 16 observable registers; every value "
                          "naming an unseeded register (>=r16) reads 0."),
        "corrects": ("EXP-0128 / EXP-0139 recorded that iadd2's `srcA` byte (byte+7 "
                     "= 0xa8) 'always reads r0'. It read r0 only because srcB_ext "
                     "was 0 in every compiler-emitted anchor. byte+7 is therefore "
                     "NOT the srcA register selector."),
        "do_not_adopt": ("EXP-0146's `(v & 0x7C) == 0x00` fits the ok-set exactly "
                         "(confirmed here) but only because it encodes 'srcA must "
                         "be r0' for that carrier. As a modifier constraint it "
                         "would tell an emitter bits 2..6 must be zero, when those "
                         "bits are how a register is chosen."),
        "verdict_label": se.get("label"),
        "evidence": "analysis/crosscheck.json :: iadd2_srcB_ext_32bit",
    }

    # (5) the ilogic LUT table's operand labelling contradicts db.json's names.
    defects["DEF-0154-5_ilogic_lut_table_operand_labels_are_swapped"] = {
        "instruction": "ilogic",
        "observed": ("all 16 two-input boolean functions are reachable on G17P and "
                     "EXP-0146's complete M4 selector table reproduces 16/16 -- but "
                     "ONLY when its `a` is read as db.json's `srcB` (byte+3) and its "
                     "`b` as db.json's `srcA` (byte+1)."),
        "impact": ("an emitter combining "
                   "experiments/EXP-0146-m4-emit-int-misc/analysis/ilogic_lut_table.md "
                   "with db.json's field names emits all EIGHT asymmetric functions "
                   "backwards (a_and_not_b, a, not_a_and_b, b, not_b, a_or_not_b, "
                   "not_a, not_a_or_b); the eight symmetric ones still look correct, "
                   "so the bug would surface late and look data-dependent."),
        "evidence": "analysis/crosscheck.json :: ilogic_operand_convention",
    }
    out["db_defects"] = defects

    # ---- ilogic: promote lut_a / lut_b / op_base on the FUNCTIONAL map -----
    # These fields are not characterised by "which value reproduces the anchor"
    # (only `and`, the carrier's own function, does). What an emitter needs is
    # the selector -> boolean-function map, which the dedicated 2-D probe
    # (`__lut2d`) measures directly: 8 distinct threads are not needed because a
    # single (a, b) pair whose bits cover all four (bit_a, bit_b) combinations
    # determines the function bit-exactly, and `derive_lut` returns None unless
    # the result is a CONSISTENT bitwise function across all 32 bit positions.
    def derive_lut2(av, bv, res):
        tab = {}
        for i in range(32):
            ka, kb, kr = (av >> i) & 1, (bv >> i) & 1, (res >> i) & 1
            if (ka, kb) in tab and tab[(ka, kb)] != kr:
                return None
            tab[(ka, kb)] = kr
        if len(tab) < 4:
            return None
        return (tab[(0, 0)] << 3) | (tab[(0, 1)] << 2) | (tab[(1, 0)] << 1) | tab[(1, 1)]

    lut = {}
    for idx, r in gated.items():
        c = cases[idx]
        if c["arm"] == "ILOGIC" and c["field"] == "__lut2d" and r["observed"]["regs"]:
            lut[c["value"]] = r["observed"]["regs"]
    if lut and "ILOGIC" in base_regs:
        A, B = H.SEED_I[0], H.SEED_I[2]     # EXP-0146 convention (DEF-0154-5)
        br = base_regs["ILOGIC"]
        votes = Counter()
        for key, regs in lut.items():
            for i in range(H.N_REGS):
                if regs[i] != br[i] and derive_lut2(A, B, regs[i]) is not None:
                    votes[i] += 1
        if votes:
            dr = votes.most_common(1)[0][0]
            fmap = {}
            sel = {}
            for key, regs in sorted(lut.items()):
                f = derive_lut2(A, B, regs[dr])
                if f is None:
                    continue
                ob, la, lb = key >> 8, (key >> 4) & 15, key & 15
                fmap.setdefault(f, []).append((ob, la, lb))
                sel.setdefault((ob, la & 3, lb & 0x0f), set()).add(f)
            collisions = sum(1 for k, v in sel.items() if len(v) > 1)
            if len(fmap) == 16 and collisions == 0 and fals.get("ILOGIC") != "ok":
                for fld in ("lut_a", "lut_b", "op_base"):
                    k = "ilogic.%s" % fld
                    if k in out:
                        out[k]["label"] = "hardware-run"
                        out[k]["range"] = ("op_base 0..1 x lut_a 0..15 x lut_b 0..15, "
                                           "DENSE (512 combinations). The upper bits of "
                                           "lut_a/lut_b were swept 0..255 separately but "
                                           "the full 2^8 x 2^8 product was NOT swept.")
                        out[k]["semantics"] = (
                            "boolean-function selector: (op_base, lut_a & 3, lut_b & 0x0f) "
                            "selects one of the 16 two-input boolean functions with ZERO "
                            "collisions over the swept space; all 16 functions were "
                            "realized on G17P and EXP-0146's M4 minimal-selector table "
                            "reproduced 16/16 (see DEF-0154-5 for the a/b labelling).")
                        out[k]["lut_destination_register"] = dr
                        out[k]["functions_reached"] = len(fmap)
                        out[k]["selector_collisions"] = collisions

    # ---- per-arm output-path liveness (FIELD-SWEEP-PROTOCOL section 3.2) --
    # "A field whose value cannot reach the output proves nothing." For each arm
    # count how many DISTINCT non-baseline register states its own sweep
    # produced; an arm that never varied cannot support an `INERT` verdict.
    live = defaultdict(set)
    for idx, r in gated.items():
        c = cases[idx]
        if r["observed"]["digest"]:
            live[c["arm"]].add(r["observed"]["digest"])
    arm_live = dict((a, len(v)) for a, v in live.items())
    for k, v in out.items():
        if k.startswith("_") or k == "db_defects" or not isinstance(v, dict):
            continue
        a = v.get("arm")
        v["arm_distinct_states"] = arm_live.get(a, 0)
        if arm_live.get(a, 0) < 2 and v["label"] != "untested":
            v["label"] = "untested"
            v["semantics"] = ("DEMOTED: arm %s produced only %d distinct register "
                              "state(s) over its whole sweep, so no field in it is "
                              "demonstrably live on the output path; %s"
                              % (a, arm_live.get(a, 0), v["semantics"]))

    out["_meta"] = {
        "experiment": "EXP-0154", "target": "G17P",
        "runs": runs, "gated_cases": len(gated),
        "victim_excluded": victim_excluded,
        "cross_run_disagreements": dict((("%s.%s" % k), v)
                                        for k, v in disagree.items()),
        "falsifiers": fals,
        "arm_distinct_register_states": arm_live,
        "promotion_rule": "PRE_REGISTRATION.md section 7",
        "skipped_instructions": CM.SKIPPED,
    }
    p = HERE / "field_verdicts.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote", p, "fields:", len(out) - 2)
    lab = Counter(v["label"] for k, v in out.items()
                  if not k.startswith("_") and k != "db_defects")
    print(dict(lab))


def compact(vs):
    if not vs:
        return "{}"
    if len(vs) > 24:
        return "{%d values}" % len(vs)
    out, i = [], 0
    while i < len(vs):
        j = i
        while j + 1 < len(vs) and vs[j + 1] == vs[j] + 1:
            j += 1
        out.append("0x%x" % vs[i] if i == j else "0x%x-0x%x" % (vs[i], vs[j]))
        i = j + 1
    return "{%s}" % ", ".join(out)


_W = {}


def cases_width(cases, arm, field, bidx):
    if bidx is not None:
        return 8
    k = (arm, field)
    if k not in _W:
        for c in cases.values():
            if c["arm"] == arm and c["field"] == field and c.get("fwidth"):
                _W[k] = c["fwidth"]
                break
        else:
            _W[k] = 8
    return _W[k]


if __name__ == "__main__":
    sys.exit(main() or 0)
