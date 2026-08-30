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
    seen = set()
    for v, r in sorted(recs_by_byte.items()):
        seen.add(r["bytes"])
        if (v & ~(mask << bit) & 0xFF) != other:
            continue
        sub[(v >> bit) & mask] = r
    return sub, seen


def moved(r):
    """MOVEMENT. The unmutated observation of a carrier is exactly its
    `baseline_digest`, and every case carries it, so movement is uniform across
    single-byte and multi-byte fields and needs no anchor case in the sample
    set. (Cross-checked against the anchor sub-value where one exists: for the
    dense sweeps the two definitions agree case-for-case.)"""
    if r["outcome"] in ("fault", "hang", "undecodable"):
        return True
    return r["observed"]["digest"] != r["baseline_digest"]


def gather(recs, cid, span, fname):
    """{run: {subvalue: record}} plus the coverage counters, for one carrier."""
    start, width, b0, b1 = span
    multi = (b0 != b1)
    out = {"subs": {}, "bytes": set(), "dispatched": 0, "anchor_sub": None,
           "per_byte": {}}
    anchor = None
    for r in recs:
        if r["carrier_id"] != cid:
            continue
        if anchor is None:
            anchor = bytes.fromhex(r["anchor_bytes"])
    if anchor is None:
        return None
    if multi:
        wide = dict((r["value"], r) for r in recs
                    if r["carrier_id"] == cid and r["role"] == "wide"
                    and r.get("field") == fname)
        av = 0
        for k, bb in enumerate(range(b0, b1 + 1)):
            av |= anchor[bb] << (8 * k)
        out["subs"] = wide
        out["anchor_sub"] = av
        out["wide_bytes"] = set(r["bytes"] for r in wide.values())
        out["bytes"] = set(out["wide_bytes"])
        out["dispatched"] = len(wide)
        for bb in range(b0, b1 + 1):
            dense = dict((r["value"], r) for r in recs
                         if r["carrier_id"] == cid
                         and r["role"] in ("ladder", "target")
                         and r["byte_index"] == bb)
            out["per_byte"][bb] = {
                "n": len(dense),
                "distinct_bytes": len(set(r["bytes"] for r in dense.values())),
                "moved": sum(1 for r in dense.values() if moved(r)),
                "accept_n": sum(1 for r in dense.values()
                                if r["outcome"] == "ok")}
            out["bytes"] |= set(r["bytes"] for r in dense.values())
    else:
        dense = dict((r["value"], r) for r in recs
                     if r["carrier_id"] == cid
                     and r["role"] in ("ladder", "target")
                     and r["byte_index"] == b0)
        if not dense:
            return None
        sub, seen = decompose(dense, anchor, start, width, b0)
        out["subs"] = sub
        out["bytes"] = seen
        out["dispatched"] = len(dense)
        out["anchor_sub"] = (anchor[b0] >> (start % 8)) & ((1 << width) - 1)
        out["per_byte"][b0] = {
            "n": len(dense), "distinct_bytes": len(seen),
            "moved": sum(1 for r in dense.values() if moved(r)),
            "accept_n": sum(1 for r in dense.values()
                            if r["outcome"] == "ok")}
    return out


