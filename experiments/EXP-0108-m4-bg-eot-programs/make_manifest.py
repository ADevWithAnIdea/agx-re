#!/usr/bin/env python3
"""EXP-0108 manifest generator/checker. `--write` regenerates manifest.json
from the tree's current state; `--check` verifies it matches (fails closed)."""
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def expected(capture):
    entries = []
    for rel in ("README.md", "PRE_REGISTRATION.md", "RESULTS.md", "PROGRESS.md",
                "CAPTURE_CONTRACT.json", "run.py", "analysis.py", "verify.py",
                "make_manifest.py", "harness/wtrace.c", "harness/probe.m",
                "harness/build.sh", "harness/casematrix.py"):
        p = HERE / rel
        if p.exists():
            entries.append({"path": rel, "sha256": sha(p), "size": p.stat().st_size})
    if capture:
        raw = HERE / "raw"
        if raw.is_dir():
            for run_dir in sorted(raw.iterdir()):
                if not run_dir.is_dir():
                    continue
                for f in sorted(run_dir.iterdir()):
                    if f.is_file():
                        rel = f"raw/{run_dir.name}/{f.name}"
                        entries.append({"path": rel, "sha256": sha(f), "size": f.stat().st_size})
        aj = HERE / "analysis.json"
        if aj.exists():
            entries.append({"path": "analysis.json", "sha256": sha(aj), "size": aj.stat().st_size})
    return {"schema": 1, "experiment": "EXP-0108-m4-bg-eot-programs",
            "state": "CAPTURED" if capture else "PRE_GPU",
            "artifacts": sorted(entries, key=lambda e: e["path"])}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args()
    capture = (HERE / "raw").is_dir() and any((HERE / "raw").iterdir())
    exp = expected(capture)
    if a.write:
        (HERE / "manifest.json").write_text(json.dumps(exp, indent=2, sort_keys=True) + "\n")
        print("WROTE manifest.json (%d artifacts, state=%s)" % (len(exp["artifacts"]), exp["state"]))
        return 0
    mp = HERE / "manifest.json"
    if not mp.exists():
        print("FAIL: manifest.json missing"); return 1
    cur = json.loads(mp.read_text())
    if cur != exp:
        print("FAIL: manifest.json does not match current tree state")
        return 1
    print("CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
