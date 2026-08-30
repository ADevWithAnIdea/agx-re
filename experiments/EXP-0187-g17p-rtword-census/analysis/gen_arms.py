#!/usr/bin/env python3
"""EXP-0187 arm generation -- the SELECTION RULE, frozen in PRE_REGISTRATION.md 7.4.

Reads `raw/prefreeze/census.json` and writes `harness/arms187.json`, which is
then hashed into CAPTURE_CONTRACT.json and never edited again.

THE RULE (frozen; a reviewer can check every arm against it):

 1. A carrier that does not EMIT `n4_rt_word` is DROPPED, and the drop is
    recorded with its occurrence count. "N carriers tried, 0 occurrences" is a
    bounded negative, not a failure.
 2. Only PARCEL-ALIGNED occurrences are swept. A signature hit at an odd offset
    is recorded in the census as evidence the descriptor signature is ambiguous
    but is never dispatched as if it were an instruction.
 3. TARGET arms: EVERY aligned occurrence in EVERY surviving carrier is swept
    DENSE over all 256 values -- there is no per-carrier occurrence cap.
    EXP-0184 needed one only because it could afford 14 of 56 rtq occurrences,
    and its own conclusion was that freezing blind on a subset would very likely
    have hit unreached occurrences and published a confident meaningless INERT
    verdict. 32 aligned occurrences x 256 values is affordable here, so the
    subset problem is removed rather than mitigated.
 4. DETECTION POWER. `n4_rt_word` has exactly ONE modelled field: byte0, byte+2
    and byte+3 are fixed match constants, so **no same-instruction control
    exists**, and sweeping a match byte is the discredited shape -- EXP-0138's
    `copysign` control was a byte+1 sweep where byte+1 is a match constant, so it
    "fired" by encoding a DIFFERENT opcode (the sixth shape of a check that
    cannot fail). Two weaker controls are generated instead, and every verdict
    states which one backed it:
      (a) SAME PROGRAM POINT -- where the token at off+4 is an op with a
          known-live field (`if_push.scope_kind`, hardware-run, EXP-0140), sweep
          that field at off+4. This proves the program point is executed and
          observable. Available at 3 of 32 occurrences.
      (b) CARRIER LEVEL -- `rt_query_traverse.opB` (byte+7) at every aligned
          `rt_query_traverse` occurrence in the same carrier. HW-VALIDATED
          load-bearing on A18 (EXP-M4-14: {0x42,0x48,0xc8} give the correct near
          hit, other values skip it) and re-measured on G17P by EXP-0184. This
          proves the CARRIER has an observable ray-query path; it does not prove
          this occurrence is executed.
    The four opB values EXP-M4-14 measured as HANGING the traversal
    (0x02,0x06,0x07,0x40) are excluded from the control set: a control only has
    to fire, and deliberately hanging the device to make it fire is not worth a
    device reset for every arm.
 5. Every TARGET arm dispatches the field's FULL encodable range (width 8 ->
    all 256 values, dense). Controls are sampled, because a control only has to
    fire once.

Derived from EXP-0184 analysis/gen_arms.py (our own code, cited).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import locate187 as L        # noqa: E402

MNEMONIC = "n4_rt_word"
FIELD = "dst"
# EXP-M4-14 (A18) behaviour classes, minus the four HANG values.
OPB_CONTROL_VALUES = [0x00, 0x0f, 0x1a, 0x20, 0x42, 0x48, 0x60, 0xc8, 0xff]
SCOPEKIND_CONTROL_VALUES = [0, 1, 2, 4, 5, 8, 16, 26, 32, 33, 37, 64, 128, 160,
                            224, 255]
MATCH_PROBE_VALUES = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x7f,
                      0x80, 0x81, 0xa0, 0xc0, 0xe0, 0xfe, 0xff]


def main():
    census = json.loads((EXP / "raw" / "prefreeze" / "census.json").read_text())
    start, width = L.field_span(MNEMONIC, FIELD)
    arms, dropped = [], []
    for name, rec in sorted(census.items()):
        if rec.get("error"):
            dropped.append({"carrier": name, "reason": "compile_fail",
                            "detail": rec["error"][:200]})
            continue
        occ = [h for h in rec.get("occurrences", []) if h["parcel_aligned"]]
        if not occ:
            dropped.append({"carrier": name, "reason": "no_occurrence",
                            "n_signature_hits": rec.get("n_occ", 0)})
            continue
        for i, h in enumerate(sorted(occ, key=lambda x: x["off"])):
            arms.append({
                "group": "rq", "carrier": name, "instr": MNEMONIC, "field": FIELD,
                "arm": "%s#%d/%s.%s" % (name, i, MNEMONIC, FIELD),
                "occ": i, "off": h["off"], "len": h["len"],
                "start": start, "width": width,
                "values": list(range(1 << width)),
                "baseline_field": h["baseline_field"],
                "baseline_bytes": h["bytes"], "role": "target",
                "succ_mnemonic": (h.get("succ_token") or {}).get("mnemonic"),
                "note": "target field, dense full range",
            })
            # WHOLE-WORD LIVENESS PROBES. `n4_rt_word` is `04 <dst> 20 80`:
            # byte0/+2/+3 are fixed match constants, so changing them changes
            # which instruction the bytes ARE. That makes them USELESS as field
            # controls (EXP-0138's discredited shape) but exactly right as a
            # LIVENESS probe of the occurrence: if no value of byte+2 or byte+3
            # changes the output either, the four bytes at this offset have no
            # observable effect at all -- which is EXP-0172's DEF-0172-4 finding
            # for the sibling `n4_cf_word`, and it distinguishes "the field is
            # inert" from "this occurrence is never executed". They are routed to
            # `match_byte_probes` in verdicts.py and can NEVER carry a field
            # label, however cleanly they move.
            for pname, pstart in (("_b2_match", 16), ("_b3_match", 24)):
                arms.append({
                    "group": "rq", "carrier": name, "instr": MNEMONIC,
                    "field": pname,
                    "arm": "%s#%d/%s.%s" % (name, i, MNEMONIC, pname),
                    "occ": i, "off": h["off"], "len": h["len"],
                    "start": pstart, "width": 8,
                    "values": MATCH_PROBE_VALUES,
                    "baseline_field": h["baseline_field"],
                    "baseline_bytes": h["bytes"], "role": "probe_word_liveness",
                    "note": "fixed match constant in the pinned db; swept as a "
                            "WHOLE-WORD liveness probe, never as a field",
                })
            ctl = h.get("succ_control")
            if ctl:
                cf, cs_, cw = ctl
                arms.append({
                    "group": "rq", "carrier": name,
                    "instr": (h.get("succ_token") or {}).get("mnemonic"),
                    "field": cf,
                    "arm": "%s#%d/succ.%s" % (name, i, cf),
                    "occ": i, "off": h["off"] + h["len"],
                    "len": (h.get("succ_token") or {}).get("length") or 4,
                    "start": cs_, "width": cw,
                    "values": SCOPEKIND_CONTROL_VALUES,
                    "baseline_field": h["baseline_field"],
                    "baseline_bytes": h["bytes"],
                    "role": "control_same_program_point",
                    "note": "known-live field of the op at off+4; proves this "
                            "program point is executed and observable",
                })
        for j, h in enumerate(sorted(rec.get("rtq_occurrences", []),
                                     key=lambda x: x["off"])):
            arms.append({
                "group": "rq", "carrier": name, "instr": "rt_query_traverse",
                "field": "opB",
                "arm": "%s/rtq%d.opB" % (name, j),
                "occ": "rtq%d" % j, "off": h["off"], "len": h["len"],
                "start": 56, "width": 8, "values": OPB_CONTROL_VALUES,
                "baseline_field": None, "baseline_bytes": h["bytes"],
                "role": "control_carrier",
                "note": "HW-VALIDATED load-bearing on A18 (EXP-M4-14); proves "
                        "the CARRIER has an observable ray-query path, NOT that "
                        "any given n4_rt_word occurrence is executed",
            })
    doc = {"generated_from": "raw/prefreeze/census.json",
           "rule": "analysis/gen_arms.py docstring (frozen in "
                   "PRE_REGISTRATION.md section 7.4)",
           "dropped_carriers": dropped, "arms": arms}
    p = EXP / "harness" / "arms187.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True))
    n = sum(len(a["values"]) for a in arms)
    nt = sum(1 for a in arms if a["role"] == "target")
    print("arms=%d (target=%d) cases=%d dropped=%d -> %s"
          % (len(arms), nt, n, len(dropped), p))
    for d in dropped:
        print("  DROPPED %s: %s" % (d["carrier"], d["reason"]))


if __name__ == "__main__":
    main()
