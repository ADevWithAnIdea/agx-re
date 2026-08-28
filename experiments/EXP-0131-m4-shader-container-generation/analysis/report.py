#!/usr/bin/env python3
"""EXP-0131 analysis: diff each case's pre-registered prediction
(casematrix.PREDICTIONS) against what was actually observed in a captured
run's raw/<run-id>/02_results.jsonl, and against the other run for
determinism. Writes analysis/report.json (machine-readable) and prints a
human-readable table. Never touches the GPU; reads raw/ only.

Usage: python3 analysis/report.py m4_20260828_run01 m4_20260828_run02
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from casematrix import CASES, PREDICTIONS  # noqa: E402


def load(run_id: str) -> dict:
    out = {}
    for line in (ROOT / "raw" / run_id / "02_results.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        out[rec.get("case")] = rec
    return out


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    run_a, run_b = sys.argv[1], sys.argv[2]
    recs_a = load(run_a)
    recs_b = load(run_b)

    report = {"run_a": run_a, "run_b": run_b, "cases": {}}
    print(f"{'case':<28} {'pred_bgra':<10} {'obs_bgra':<10} {'match':<6} {'hang_ok':<8} {'cross_run_eq':<12}")
    all_ok = True
    for case in CASES:
        pred = PREDICTIONS[case]
        ra = recs_a.get(case, {})
        rb = recs_b.get(case, {})
        obs_bgra = ra.get("post_mutation_bgra")
        pred_bgra = pred["post_mutation_bgra"]
        bgra_match = (pred_bgra is None) or (obs_bgra == pred_bgra)
        hang_ok = (ra.get("post_mutation_hang") == pred["post_mutation_hang"])
        cross_eq = json.dumps(ra, sort_keys=True) == json.dumps(rb, sort_keys=True)
        ok = bgra_match and hang_ok and cross_eq
        all_ok = all_ok and ok
        report["cases"][case] = {
            "predicted_bgra": pred_bgra, "observed_bgra": obs_bgra,
            "bgra_match": bgra_match, "hang_ok": hang_ok, "cross_run_equal": cross_eq,
            "note": pred["note"],
        }
        print(f"{case:<28} {str(pred_bgra):<10} {str(obs_bgra):<10} {str(bgra_match):<6} "
              f"{str(hang_ok):<8} {str(cross_eq):<12}")

    (ROOT / "analysis" / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"\nALL PREDICTIONS MATCH OBSERVATIONS AND ARE CROSS-RUN DETERMINISTIC: {all_ok}")
    print("analysis/report.json written")


if __name__ == "__main__":
    main()
