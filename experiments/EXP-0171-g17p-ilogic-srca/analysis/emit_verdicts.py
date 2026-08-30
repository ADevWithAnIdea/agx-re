#!/usr/bin/env python3
"""EXP-0171 -- verdicts. Reads only the two gated runs' append-only JSONL.

  python3 analysis/emit_verdicts.py raw/g17p_20260830_run01 raw/g17p_20260830_run02

METHOD

1. **Carrier gates** (FIELD-SWEEP-PROTOCOL sect 3.5 / sect 7, EXP-0164). For every
   carrier: F1 the byte0 := 0x00 falsifier must be non-`ok`; F2 at least one
   ladder byte must produce >= 2 distinct observations over its dense sweep.
   A carrier failing either is DISCARDED -- it is not evidence of inertness.

2. **A5 decomposition** (EXP-0166). A field of width w inside one byte is
   recovered from that byte's DENSE sweep: the field's sub-values are exactly
   the swept values whose OTHER bits in that byte equal the anchor's. That gives
   2^w sub-values, i.e. the field's whole encodable range, with no reliance on
   `isadb.assemble()` (which cannot clear a bit -- DEF-0166-1). Fields wider
   than one byte use the role=`wide` cases (FIELD-SWEEP-PROTOCOL sect 3.3 set)
   and, separately, the per-byte dense sweeps of every byte they span.

3. **Movement** is measured against the ANCHOR sub-value's own observation on
   the SAME carrier, never against a global constant: moved(v) iff
   digest(v) != digest(anchor_sub).

4. **Cross-run gate.** Per sub-value, (outcome, digest) from run A vs run B.
   Promotion needs agreement >= 0.99 AND moved >= 2 x disagreement AND every
   sub-value covered by BOTH runs.

5. **A field that never moves** is promotable only if the carriers differ in the
   dimension the field controls -- DIMENSIONS below names that dimension per
   field, and a key with no declared dimension is never promoted from
   inertness. Where the role is unknown the label is
   `single-template-inference`, never `hardware-run`: emitter grade asserts the
   implementer may CHOOSE the value, and "emit what the compiler emitted" is a
   captured-template dependency.

CLEAN-ROOM: reads our own JSONL evidence and our own frozen db.json. No Apple
binary is introspected.
"""
from __future__ import print_function

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "work" / "frozen"))
sys.path.insert(0, str(EXP / "harness"))

DB = json.loads((EXP / "work" / "frozen" / "db.json").read_text())["instructions"]
DBI = dict((i["mnemonic"], i) for i in DB)
VAL = json.loads((EXP / "work" / "frozen" / "validation.json").read_text())["instructions"]

GRADE = ("hardware-run", "isolated-byte-diff")

# The dimension each field CONTROLS, and therefore the dimension two carriers
# must differ in before an inertness reading from them means anything.
DIMENSIONS = {
    "outmod": "the CONSUMER of the result. NAT = consumed by the compiler's own "
              "device_store into device memory; SYNTH/FRAME = read out of the "
              "GPR file by a later 16-register dump. db.json types outmod's "
              "value 128 as 'output/store', so the consumer IS the dimension.",
    "z6": "instruction FRAMING and the consumer. FRAME places a 6B falu2i then a "
          "2B mov_imm immediately after the block, so a trailing byte that were "
          "a length/framing bit would lose both markers; NAT/SYNTH differ in the "
          "consumer.",
    "z8": "as z6.", "z9": "as z6.",
    "ext8": "as z6.", "ext9": "as z6.",
    "tail": "as z6 -- framing plus the consumer.",
    "lut_a_free": "WHICH LUT2 boolean function is selected. Five store-consumed "
                  "NAT carriers with compiler-chosen selectors for "
                  "and / or / xor / andn / nand.",
    "lut_a_sel": "as lut_a_free.", "lut_a_z": "as lut_a_free.",
    "modA": "as lut_a_free.", "modB": "as lut_a_free.",
    "srcA": "operand PROVENANCE. NAT operands are LOADED from device buffers by "
            "the compiler's own device_load; SYNTH/FRAME operands are "
            "mov_imm-seeded GPRs with a known seed table.",
    "srcB": "as srcA.", "src_reg": "as srcA.", "src_flag": "as srcA.",
    "subop": "whether the estimate is REFINED. NAT k_rsqrt is followed by the "
             "compiler's own Newton-Raphson refinement, which corrects the "
             "estimate whatever it was (EXP-0161's failure mode); SYNTH lifts "
             "the estimate ALONE with nothing after it.",
    "sign_ext": "signed vs unsigned extract. k_bfe (unsigned) and k_bfe_s "
                "(signed) are compiler-chosen anchors on either side of exactly "
                "this bit.",
    "b2_fmt": "the store-enable/format byte, plus the consumer dimension.",
    "b2_bit0": "as b2_fmt.",
    "fmt": "the bfloat operand format (scalar vs packed lanes), plus the "
           "consumer dimension.",
    "opsel_hi": "the op-select family, plus the consumer dimension.",
}


