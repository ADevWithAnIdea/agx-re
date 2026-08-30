#!/usr/bin/env python3
"""EXP-0156 fault re-validation (FIELD-SWEEP-PROTOCOL §7A).

EXP-0153 showed that majority-of-3 plus cross-run agreement is NOT sufficient for a
`fault`/`hang` verdict: under sustained sibling load, contamination can look
reproducible AND survive an independent second run. Only isolation settles it.

This script finds every case that the two gated runs of a pair BOTH recorded as
`fault` or `hang`, and writes their frozen case indices to a file so `run.py
--cases <file> --replicates 5` can re-dispatch exactly those, 5x each, inside a
held GPU lease.

Usage:
  python3 harness/revalidate.py list RUN_A RUN_B > work/reval_<pair>.idx
  # then, on the neo, under the lease:
  bash harness/drive.sh lease <new_run_id> "" --cases work/reval_<pair>.idx --replicates 5
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent


def load(run):
    p = EXP / "raw" / run / "sweep.jsonl"
    return [json.loads(l) for l in p.open()] if p.exists() else []


def main():
    _, ra, rb = sys.argv[1:4] if sys.argv[1] == "list" else (None, None, None)
    A = {r["i"]: r for r in load(ra) if r.get("kind") == "case"}
    B = {r["i"]: r for r in load(rb) if r.get("kind") == "case"}
    out = []
    for i, r in sorted(A.items()):
        s = B.get(i)
        if s is None:
            continue
        if r["outcome"] in ("fault", "hang") and s["outcome"] in ("fault", "hang"):
            out.append(i)
    sys.stderr.write("%s|%s: %d fault/hang cases to re-validate\n" % (ra, rb, len(out)))
    print("\n".join(str(i) for i in out))


if __name__ == "__main__":
    main()
