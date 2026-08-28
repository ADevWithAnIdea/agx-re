#!/usr/bin/env python3
"""EXP-0090 post-capture analysis: per-family (item) verdict summary from
raw/<run>/01_results.jsonl. Read-only against raw/; writes analysis.json."""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as RUN  # noqa: E402


def load(run_id):
    p = HERE / "raw" / run_id / "01_results.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()]


def summarize(rows):
    by_item = {}
    for r in rows:
        by_item.setdefault(r["item"], []).append(r)
    out = {}
    for item, rs in by_item.items():
        out[item] = {"n": len(rs), "matched": sum(1 for r in rs if r["match"]),
                     "mismatched": [r["name"] for r in rs if not r["match"]],
                     "cases": [r["name"] for r in rs]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    r1 = load(RUN.RUNS[0])
    r2 = load(RUN.RUNS[1])
    same = r1 == r2
    result = {"schema": 1, "runs": list(RUN.RUNS), "cross_run_identical": same,
              "run01_summary": summarize(r1), "run02_summary": summarize(r2)}
    print(json.dumps(result, indent=2, sort_keys=True))
    if a.write:
        (HERE / "analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
