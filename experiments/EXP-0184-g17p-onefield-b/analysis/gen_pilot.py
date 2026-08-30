#!/usr/bin/env python3
"""EXP-0184 PILOT arm generation -- CALIBRATION ONLY. NO VERDICT MAY CITE IT.

Added AFTER the contract was frozen; recorded in PRE_REGISTRATION.md section 10
(amendment log) before it was run. It exists to answer three questions that
must be settled before a gated run id is spent, and that the census cannot
answer because they need the device:

 1. **Which of the 14 `rt_query_traverse` occurrences are load-bearing?**
    EXP-M4-14 found only ONE of 18 rtq ops in its kernel was on the committed
    path -- "the other 17 rtq ops are inert on `sel`". Sweeping `dst` at four
    arbitrary occurrences would very likely sweep four inert ones and report a
    confident, meaningless INERT. The probe is the `opB` control at every
    occurrence: opB is `hardware-run` on A18 and *known* to change the answer at
    a load-bearing occurrence.
 2. **Hang density on the control-flow sweep**, before committing a gated run
    with no abort path.
 3. **Per-case wall-clock cost**, to size the gated runs.

Output: `harness/arms_pilot.json`, dispatched into `raw/prefreeze/`.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import locate184 as L        # noqa: E402

OPB_PROBE = [0x00, 0x0a, 0x1a, 0x40, 0x48]      # EXP-M4-14: 0x48 correct, others skip/hang


def main():
    census = json.loads((EXP / "raw" / "prefreeze" / "census.json").read_text())
    arms = []

    # 1. RT reachability + a first dst pass, at EVERY occurrence of one carrier.
    rec = census["rq_mdist"]
    ds, dw = L.field_span("rt_query_traverse", "dst")
    for i, h in enumerate(rec["occurrences"]):
        arms.append({"group": "rq", "carrier": "rq_mdist",
                     "instr": "rt_query_traverse", "field": "opB",
                     "arm": "P/rq_mdist#%d/opB" % i, "occ": i,
                     "off": h["off"], "len": h["len"], "start": 56, "width": 8,
                     "values": OPB_PROBE, "role": "control",
                     "baseline_field": h["baseline_field"],
                     "note": "reachability probe"})
        arms.append({"group": "rq", "carrier": "rq_mdist",
                     "instr": "rt_query_traverse", "field": "dst",
                     "arm": "P/rq_mdist#%d/dst" % i, "occ": i,
                     "off": h["off"], "len": h["len"], "start": ds, "width": dw,
                     "values": list(range(16)), "role": "target",
                     "baseline_field": h["baseline_field"], "note": "pilot"})

    # 2. Control-flow hang density: outermost and innermost push, coarse stride.
    for carrier, occs in (("cf_if3", [0, 6]), ("cf_if2", [0])):
        rc = census[carrier]
        ss, sw = L.field_span("if_push", "scope")
        for i in occs:
            h = rc["occurrences"][i]
            arms.append({"group": "cf", "carrier": carrier, "instr": "if_push",
                         "field": "scope", "arm": "P/%s#%d/scope" % (carrier, i),
                         "occ": i, "off": h["off"], "len": h["len"],
                         "start": ss, "width": sw,
                         "values": list(range(0, 256, 16)) + [0x54, 0x56],
                         "role": "target", "baseline_field": h["baseline_field"],
                         "note": "pilot: hang density"})
            arms.append({"group": "cf", "carrier": carrier, "instr": "if_push",
                         "field": "scope_kind",
                         "arm": "P/%s#%d/scope_kind" % (carrier, i), "occ": i,
                         "off": h["off"], "len": h["len"], "start": 24, "width": 8,
                         "values": [0x00, 0x01, 0x05, 0x1a, 0x21, 0x25, 0xff],
                         "role": "control", "baseline_field": h["baseline_field"],
                         "note": "pilot: detection power"})

    # 3. Convert + copysign: coarse target pass and the detection-power control.
    rc = census["cvt_s32"]
    h = rc["occurrences"][0]
    bs, bw = L.field_span("cvt_f2i", "b9")
    arms.append({"group": "cvt", "carrier": "cvt_s32", "instr": "cvt_f2i",
                 "field": "b9", "arm": "P/cvt_s32#0/b9", "occ": 0,
                 "off": h["off"], "len": h["len"], "start": bs, "width": bw,
                 "values": list(range(0, 256, 32)), "role": "target",
                 "baseline_field": h["baseline_field"], "note": "pilot"})
    arms.append({"group": "cvt", "carrier": "cvt_s32", "instr": "cvt_f2i",
                 "field": "dst", "arm": "P/cvt_s32#0/dst", "occ": 0,
                 "off": h["off"], "len": h["len"], "start": 24, "width": 8,
                 "values": list(range(0, 256, 16)), "role": "control",
                 "baseline_field": h["baseline_field"],
                 "note": "pilot: detection power (EXP-0168 G17P hardware-run)"})

    rc = census["cs_load"]
    h = rc["occurrences"][0]
    os_, ow = L.field_span("copysign", "operands")
    arms.append({"group": "cs", "carrier": "cs_load", "instr": "copysign",
                 "field": "operands", "arm": "P/cs_load#0/operands", "occ": 0,
                 "off": h["off"], "len": h["len"], "start": os_, "width": ow,
                 "values": list(range(0, 256, 32)), "role": "target",
                 "baseline_field": h["baseline_field"], "note": "pilot"})
    arms.append({"group": "cs", "carrier": "cs_load", "instr": "copysign",
                 "field": "_b1_match", "arm": "P/cs_load#0/_b1_match", "occ": 0,
                 "off": h["off"], "len": h["len"], "start": 8, "width": 8,
                 "values": list(range(0, 256, 16)), "role": "control",
                 "baseline_field": h["baseline_field"],
                 "note": "pilot: detection power (EXP-0138 M4 measured LIVE)"})

    p = EXP / "harness" / "arms_pilot.json"
    p.write_text(json.dumps({"pilot": True, "arms": arms}, indent=1, sort_keys=True))
    print("pilot arms=%d cases=%d -> %s"
          % (len(arms), sum(len(a["values"]) for a in arms), p))


if __name__ == "__main__":
    main()
