#!/usr/bin/env python3
"""EXP-0179 -> analysis/field_verdicts.json (FIELD-SWEEP-PROTOCOL section 5,
FLAT, one row per field).

  python3 analysis/verdicts.py --gate analysis/gate.json

Labels come from `docs/evidence-classification.md` and NOTHING ELSE. An
inconclusive sweep is `corpus-correlation` or `untested`; it is never rounded up.
`rt_ok` is not read.
"""
from __future__ import print_function

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# THE EIGHT LABELS, verbatim from docs/evidence-classification.md section 2.
# Nothing else may be written here; a dishonest label becomes someone else's
# silent-zero bug when the orchestrator merges these into validation.json.
LABELS = ("hardware-run", "isolated-byte-diff", "corpus-correlation",
          "tokenization-only", "single-template-inference",
          "api-accept-reject", "host-private", "untested")


# Hand-written semantics, each traceable to the raw. The mechanical gate decides
# PROMOTABILITY; these say WHAT the field does. Nothing here is asserted that
# `raw/g17p_20260830_run03|04/sweep.jsonl` does not show.
SEMANTICS = {
 "call.b3": ("BRANCH-TAKEN SELECTOR. The live field is bits 5:2 (a 4-bit code); bits 1:0 "
             "and 7:6 are INERT (outcome constant within every bits5:2 code, 0 violations "
             "over 256 values x 2 carriers x 2 runs). Codes that TAKE the call: "
             "{6, 8, 9, 10, 11, 12, 13, 15}. Codes that do NOT: {0,1,2,3,4,5,7,14} -- and "
             "the failure is always a clean FALL-THROUGH (callee never ran, breadcrumb "
             "still 0xDEADBEEF, control continued at the next instruction and returned), "
             "NEVER a fault. The compiler's 0x1a is code 6. This is the shape `if_push`'s "
             "own descriptor calls scope_kind, on the instruction that shares its leader."),
 "call.b5": ("TWO LIVE BITS, six inert. bit1 (0x02) set -> CMDBUF_ERROR fault, 128/128 "
             "values. bit2 (0x04) set with bit1 clear -> the call is NOT taken. bits 0, 3, "
             "4, 5, 6, 7 are INERT (perfect 16/16 and 32/32 splits throughout). "
             "LEGAL RANGE: (b5 & 0x06) == 0, i.e. 64 of 256 encodable values, and the rule "
             "holds for all 256 values on both carriers in both runs."),
 "call.b6": ("INERT over the full 0..255 range. The complete observation -- all 16 "
             "registers, the POST sentinel and the callee breadcrumb -- is BYTE-IDENTICAL "
             "for every one of the 256 values on both carriers in both runs (1 distinct "
             "observation per carrier). The corpus value 0x56 is not load-bearing. An "
             "emitter may write any value."),
 "call.tail": ("INERT over the full 0..255 range, same evidence shape as call.b6: one "
               "distinct full observation per carrier across 256 values x 2 runs."),
 "ret.scoreboard": ("INERT in this carrier over the full 0..255 range (one distinct full "
                    "observation per carrier across 256 values x 2 runs). THAT IS NOT A "
                    "PROMOTION -- see the note."),
 "ret.linkmode": ("0x02 (leaf) and 0x12 (non-leaf) both return correctly from a generated "
                  "leaf callee; 0x04 and 0x05 (CF merge) do NOT return -- the callee ran "
                  "and control never came back. Consistent with EXP-0035 and EXP-0156. "
                  "Only 4 values were dispatched here, as a CONTROL; this experiment does "
                  "not re-label the field."),
}
# The carrier-dimension clause, applied by hand where the mechanical gate cannot.
OVERRIDE = {
 "ret.scoreboard": ("corpus-correlation",
  "DECLINED, as pre-registered (PRE_REGISTRATION H6 / section 9). The mechanical gate "
  "reports `promotable` because agreement is 1.0 and there are no disagreements -- but "
  "FIELD-SWEEP-PROTOCOL's own clause says a NEVER-MOVING field is promotable only if the "
  "carriers differ IN THE DIMENSION THE FIELD CONTROLS. `ret.scoreboard` is an "
  "execution/scoreboard WAIT mask; the dimension it controls is memory/execution ORDERING, "
  "and neither carrier differs in that dimension -- both return from a leaf callee with no "
  "outstanding asynchronous operation to wait on. Zero movement here therefore means 'this "
  "carrier cannot ask the question', not 'the field is inert'. Three prior experiments "
  "declined this family and EXP-0172 declined it in advance for the adjacent reason. Arm O "
  "is the construction that could settle it and had not yet run when this was written."),
 "ret.linkmode": ("untested",
  "NOT SWEPT HERE. Four values dispatched as a cross-experiment consistency control only. "
  "EXP-0156's dense 0..255 G17P sweep stands; this experiment does not re-label it."),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default=str(HERE / "gate.json"))
    ap.add_argument("--out", default=str(HERE / "field_verdicts.json"))
    ap.add_argument("--target", default="G17P")
    args = ap.parse_args()

    g = json.loads(Path(args.gate).read_text())
    out = {}
    for fk, d in sorted(g["fields"].items()):
        cars = d["carriers"]
        vd = max((c["values_dispatched"] for c in cars.values()), default=0)
        db = max((c["distinct_bytes"] for c in cars.values()), default=0)
        mv = max((c["movement"] for c in cars.values()), default=0)
        agree = min((c["agreement"] for c in cars.values()), default=0.0)
        label = "hardware-run" if d["gate_pass"] else "corpus-correlation"
        if vd == 0:
            label = "untested"
        if fk in OVERRIDE:
            label, note = OVERRIDE[fk]
        else:
            note = ""
        assert label in LABELS
        out[fk] = {
            "label": label,
            "range": "0..255 dense (all 256 values), %d carriers" % d["n_carriers"],
            "target": args.target,
            "evidence": ["EXP-0179"],
            "values_dispatched": vd,
            "distinct_bytes": db,
            "encodable_range": 256,
            "movement": mv,
            "min_cross_run_agreement": agree,
            "gate_pass": d["gate_pass"],
            "semantics": SEMANTICS.get(fk, ""),
            "note": note,
            "carriers": {c: {"values_dispatched": v["values_dispatched"],
                             "distinct_bytes": v["distinct_bytes"],
                             "movement": v["movement"],
                             "agreement": v["agreement"],
                             "disagreements": v["disagreements"],
                             "outcomes": v["outcomes"],
                             "hang_values": v["hang_values"]}
                         for c, v in cars.items()},
        }
    Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