def analyse_key(key, runs, gates, arms):
    mn, fname = key.split(".", 1)
    span = field_span(mn, fname)
    if span is None:
        return {"label": "untested",
                "note": "field absent from the frozen db.json"}
    start, width, b0, b1 = span
    multi = (b0 != b1)
    prior = VAL.get(mn, {}).get(fname, {})

    percar = {}
    for cid, g in gates.items():
        if not g["admitted"] or key not in arms.get(g["arm"], []):
            continue
        got = {}
        for rname, recs in runs.items():
            gg = gather(recs, cid, span, fname)
            if gg and gg["subs"]:
                got[rname] = gg
        if len(got) < 2:
            continue
        rn = sorted(got)
        A, B = got[rn[0]], got[rn[1]]
        common = set(A["subs"]) & set(B["subs"])
        agree = disagree = 0
        mv = []
        acc = []
        outc = defaultdict(int)
        for v in sorted(common):
            ra, rb = A["subs"][v], B["subs"][v]
            if obs_key(ra) == obs_key(rb):
                agree += 1
                if moved(ra):
                    mv.append(v)
                if ra["outcome"] == "ok":
                    acc.append(v)
            else:
                disagree += 1
            outc[ra["outcome"]] += 1
        percar[cid] = {
            "carrier": g["carrier"], "probe": g["probe"],
            "subvalues_common": len(common),
            "encodable_range": 1 << width,
            # COVERAGE, per the coordinator's schema: `values_dispatched` and
            # `distinct_bytes` are about THIS FIELD's own values, so
            # distinct_bytes < values_dispatched is the DEF-0166-1
            # under-coverage signature and distinct_bytes == encodable_range is
            # completeness. The number of distinct encodings of the whole
            # containing BYTE is carried separately.
            "values_dispatched": len(A["subs"]),
            "distinct_bytes": len(set(r["bytes"] for r in A["subs"].values())),
            "byte_sweep_distinct_encodings": len(A["bytes"]),
            "wide_values_dispatched": A["dispatched"],
            "wide_distinct_bytes": len(A.get("wide_bytes", A["bytes"])),
            "anchor_subvalue": A["anchor_sub"],
            "per_byte_dense": A["per_byte"],
            "agree": agree, "disagree": disagree,
            "agreement": (round(agree / float(agree + disagree), 5)
                          if agree + disagree else None),
            "moved": len(mv), "moved_subvalues": mv[:48],
            "accept_set": acc[:48], "accept_set_size": len(acc),
            "outcomes": dict(outc),
            "sentinel_bad": sum(1 for r in A["subs"].values()
                                if r["sentinel_bad"]),
            "invalid_run": sum(1 for r in A["subs"].values()
                               if r["invalid_run"]),
            "poison_out_cases": sum(1 for r in A["subs"].values()
                                    if r["poison_out"]),
        }

    row = {"start": start, "width": width, "encodable_range": 1 << width,
           "target": "G17P", "evidence": ["EXP-0171"], "carriers": percar,
           "prior_label": prior.get("label"), "prior_target": prior.get("target"),
           "dimension": DIMENSIONS.get(fname)}
    if not percar:
        row["values_dispatched"] = 0
        row["distinct_bytes"] = 0
        if prior.get("label") in GRADE:
            row["label"] = "NO-ROW"
            row["note"] = ("not covered by any admitted carrier in this "
                           "experiment, and the field is ALREADY at %s in "
                           "validation.json -- no row is emitted, so nothing "
                           "here can downgrade it." % prior.get("label"))
        else:
            row["label"] = "untested"
            row["note"] = ("no ADMITTED carrier covered this field in both "
                           "gated runs (carrier gates F1/F2)")
        return row

    styles = sorted(set(v["carrier"] for v in percar.values()))
    probes = sorted(set(v["probe"] for v in percar.values()))
    any_moved = any(v["moved"] > 0 for v in percar.values())

    def ok_gate(c):
        cov = (c["distinct_bytes"] == c["encodable_range"] and
               c["subvalues_common"] == c["encodable_range"] and
               c["byte_sweep_distinct_encodings"] == 256) if not multi \
            else (c["wide_values_dispatched"] == c["wide_distinct_bytes"] and
                  all(pb["distinct_bytes"] == 256
                      for pb in c["per_byte_dense"].values()))
        run = c["agreement"] is not None and c["agreement"] >= 0.99
        mvt = c["moved"] > 0 and c["moved"] >= 2 * c["disagree"]
        hyg = (c["invalid_run"] == 0 and
               c["sentinel_bad"] <= max(1, 0.01 * max(1, c["values_dispatched"])))
        return cov, run, mvt, hyg

    best = None
    for cid, c in percar.items():
        cov, run, mvt, hyg = ok_gate(c)
        sc = (cov and run and mvt and hyg, c["moved"])
        if best is None or sc > best[0]:
            best = (sc, cid, cov, run, mvt, hyg)
    passed, cid, cov, run, mvt, hyg = best
    c = percar[cid]
    row["values_dispatched"] = c["values_dispatched"]
    row["distinct_bytes"] = c["distinct_bytes"]
    row["decisive_carrier"] = cid
    row["range"] = (("%d of %d sub-values, DENSE (%d distinct encodings of the "
                     "byte)" % (c["subvalues_common"], c["encodable_range"],
                                c["distinct_bytes"])) if not multi else
                    ("FIELD-SWEEP-PROTOCOL 3.3 set: %d of 2^%d values "
                     "(0,1,2,max-1,max + every power of two + 16 asymmetric "
                     "interior), plus every spanned byte swept DENSE 0..255"
                     % (c["subvalues_common"], width)))

    if passed[0]:
        row["label"] = "hardware-run"
        row["note"] = ("MOVED %d of %d on %s; cross-run agreement %.4f "
                       "(%d agree / %d disagree); %d admitted carriers "
                       "[%s | %s]; accept-set size %d%s; outcomes %s"
                       % (c["moved"], c["subvalues_common"], cid,
                          c["agreement"], c["agree"], c["disagree"],
                          len(percar), ",".join(styles), ",".join(probes),
                          c["accept_set_size"],
                          (" = %s" % c["accept_set"]
                           if c["accept_set_size"] <= 24 else ""),
                          json.dumps(c["outcomes"], sort_keys=True))
                       + (" CAVEAT (EXP-0166 6.2): a SINGLETON accept-set "
                          "establishes 'every other value breaks THIS carrier', "
                          "NOT an operand/sub-op map -- and for a sub-op "
                          "selector a non-ok outcome may simply mean 'a "
                          "different function', not 'invalid'."
                          if c["accept_set_size"] == 1 else "")
                       + ((" The accept-set is empty BY CONSTRUCTION: this "
                           "field spans %d bytes, its anchor composite value "
                           "0x%x is not a member of the FIELD-SWEEP-PROTOCOL "
                           "3.3 sample set, so no sampled value can reproduce "
                           "the baseline. The per-byte DENSE accept counts are "
                           "%s." % (b1 - b0 + 1, c["anchor_subvalue"],
                                    json.dumps(dict(
                                        (b, pb["accept_n"]) for b, pb
                                        in c["per_byte_dense"].items()),
                                        sort_keys=True)))
                          if multi and c["accept_set_size"] == 0 else ""))
    elif not any_moved:
        dim = DIMENSIONS.get(fname)
        strong = (len(styles) >= 2 and len(probes) >= 2 and dim is not None)
        weak = (len(styles) >= 2 and dim is not None)
        base = ("DENSE-INERT: 0 of %d sub-values moved, on %d admitted "
                "carriers [%s | %s], every one with its byte0 falsifier PROVEN "
                "non-ok and its liveness ladder PROVEN live (%s). %d distinct "
                "encodings, cross-run agreement %s. "
                % (c["subvalues_common"], len(percar), ",".join(styles),
                   ",".join(probes),
                   json.dumps(gates[cid]["F2_ladder_distinct_obs"],
                              sort_keys=True),
                   c["distinct_bytes"], c["agreement"]))
        if strong:
            row["label"] = "isolated-byte-diff"
            row["note"] = base + ("The carriers DO differ in the dimension "
                                  "this field would control (%s), across %d "
                                  "INDEPENDENT compiler-emitted anchors of "
                                  "this instruction (not one template), so an "
                                  "emitter may "
                                  "choose ANY value of this field. Labelled "
                                  "isolated-byte-diff, not hardware-run: the "
                                  "field was proven ACCEPTED at every "
                                  "encoding, never proven to SELECT anything."
                                  % (dim, len(probes)))
        elif weak:
            row["label"] = "single-template-inference"
            row["note"] = base + ("The carriers differ in the dimension this "
                                  "field would control (%s) but share ONE "
                                  "compiler-emitted anchor, so 'any value "
                                  "works' is still a statement about one "
                                  "template. NOT promoted: emitter grade "
                                  "asserts the implementer may CHOOSE the "
                                  "value, and 'emit what the compiler emitted' "
                                  "is a captured-template dependency. A "
                                  "successor needs a SECOND anchor of this "
                                  "instruction." % dim)
        else:
            row["label"] = "untested"
            row["note"] = base + ("NOT promotable: %s. Two carriers identical "
                                  "in the controlled dimension are one carrier "
                                  "(EXP-0164)."
                                  % ("no dimension is declared for this field"
                                     if dim is None
                                     else "fewer than 2 admitted carrier styles"))
    else:
        why = []
        if not cov:
            why.append("coverage (%d distinct encodings, %d of %d sub-values%s)"
                       % (c["distinct_bytes"], c["subvalues_common"],
                          c["encodable_range"],
                          "" if not multi else "; per-byte %s"
                          % json.dumps(c["per_byte_dense"], sort_keys=True)))
        if not run:
            why.append("cross-run agreement %s" % c["agreement"])
        if not mvt:
            why.append("movement %d < 2 x disagreement %d"
                       % (c["moved"], c["disagree"]))
        if not hyg:
            why.append("hygiene (%d invalid_run, %d sentinel_bad)"
                       % (c["invalid_run"], c["sentinel_bad"]))
        row["label"] = "corpus-correlation"
        row["note"] = ("MOVED (%d of %d on %s) but did not clear the gate: %s"
                       % (c["moved"], c["subvalues_common"], cid,
                          "; ".join(why)))
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
           "_no_row": dict((k, v.get("note")) for k, v in verdicts.items()
                           if v["label"] == "NO-ROW"),
           "verdicts": verdicts}
    # A NO-ROW key is deliberately ABSENT from the merge file: this experiment
    # did not cover it and it is already at emitter grade, so any row here
    # could only downgrade it.
    verdicts = dict((k, v) for k, v in verdicts.items()
                    if v["label"] != "NO-ROW")
    out["verdicts"] = verdicts
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
    print("xplant controls: %d of %d reproduced the transplanted function "
          "exactly, %d more with the operands swapped (the DEF-0154-5 check)"
          % (sum(1 for x in xp if x["matched_transplanted_function"]),
             len(xp),
             sum(1 for x in xp if x["matched_with_operands_swapped"]
                 and not x["matched_transplanted_function"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
