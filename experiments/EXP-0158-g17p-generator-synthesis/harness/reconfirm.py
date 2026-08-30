#!/usr/bin/env python3
"""EXP-0158 §7A re-confirmation pass.

`FIELD-SWEEP-PROTOCOL.md` §7A (added 2026-08-29 after EXP-0153) is explicit:
majority-of-3 is NOT sufficient for a `fault`/`hang` verdict.  Under sustained
sibling load contamination can look reproducible *and* survive an independent
second run.  Any case this experiment still reports as `fault`, `hang`,
`victim` or `invalid_run` after both gated runs is re-run REPS more times here,
and its verdict is whatever the majority of those independent observations say.

This is a separate, named pass over a named case list -- it never edits a gated
`raw/` tree.  Its output is its own append-only JSONL.

Usage: reconfirm.py --indices 12,34,56 --reps 5 --out FILE --bin-dir D --repo R
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(HERE))
import casematrix as CM   # noqa: E402
import case_exec as CE    # noqa: E402  (the same executor the gated runs use)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indices", required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args()
    cs = CM.build_cases()
    f = open(a.out, "a")
    for idx in [int(x) for x in a.indices.split(",") if x.strip()]:
        c = cs[idx]
        obs = []
        for rep in range(a.reps):
            args = argparse.Namespace(run_dir="%s/rep%d" % (a.run_dir, rep),
                                      bin_dir=a.bin_dir, repo=a.repo)
            rec, ms = CE.run_one(c, args)
            obs.append({"rep": rep, "outcome": rec["outcome"], "status": rec["status"],
                        "fault_class": rec["fault_class"], "match": rec["match"],
                        "observed": rec["observed"], "sentinel": rec["sentinel"],
                        "victim_retries": rec["victim_retries"]})
        tally = {}
        for o in obs:
            tally[o["outcome"]] = tally.get(o["outcome"], 0) + 1
        maj = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        row = {"i": idx, "name": c["name"], "group": c["group"],
               "expect_match": c["expect_match"], "reps": a.reps,
               "observations": obs, "tally": tally,
               "majority_outcome": maj[0], "majority_count": maj[1],
               "majority_is_ok": maj[0] == "ok"}
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        print("%-40s %-12s %s" % (c["name"], maj[0], tally), flush=True)
    f.close()


if __name__ == "__main__":
    main()