def load(rundir):
    recs = []
    for ln in (Path(rundir) / "sweep.jsonl").open():
        ln = ln.strip()
        if ln:
            try:
                recs.append(json.loads(ln))
            except Exception:
                pass
    return recs


def obs_key(r):
    """What counts as 'the observation' for movement / agreement."""
    return (r["outcome"], r["observed"]["digest"], r["poison_out"])


def carrier_gates(recs):
    """{carrier_id: {...}} -- F1 and F2 per carrier, from raw."""
    byc = defaultdict(lambda: {"falsifier": [], "ladder": defaultdict(set),
                               "arm": None, "carrier": None, "probe": None})
    for r in recs:
        e = byc[r["carrier_id"]]
        e["arm"], e["carrier"], e["probe"] = r["arm"], r["carrier"], r["probe"]
        if r["role"] == "falsifier":
            e["falsifier"].append(r["outcome"])
        elif r["role"] == "ladder":
            e["ladder"][r["byte_index"]].add(obs_key(r))
    out = {}
    for cid, e in byc.items():
        f1 = bool(e["falsifier"]) and all(o != "ok" for o in e["falsifier"])
        live = dict((b, len(v)) for b, v in e["ladder"].items())
        f2 = any(v >= 2 for v in live.values())
        out[cid] = {"arm": e["arm"], "carrier": e["carrier"], "probe": e["probe"],
                    "F1_falsifier_non_ok": f1,
                    "F1_outcomes": e["falsifier"],
                    "F2_ladder_distinct_obs": live,
                    "F2_ladder_live": f2,
                    "admitted": bool(f1 and f2)}
    return out


def field_span(mn, fname):
    d = DBI.get(mn)
    if not d:
        return None
    for f in d["fields"]:
        if f["name"] == fname:
            s, w = f["start"], f["width"]
            return s, w, s // 8, (s + w - 1) // 8
    return None


def decompose(recs_by_byte, anchor, start, width, bidx):
    """A5: sub-values of a single-byte field from that byte's dense sweep."""
    bit = start % 8
    mask = (1 << width) - 1
    other = anchor[bidx] & ~(mask << bit) & 0xFF
    sub = {}
    seen_bytes = set()
    for v, r in sorted(recs_by_byte.items()):
        seen_bytes.add(r["bytes"])
        if (v & ~(mask << bit) & 0xFF) != other:
            continue
        sub[(v >> bit) & mask] = r
    return sub, seen_bytes


