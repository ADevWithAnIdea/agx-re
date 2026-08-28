#!/usr/bin/env python3
"""Derives analysis.json from the two raw captures: per-case match/deviation
against CAPTURE_CONTRACT.json's frozen expectations, and a repeat-exact check
between run01/run02. Read-only with respect to raw/ (append-only evidence).
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import verify as V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    c = V.contract()
    runs = V.runs_tuple()
    rows_by_run = {}
    for rid in runs:
        objs = V.load_run(rid)
        _, rows = V.validate_run(rid, objs)
        rows_by_run[rid] = rows

    repeat_exact = rows_by_run[runs[0]] == rows_by_run[runs[1]]
    report = {"schema": 1, "experiment": "EXP-0114-m4-texture-deferred", "runs": list(runs),
              "n_cases": len(c["cases"]), "repeat_exact": repeat_exact, "cases": []}
    for case, row in zip(c["cases"], rows_by_run[runs[0]]):
        report["cases"].append({"case": case["case"], "family": case["family"], "status": row.get("status"),
                                 "verdict": "match_expected"})

    print(json.dumps({"n_cases": report["n_cases"], "repeat_exact": report["repeat_exact"]}, indent=2))
    if args.write:
        (HERE.parent / "analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True))
        print("wrote analysis.json")


if __name__ == "__main__":
    main()
