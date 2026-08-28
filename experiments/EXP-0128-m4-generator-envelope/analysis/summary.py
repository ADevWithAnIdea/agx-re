#!/usr/bin/env python3
"""EXP-0128 repeatable analysis: summarize the gated capture (no GPU,
reads only committed raw/ JSONL). Writes analysis/summary.json."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
RUN = "m4-20260828-run01"


def main():
    lines = (EXP / "raw" / RUN / "01_results.jsonl").read_text().splitlines()
    recs = [json.loads(l) for l in lines]
    by_group = Counter(r["group"] for r in recs)
    unexpected = [r["name"] for r in recs if r["expect_match"] and not r["match"]]
    surprises = [r["name"] for r in recs if not r["expect_match"] and r["match"]]
    status_counts = Counter(r["status"] for r in recs)
    out = {
        "run_id": RUN,
        "n_cases": len(recs),
        "by_group": dict(by_group),
        "status_counts": dict(status_counts),
        "match_true_count": sum(1 for r in recs if r["match"]),
        "match_false_count": sum(1 for r in recs if not r["match"]),
        "unexpected_mismatches": unexpected,
        "disclosed_surprises": surprises,
    }
    (HERE / "summary.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