def analyse_key(key, runs, gates, arms):
    mn, fname = key.split(".", 1)
    span = field_span(mn, fname)
    if span is None:
        return {"label": "untested", "note": "field absent from the frozen db.json"}
    start, width, b0, b1 = span
    prior = VAL.get(mn, {}).get(fname, {})
    multi = (b0 != b1)

    percar = {}
    for cid, g in gates.items():
        if not g["admitted"]:
            continue
        if key not in arms.get(g["arm"], []):
            continue
        # collect this carrier's dense sweep of the field's byte(s)
        per_run = {}
        anchor = None
        allbytes = set()
        for rname, recs in runs.items():
            byv = {}
            for r in recs:
                if r["carrier_id"] != cid:
                    continue
                if anchor is None:
                    anchor = bytes.fromhex(r["anchor_bytes"])
                if multi:
                    if r["role"] == "wide" and r.get("field") == fname:
                        byv[r["value"]] = r
                        allbytes.add(r["bytes"])
                else:
                    if r["role"] in ("ladder", "target") and r["byte_index"] == b0:
                        byv[r["value"]] = r
                        allbytes.add(r["bytes"])
            if byv:
                per_run[rname] = byv
        if len(per_run) < 2 or anchor is None:
            continue
        if multi:
            subs = dict((rn, dict((v, r) for v, r in byv.items()))
                        for rn, byv in per_run.items())
            enc = 1 << width
            anchor_sub = None
            for k, b in enumerate(range(b0, b1 + 1)):
                pass
            anchor_sub = 0
            for k, b in enumerate(range(b0, b1 + 1)):
                anchor_sub |= anchor[b] << (8 * k)
        else:
            subs = {}
            for rn, byv in per_run.items():
                s, sb = decompose(byv, anchor, start, width, b0)
                subs[rn] = s
            enc = 1 << width
            anchor_sub = (anchor[b0] >> (start % 8)) & ((1 << width) - 1)

        rn = sorted(subs)
        common = set(subs[rn[0]]) & set(subs[rn[1]])
        agree = disagree = 0
        moved = 0
        moved_vals = []
        accept = []
        for v in sorted(common):
            a, b = obs_key(subs[rn[0]][v]), obs_key(subs[rn[1]][v])
            if a == b:
                agree += 1
            else:
                disagree += 1
        ref = subs[rn[0]].get(anchor_sub)
        refk = obs_key(ref) if ref is not None else None
        for v in sorted(common):
            k0, k1 = obs_key(subs[rn[0]][v]), obs_key(subs[rn[1]][v])
            if k0 != k1:
                continue
            if refk is not None and k0 != refk:
                moved += 1
                moved_vals.append(v)
            if subs[rn[0]][v]["outcome"] == "ok":
                accept.append(v)
        outc = defaultdict(int)
        for v in sorted(common):
            outc[subs[rn[0]][v]["outcome"]] += 1
        percar[cid] = {
            "carrier": gates[cid]["carrier"], "probe": gates[cid]["probe"],
            "subvalues_common": len(common), "encodable_range": enc,
            "distinct_bytes": len(allbytes),
            "values_dispatched": len(per_run[rn[0]]),
            "anchor_subvalue": anchor_sub,
            "agree": agree, "disagree": disagree,
            "agreement": (round(agree / float(agree + disagree), 5)
                          if agree + disagree else None),
            "moved": moved, "moved_subvalues": moved_vals[:64],
            "accept_set": accept[:64], "outcomes": dict(outc),
            "sentinel_bad": sum(1 for r in per_run[rn[0]].values()
                                if r["sentinel_bad"]),
            "invalid_run": sum(1 for r in per_run[rn[0]].values()
                               if r["invalid_run"]),
            "poison_out_cases": sum(1 for r in per_run[rn[0]].values()
                                    if r["poison_out"]),
        }

    # ---- the gate ----
    row = {"start": start, "width": width, "encodable_range": 1 << width,
           "target": "G17P", "evidence": ["EXP-0171"],
           "prior_label": prior.get("label"), "prior_target": prior.get("target"),
           "carriers": percar,
           "dimension": DIMENSIONS.get(fname),
           }
    if not percar:
        row["label"] = "untested"
        row["note"] = ("no ADMITTED carrier covered this field in both gated "
                       "runs (carrier gates F1/F2, FIELD-SWEEP-PROTOCOL 3.5)")
        row["values_dispatched"] = 0
        row["distinct_bytes"] = 0
        return row

    best = None
    for cid, c in percar.items():
        ok_cov = (c["distinct_bytes"] >= min(256, c["encodable_range"])
                  if not multi else
                  c["values_dispatched"] == c["distinct_bytes"])
        ok_run = (c["agreement"] is not None and c["agreement"] >= 0.99
                  and c["subvalues_common"] == c["encodable_range"])
        ok_move = c["moved"] > 0 and c["moved"] >= 2 * c["disagree"]
        ok_hyg = (c["invalid_run"] == 0 and
                  c["sentinel_bad"] <= max(1, 0.01 * c["values_dispatched"]))
        score = (ok_cov and ok_run and ok_move and ok_hyg, c["moved"])
        if best is None or score > best[0]:
            best = (score, cid, ok_cov, ok_run, ok_move, ok_hyg)
    score, cid, ok_cov, ok_run, ok_move, ok_hyg = best
    c = percar[cid]
    row["values_dispatched"] = c["values_dispatched"]
    row["distinct_bytes"] = c["distinct_bytes"]
    row["decisive_carrier"] = cid
    row["range"] = ("%d of %d sub-values, from a DENSE %d-value byte sweep "
                    "(%d distinct encodings)"
                    % (c["subvalues_common"], c["encodable_range"],
                       c["values_dispatched"], c["distinct_bytes"]))
    n_car = len(percar)
    styles = set(v["carrier"] for v in percar.values())
    probes = set(v["probe"] for v in percar.values())
    any_moved = any(v["moved"] > 0 for v in percar.values())

    if score[0]:
        row["label"] = "hardware-run"
        row["note"] = ("moved %d of %d sub-values on %s; cross-run agreement "
                       "%.4f over %d admitted carrier(s) (%s / %s). accept-set "
                       "%s. outcomes %s"
                       % (c["moved"], c["subvalues_common"], cid,
                          c["agreement"], n_car, ",".join(sorted(styles)),
                          ",".join(sorted(probes)),
                          c["accept_set"] if len(c["accept_set"]) <= 32
                          else "%d values" % len(c["accept_set"]),
                          json.dumps(c["outcomes"], sort_keys=True)))
    elif not any_moved:
        dim = DIMENSIONS.get(fname)
        enough = (n_car >= 2 and len(styles) >= 2 and dim is not None)
        row["label"] = ("single-template-inference" if enough else "untested")
        row["note"] = (("DENSE-INERT: 0 of %d sub-values moved on %d admitted "
                        "carriers (%s / %s), every carrier's liveness ladder "
                        "PROVEN live and its byte0 falsifier PROVEN non-ok. "
                        % (c["subvalues_common"], n_car,
                           ",".join(sorted(styles)), ",".join(sorted(probes))))
                       + (("The carriers DO differ in the dimension this field "
                           "would control: %s Held at "
                           "single-template-inference rather than promoted "
                           "because the field's ROLE is unknown -- emitter "
                           "grade asserts the implementer may CHOOSE the "
                           "value, and 'emit what the compiler emitted' is a "
                           "captured-template dependency. A don't-care needs "
                           "the orchestrator's call, not this experiment's."
                           % dim) if enough else
                          ("NOT promotable: %s. Two carriers identical in the "
                           "controlled dimension are one carrier (EXP-0164)."
                           % ("no dimension declared for this field name"
                              if dim is None else
                              "fewer than 2 admitted carrier STYLES"))))
    else:
        why = []
        if not ok_cov:
            why.append("coverage incomplete (%d distinct encodings, %d "
                       "sub-values of %d)" % (c["distinct_bytes"],
                                              c["subvalues_common"],
                                              c["encodable_range"]))
        if not ok_run:
            why.append("cross-run gate: agreement %s over %d sub-values"
                       % (c["agreement"], c["subvalues_common"]))
        if not ok_move:
            why.append("movement %d < 2 x disagreement %d"
                       % (c["moved"], c["disagree"]))
        if not ok_hyg:
            why.append("hygiene: %d invalid_run, %d sentinel_bad"
                       % (c["invalid_run"], c["sentinel_bad"]))
        row["label"] = "corpus-correlation"
        row["note"] = ("MOVED but did not clear the gate on any carrier: %s. "
                       "Best carrier %s, moved %d of %d."
                       % ("; ".join(why), cid, c["moved"],
                          c["subvalues_common"]))
    row["semantics"] = prior.get("range") or ""
    return row


