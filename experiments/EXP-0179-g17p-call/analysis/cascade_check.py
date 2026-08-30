#!/usr/bin/env python3
"""Is a non-OK outcome a HARDWARE PROPERTY or a RUNNER ARTEFACT?

  python3 analysis/cascade_check.py --runs <forward_run> <reverse_run> [--arm N]

THE TEST (proposed by EXP-0178, run here because arm N is the one arm whose
EXPECTED result is a hang, which is exactly where an artefact and the real thing
are hardest to tell apart):

  A genuine hardware property maps IDENTICALLY IN BOTH DIRECTIONS -- the same
  VALUES fail whichever order they are dispatched in.
  A DEF-0178-1 cascade tracks DISPATCH ORDER -- the failures begin at some index
  and continue, regardless of which values happen to sit there.

So we compute both agreements over the same data and compare them:

  agreement_by_value    -- fraction of CASE KEYS (arm, carrier, field, value)
                           whose outcome matches across the forward and reverse
                           passes. High => the outcome is a property of the VALUE.
  agreement_by_position -- fraction of DISPATCH INDICES whose outcome matches.
                           Under a reversed order the case at index i differs
                           between runs, so this is high only if the outcome is a
                           property of WHERE in the run it was dispatched.

Plus the cascade's own signature: a DEF-0178-1 tail is a CONTIGUOUS SUFFIX of
dispatch indices (everything after the first watchdog timeout is poisoned). We
test that directly, and we report the runner's own counters -- `restarts`,
`malformed_total`, `discarded_lines` -- which a cascade cannot leave at zero.

VERDICT is only stated when the two agreements are far enough apart to be
distinguishable; otherwise it says so.
"""
from __future__ import print_function

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
MARGIN = 0.20        # how far apart the two agreements must be to call it


def load(run):
    p = EXP / "raw" / run / "sweep.jsonl"
    out = []
    for ln in p.read_text().splitlines():
        if ln.strip():
            r = json.loads(ln)
            if not r.get("skipped"):
                out.append(r)
    return out


def key(r):
    """The identity of a CASE.

    `note` is part of the key. Arm O dispatches 12 filler lengths per
    (carrier, scoreboard) triple, so a key without it COLLIDES: the dict keeps
    only the last record per key, which is filler=24 in the forward pass and
    filler=0 in the reverse one. That produced a spurious
    `agreement_by_value = 0.0` on the first run of this script -- a defect in the
    ANALYSIS, not a hardware result, and exactly the kind of thing that would
    have read as a cascade if it had not been checked."""
    return (r.get("arm"), r.get("carrier"), r.get("instr"), r.get("field"),
            str(r.get("value")), r.get("note") or "")


def contiguous_suffix(idxs, n):
    """True iff `idxs` is exactly {k, k+1, ..., n-1} for some k -- the shape a
    DEF-0178-1 cascade leaves behind."""
    if not idxs:
        return False
    s = sorted(idxs)
    return s == list(range(s[0], n)) and s[-1] == n - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs=2, required=True,
                    metavar=("FORWARD", "REVERSE"))
    ap.add_argument("--arm", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    fwd, rev = (load(r) for r in args.runs)
    if args.arm:
        fwd = [r for r in fwd if r["arm"] == args.arm]
        rev = [r for r in rev if r["arm"] == args.arm]

    fk = {key(r): r for r in fwd}
    rk = {key(r): r for r in rev}
    common = sorted(set(fk) & set(rk))

    by_value = sum(1 for k in common
                   if fk[k]["outcome"] == rk[k]["outcome"])
    n = min(len(fwd), len(rev))
    by_position = sum(1 for i in range(n)
                      if fwd[i]["outcome"] == rev[i]["outcome"])

    av = by_value / float(len(common)) if common else 0.0
    ap_ = by_position / float(n) if n else 0.0

    nonok_f = [i for i, r in enumerate(fwd) if r["outcome"] != "ok"]
    nonok_r = [i for i, r in enumerate(rev) if r["outcome"] != "ok"]
    nonok_keys_f = {k for k in common if fk[k]["outcome"] != "ok"}
    nonok_keys_r = {k for k in common if rk[k]["outcome"] != "ok"}

    counters = {}
    for label, rs in (("forward", fwd), ("reverse", rev)):
        counters[label] = {
            "restarts_max": max([r.get("restarts") or 0 for r in rs] or [0]),
            "malformed_total_max": max([r.get("malformed_total") or 0 for r in rs] or [0]),
            "discarded_lines_max": max([r.get("discarded_lines") or 0 for r in rs] or [0]),
            "n_malformed_validity": sum(1 for r in rs
                                        if r.get("validity") == "invalid_malformed"),
        }

    if av - ap_ > MARGIN:
        verdict = ("VALUE-CLUSTERED -- a HARDWARE property. The same values give the "
                   "same outcome whichever order they are dispatched in.")
    elif ap_ - av > MARGIN:
        verdict = ("POSITION-CLUSTERED -- an ARTEFACT TAIL. The outcome tracks where "
                   "in the run the case was dispatched, not which value it carried.")
    elif not nonok_keys_f and not nonok_keys_r:
        verdict = "NOT APPLICABLE -- there are no non-OK cases to attribute."
    else:
        verdict = ("INDISTINGUISHABLE at this margin (%.2f) -- do not claim either. "
                   "This happens when almost every case shares one outcome, so both "
                   "agreements are trivially high." % MARGIN)

    rep = {
        "runs": args.runs, "arm": args.arm or "ALL",
        "n_common_cases": len(common), "n_positions": n,
        "agreement_by_value": round(av, 6),
        "agreement_by_position": round(ap_, 6),
        "margin_required": MARGIN,
        "nonok_case_keys_forward": len(nonok_keys_f),
        "nonok_case_keys_reverse": len(nonok_keys_r),
        "nonok_keys_identical_across_runs": sorted(nonok_keys_f) == sorted(nonok_keys_r),
        "nonok_positions_forward": nonok_f[:64],
        "nonok_positions_reverse": nonok_r[:64],
        "cascade_signature_contiguous_suffix": {
            "forward": contiguous_suffix(nonok_f, len(fwd)),
            "reverse": contiguous_suffix(nonok_r, len(rev)),
        },
        "runner_counters": counters,
        "VERDICT": verdict,
    }
    out = args.out or str(HERE / ("cascade_%s.json" % (args.arm or "all")))
    Path(out).write_text(json.dumps(rep, indent=1, sort_keys=True))
    print(json.dumps(rep, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
