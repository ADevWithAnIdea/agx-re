#!/usr/bin/env python3
"""EXP-0116 analysis/report.py -- derives RESULTS.md's summary table directly
from the gated raw/ captures. Reproduction: `python3 analysis/report.py
raw/m4_20260828_run05`. No Apple binary inspected; pure JSONL bookkeeping.
"""
import json
import sys
import os


def load(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    run_dir = sys.argv[1] if len(sys.argv) > 1 else "raw/m4_20260828_run05"
    gated = load(os.path.join(run_dir, "02_results.jsonl"))
    rows = []
    for g in gated:
        case = g.get("case")
        rbA = g.get("readback_A_word0", g.get("readback_A"))
        rbMID = g.get("readback_MID_word0", g.get("readback_MID"))
        seg1_ran = (rbMID is not None and rbMID != g.get("sentinel_MID"))
        seg2_reached = (rbA == g.get("expect_seg2_last"))
        rows.append({
            "case": case, "wrote": g.get("wrote"), "hang": g.get("hang"),
            "final_status": g.get("final_status"),
            "final_error_category": g.get("final_error_category"),
            "readback_A": rbA, "readback_MID": rbMID,
            "seg1_ran": seg1_ran, "seg2_reached_via_redirect": seg2_reached,
        })
    print(f"{'case':26s} {'status':>6s} {'err_cat':18s} {'seg1_ran':9s} {'seg2_reached':13s}")
    for r in rows:
        print(f"{r['case']:26s} {str(r['final_status']):>6s} "
              f"{str(r['final_error_category']):18s} {str(r['seg1_ran']):9s} "
              f"{str(r['seg2_reached_via_redirect']):13s}")
    out = os.path.join(os.path.dirname(__file__), "summary.json")
    with open(out, "w") as f:
        json.dump(rows, f, indent=2)
        f.write("\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