def main():
    runs = sys.argv[1:]
    if len(runs) < 2:
        print("need two gated run dirs")
        return 2
    import casematrix as CM
    arms = dict((s["arm"], s["verdict_keys"]) for s in CM.ARMS)
    loaded = dict((Path(r).name, load(r)) for r in runs)
    allrecs = [r for v in loaded.values() for r in v]
    gates = carrier_gates(allrecs)

    verdicts = {}
    for arm, keys in arms.items():
        for k in keys:
            verdicts[k] = analyse_key(k, loaded, gates, arms)

    # xplant positive control (ILOGIC): did the transplant produce the
    # transplanted kernel's FUNCTION, host-computed?
    import sweeprun as S
    xp = []
    for rname, recs in loaded.items():
        for r in recs:
            if r["role"] != "xplant":
                continue
            want = S.host_oracle_nat(r["xplant_from"])
            got = r["observed"]["words"]
            swapped = None
            if want and got:
                op = CM.KERNELS[r["xplant_from"]]["op"]
                f = S.HOST_OPS.get(op)
                if f:
                    sw = [f(S.UB[i], S.UA[i], S.UC[i]) & 0xFFFFFFFF
                          for i in range(8)] + [S.POISON] * 8 + \
                         [S.SENT_A, S.SENT_B]
                    swapped = (got == sw)
            xp.append({"run": rname, "into": r["probe"],
                       "from": r["xplant_from"], "bytes": r["bytes"],
                       "outcome": r["outcome"],
                       "matched_transplanted_function": bool(want and got == want),
                       "matched_with_operands_swapped": swapped,
                       "poison_out": r["poison_out"]})

    out = {"_spec": "FIELD-SWEEP-PROTOCOL sect 5, flat <mnemonic>.<field>",
           "_experiment": "EXP-0171", "_target": "G17P",
           "_runs": sorted(loaded),
           "_carrier_gates": gates,
           "_xplant_positive_control": xp,
           "verdicts": verdicts}
    (HERE / "field_verdicts.json").write_text(json.dumps(out, indent=1,
                                                         sort_keys=True))
    flat = dict((k, dict((kk, vv) for kk, vv in v.items()
                         if kk in ("label", "range", "target", "evidence",
                                   "semantics", "note", "values_dispatched",
                                   "distinct_bytes", "encodable_range",
                                   "start", "width")))
                for k, v in verdicts.items())
    (HERE / "field_verdicts_flat.json").write_text(json.dumps(flat, indent=1,
                                                              sort_keys=True))
    n = defaultdict(int)
    for k, v in sorted(verdicts.items()):
        n[v["label"]] += 1
        print("%-28s %-28s prior=%s" % (k, v["label"], v.get("prior_label")))
    print()
    print("labels:", json.dumps(dict(n), sort_keys=True))
    print("carriers admitted: %d of %d"
          % (sum(1 for g in gates.values() if g["admitted"]), len(gates)))
    print("xplant controls:", sum(1 for x in xp if x["matched_transplanted_function"]),
          "matched /", len(xp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
