#!/usr/bin/env python3
"""EXP-0112 results summary: pass rate by family, failure taxonomy, status
breakdown. Reads raw/m4-20260828-run01/01_results.jsonl (byte-identical to
run02, verified by verify.py --captured) and writes analysis/summary.json.
No GPU access; pure post-hoc analysis of already-captured evidence."""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def main():
    lines = (EXP / "raw" / "m4-20260828-run01" / "01_results.jsonl").read_text().splitlines()
    recs = [json.loads(l) for l in lines]

    by_group = defaultdict(list)
    for r in recs:
        by_group[r["group"]].append(r)

    summary = {"total_cases": len(recs), "groups": {}}
    for g, rs in sorted(by_group.items()):
        n = len(rs)
        n_expect_true = sum(1 for r in rs if r["expect_match"])
        n_expect_false = n - n_expect_true
        n_expect_true_pass = sum(1 for r in rs if r["expect_match"] and r["match"])
        n_expect_false_asexpected = sum(1 for r in rs if not r["expect_match"] and not r["match"])
        n_unexpected = sum(1 for r in rs if r["expect_match"] != r["match"])
        status_counts = Counter(r["status"] for r in rs)
        summary["groups"][g] = {
            "n_cases": n,
            "n_expect_match_true": n_expect_true,
            "n_expect_match_true_and_passed": n_expect_true_pass,
            "pass_rate_of_expect_true": (n_expect_true_pass / n_expect_true) if n_expect_true else None,
            "n_expect_match_false": n_expect_false,
            "n_expect_match_false_as_predicted": n_expect_false_asexpected,
            "n_unexpected_deviations": n_unexpected,
            "status_counts": dict(status_counts),
        }

    n_true = sum(1 for r in recs if r["expect_match"])
    n_true_pass = sum(1 for r in recs if r["expect_match"] and r["match"])
    summary["overall"] = {
        "n_expect_match_true": n_true,
        "n_expect_match_true_and_passed": n_true_pass,
        "pass_rate_of_expect_true": n_true_pass / n_true,
        "n_expect_match_false": len(recs) - n_true,
        "n_unexpected_deviations": sum(1 for r in recs if r["expect_match"] != r["match"]),
        "status_counts": dict(Counter(r["status"] for r in recs)),
    }

    # failure taxonomy: every expect_match=False case, classified by its own notes
    taxonomy = []
    for r in recs:
        if not r["expect_match"]:
            taxonomy.append({"name": r["name"], "group": r["group"], "status": r["status"],
                              "observed": r["observed"], "oracle": r["oracle"], "notes": r["notes"]})
    summary["adversarial_and_boundary_cases"] = taxonomy

    (HERE / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary["overall"], indent=2))
    print()
    for g, s in summary["groups"].items():
        print(g, s)


if __name__ == "__main__":
    main()
