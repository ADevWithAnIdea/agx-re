#!/usr/bin/env python3
"""Re-derive `tools/agx-isa/wave_audit.py`'s cross-run line, and show why it is
wrong for THIS raw. Reproduces `analysis/wave_audit_recheck.txt`.

    python3 analysis/wave_audit_recheck.py

`wave_audit.py` is the gate this experiment's verdicts get judged by on arrival,
and its output is committed verbatim as `analysis/wave_audit.txt`. Its per-field
cross-run agreement line reads 0-25 % here, which would look like a catastrophic
stability failure. It is not one, and BOTH causes are in the checker, not the
hardware:

1. **It pools by `value` across every arm of a field.** `runs[run][value] =
   observed` collapses the arms, so with 6 arms per value the last one written
   wins -- and run04 iterates in REVERSED case order by design (Gate E), so a
   different arm wins in each run. It is comparing different arms.

2. **It compares the whole `observed` dict, which contains `gputime_ns`.** That
   is a nondeterministic hardware timing measurement. Two byte-identical
   dispatches of the same program differ in it essentially always.

Keyed by `(arm, value)` and with `gputime_ns` excluded, this experiment's
confirmation pair has **ZERO disagreements on every field**, over 10156 shared
cases in opposite case order. The table below is printed both ways so the
difference is attributable rather than asserted.

This is reported, not fixed: `tools/agx-isa/` is not this experiment's to edit,
and a checker that silently reports near-total disagreement for any experiment
whose raw carries a timing field inside `observed` is worth the orchestrator's
attention on its own.

CLEAN-ROOM: pure re-analysis of our own committed raw.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
RUNS = ("g17p_20260830_run03", "g17p_20260830_run04")
FIELDS = [("shift_amt_move", "src_flag"), ("b_alu10_lo7", "src_flag"),
          ("irotate", "operands"), ("ibitcount", "cache"), ("ibitcount", "dst"),
          ("iunary", "b1"), ("iunary", "opsel"), ("cvt_f2i", "b9"),
          ("cvt_f2i", "signflag")]


def load(r):
    p = EXP / "raw" / r / "sweep.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def pool(recs, mn, fld, by_arm, drop):
    d = {}
    for r in recs:
        if r.get("instr") != mn or r.get("field") != fld or r.get("role") == "baseline":
            continue
        o = dict(r.get("observed") or {})
        for k in drop:
            o.pop(k, None)
        d[(r["arm"], r["value"]) if by_arm else r["value"]] = json.dumps(o, sort_keys=True)
    return d


def main():
    A, B = load(RUNS[0]), load(RUNS[1])
    print("run03 (forward) vs run04 (reverse case order)\n")
    print("%-24s %-34s %-34s %s" % ("field", "wave_audit's key (value, whole obs)",
                                    "keyed by (arm,value), whole obs",
                                    "(arm,value), gputime_ns EXCLUDED"))
    for mn, fld in FIELDS:
        row = []
        for by_arm, drop in ((False, []), (True, []), (True, ["gputime_ns"])):
            a, b = pool(A, mn, fld, by_arm, drop), pool(B, mn, fld, by_arm, drop)
            com = set(a) & set(b)
            dis = sum(1 for v in com if a[v] != b[v])
            row.append("%d/%d disagree" % (dis, len(com)))
        print("%-24s %-34s %-34s %s" % (mn + "." + fld, row[0], row[1], row[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
