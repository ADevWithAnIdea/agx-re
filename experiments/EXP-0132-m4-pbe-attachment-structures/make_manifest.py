#!/usr/bin/env python3
"""EXP-0132 manifest: sha256 every retained artifact. --write to (re)generate,
--check to verify manifest.json matches the tree (fails on drift)."""
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"

INCLUDE_DIRS = ["harness", "raw", "analysis"]
INCLUDE_FILES = ["README.md", "PRE_REGISTRATION.md", "RESULTS.md", "PROGRESS.md",
                  "CAPTURE_CONTRACT.json", "run.py", "verify.py", "analysis.py",
                  "make_manifest.py", "analysis.json"]
EXCLUDE_SUFFIXES = (".pyc",)
EXCLUDE_DIR_NAMES = {"__pycache__"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def collect():
    files = {}
    for name in INCLUDE_FILES:
        p = HERE / name
        if p.exists():
            files[name] = sha(p)
    for d in INCLUDE_DIRS:
        base = HERE / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_dir():
                continue
            if p.suffix in EXCLUDE_SUFFIXES:
                continue
            if any(part in EXCLUDE_DIR_NAMES for part in p.relative_to(HERE).parts):
                continue
            files[str(p.relative_to(HERE))] = sha(p)
    return files


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    args = ap.parse_args()

    files = collect()
    if args.write:
        MANIFEST.write_text(json.dumps({"schema": 1, "files": files}, indent=2, sort_keys=True))
        print(f"wrote manifest.json with {len(files)} entries")
        sys.exit(0)
    else:
        if not MANIFEST.exists():
            print("manifest.json missing -- run --write first", file=sys.stderr)
            sys.exit(1)
        recorded = json.loads(MANIFEST.read_text())["files"]
        missing = sorted(set(recorded) - set(files))
        extra = sorted(set(files) - set(recorded))
        changed = sorted(k for k in (set(recorded) & set(files)) if recorded[k] != files[k])
        ok = not missing and not extra and not changed
        print(f"--check: {'PASS' if ok else 'FAIL'} ({len(files)} files on disk, "
              f"{len(recorded)} in manifest)")
        if missing:
            print("  MISSING (in manifest, not on disk):", missing)
        if extra:
            print("  EXTRA (on disk, not in manifest -- run --write):", extra)
        if changed:
            print("  CHANGED:", changed)
        sys.exit(0 if ok else 1)
