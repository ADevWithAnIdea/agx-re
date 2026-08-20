#!/usr/bin/env python3
"""Fail-closed report generator for the fixed EXP-0057 artifact matrix."""
import argparse
import json
from pathlib import Path

LEVELS = ["baseline", "p576", "p1024", "p2048", "p4096", "p8192", "p16384"]
SHAPES = ["tg32", "tg256"]


def record(path):
    obj = json.loads(path.read_text())
    if obj.get("timeout"):
        return {"result": "TIMEOUT"}
    if obj.get("exit") != 0:
        return {"result": "NONZERO", "exit": obj.get("exit"), "stderr": obj.get("stderr", "")}
    try:
        return json.loads(obj["stdout"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid probe record {path}: {exc}")


def main():
    p = argparse.ArgumentParser(); p.add_argument("--run-dir", required=True, type=Path); a = p.parse_args()
    raw = a.run_dir.resolve()
    if not raw.is_dir() or raw.is_symlink(): raise SystemExit("bad run directory")
    out = {"run": raw.name, "cases": {}}
    for level in LEVELS:
        meta = record(raw / f"metadata_{level}.json")
        entry = {"metadata": meta, "shapes": {}}
        for shape in SHAPES:
            path = raw / f"trial_{level}_{shape}.json"
            entry["shapes"][shape] = record(path) if path.exists() and not path.is_symlink() else {"result": "NOT_RUN"}
        out["cases"][level] = entry
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__": main()
