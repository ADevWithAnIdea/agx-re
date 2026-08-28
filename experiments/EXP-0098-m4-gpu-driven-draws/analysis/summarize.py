#!/usr/bin/env python3
"""EXP-0098 repeatable analysis: extracts the headline statistics cited in
RESULTS.md from the two official raw/ captures. Read-only; writes nothing.

Usage: python3 analysis/summarize.py
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent

RUN_A = "m4_20260828_run01b"
RUN_B = "m4_20260828_run02b"


def load(run):
    gated, nongated = {}, {}
    for line in (EXP / "raw" / run / "02_gated.jsonl").read_text().splitlines():
        r = json.loads(line); gated[r["case_id"]] = r
    for line in (EXP / "raw" / run / "03_nongated.jsonl").read_text().splitlines():
        r = json.loads(line); nongated[r["case_id"]] = r
    return gated, nongated


def main():
    g1, n1 = load(RUN_A)
    g2, n2 = load(RUN_B)

    print("== h_sync unsafe-mode race rate (both runs combined, 8 trials/row) ==")
    for indexed in ("nonindexed", "indexed"):
        for mode in ("unsync_split", "asym_producer", "asym_consumer"):
            raced = sum(1 for run_g in (g1, g2) for r in range(4)
                        if run_g[f"hsync_{indexed}_{mode}_r{r}"]["observed"]["n_stale"] > 0)
            print(f"  {indexed:12s} {mode:15s}: raced {raced}/8")

    print("\n== xfb_sync unsafe-mode: staleness (should be 0) + wall_ms (should be ~15.6-15.8s) ==")
    for mode in ("unsync_split", "asym_producer", "asym_consumer"):
        for run_name, run_g, run_n in ((RUN_A, g1, n1), (RUN_B, g2, n2)):
            for r in range(3):
                cid = f"xfbsync_{mode}_r{r}"
                obs = run_g[cid]["observed"]
                print(f"  {run_name} {mode:15s} r{r}: n_stale={obs['n_stale']} wall_ms={run_n[cid]['wall_ms']:.1f}")

    print("\n== h_icbmax crash boundary ==")
    for tc in (1024, 65536, 1048576, 4194304, 8388608):
        for run_name, run_g in ((RUN_A, g1), (RUN_B, g2)):
            r = run_g[f"hicbmax_{tc}"]
            print(f"  {run_name} hicbmax_{tc}: status={r['status']} verdict={r['verdict']}")

    print("\n== h_icbrange loc_past_max fault ==")
    for run_name, run_g in ((RUN_A, g1), (RUN_B, g2)):
        r = run_g["hicbrange_loc_past_max"]
        print(f"  {run_name}: status={r['status']} verdict={r['verdict']}")

    print("\n== overall verdict counts ==")
    for run_name, run_g in ((RUN_A, g1), (RUN_B, g2)):
        counts = {}
        for r in run_g.values():
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        print(f"  {run_name}: {counts}")


if __name__ == "__main__":
    main()
