#!/usr/bin/env python3
"""Compare the semantic public observations in two EXP-0057 runs."""
import argparse
import json
from pathlib import Path

LEVELS = ["baseline", "p576", "p1024", "p2048", "p4096", "p8192", "p16384"]
SHAPES = ["tg32", "tg256"]


def load(run):
    data = {}
    for level in LEVELS:
        meta = json.loads((run / f"metadata_{level}.json").read_text())
        if meta.get("timeout") or meta.get("exit") != 0: raise ValueError(f"bad metadata {level}")
        m = json.loads(meta["stdout"])
        states = {}
        for shape in SHAPES:
            trial = json.loads((run / f"trial_{level}_{shape}.json").read_text())
            if trial.get("timeout") or trial.get("exit") != 0: raise ValueError(f"bad trial {level}/{shape}")
            p = json.loads(trial["stdout"])
            states[shape] = {k: p[k] for k in ("status", "tg", "threads", "words", "prefix_guard", "suffix_guard", "exact")}
        data[level] = {"gpr_field_0": m["gpr_field_0"],
                       "scratch_field_41_or_14": m["scratch_field_41_or_14"], "shapes": states}
    return data


def main():
    p = argparse.ArgumentParser(); p.add_argument("run_a", type=Path); p.add_argument("run_b", type=Path); a = p.parse_args()
    left, right = load(a.run_a), load(a.run_b)
    mismatches = {key: {"run_a": left[key], "run_b": right[key]} for key in LEVELS if left[key] != right[key]}
    print(json.dumps({"run_a": a.run_a.name, "run_b": a.run_b.name, "semantic_match": not mismatches,
                      "mismatches": mismatches, "cases": left}, indent=2, sort_keys=True))
    if mismatches: raise SystemExit(1)


if __name__ == "__main__": main()
