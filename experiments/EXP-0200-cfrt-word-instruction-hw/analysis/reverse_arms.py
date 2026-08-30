#!/usr/bin/env python3
"""EXP-0200 -- produce a REVERSED-CASE-ORDER copy of EXP-0187's frozen arms.

  python3 analysis/reverse_arms.py

GATE E (RE_EXPERIMENT_PROCESS_CORRECTIONS section 3): "Require two clean G17P
runs in reversed or shuffled case order." A confirmation run that repeats the
discovery run's case order reproduces any order-dependent artefact perfectly --
a thermal ramp, a neighbour's reset streak, a runner state leak -- and cross-run
agreement then measures the artefact rather than the hardware.

Target 1 is EXP-0187's contract honoured UNCHANGED, so its harness, its gate,
its arm set and its per-arm value lists may not be touched. Order is not part of
that contract: `t1/analysis/verdicts.py` indexes every case by (arm, value) and
never reads position. So this writes a SEPARATE file --
`harness/arms187_reversed.json`, in THIS experiment's harness directory, never
in `t1/` -- containing the SAME 25 arms with the SAME values, reversed in
dispatch order only. `t1/run.py --arms <that file>` then runs the identical
measurement in the opposite order.

The equality assertion below is the point of the script: it fails loudly if the
reversed file is anything other than a permutation of the frozen one.

CLEAN-ROOM: pure data reordering of our own frozen arm list.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent


def main():
    src = EXP / "t1" / "harness" / "arms187.json"
    doc = json.loads(src.read_text())
    arms = doc["arms"]
    rev = [dict(a, values=list(reversed(a["values"]))) for a in reversed(arms)]

    def sig(lst):
        return sorted((a["arm"], a["carrier"], a["instr"], a["field"],
                       a["off"], a["len"], a["start"], a["width"],
                       tuple(sorted(a["values"]))) for a in lst)

    if sig(arms) != sig(rev):
        sys.stderr.write("FATAL: reversed arms are not a permutation of the "
                         "frozen arms. Refusing to write.\n")
        return 2
    out = dict(doc)
    out["arms"] = rev
    out["order"] = ("REVERSED dispatch order of EXP-0187's frozen arms187.json. "
                    "Same arms, same values, same code, same gate -- position "
                    "only. Required by GATE E of "
                    "RE_EXPERIMENT_PROCESS_CORRECTIONS section 3.")
    out["source_arms"] = str(src.relative_to(EXP))
    p = EXP / "harness" / "arms187_reversed.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote %s: %d arms, %d cases, permutation check PASSED"
          % (p, len(rev), sum(len(a["values"]) for a in rev)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
