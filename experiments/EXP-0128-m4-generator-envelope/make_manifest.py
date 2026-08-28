#!/usr/bin/env python3
"""EXP-0128 manifest generator/checker. Verbatim architecture from
EXP-0112's own make_manifest.py."""
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

FILES = [
    "isa_helpers.py", "families.py", "casematrix.py",
    "harness/build.sh", "harness/case_exec.py", "harness/recorded_fixture_case0.json",
    "run.py", "verify.py", "make_manifest.py", "baseline.py",
    "kernels/carrier_dag.metal",
    "PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "README.md",
]


def sha(p):
    return hashlib.sha256((HERE / p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args()

    missing = [f for f in FILES if not (HERE / f).exists()]
    if missing:
        print("FAIL: missing authored files:", missing)
        sys.exit(1)

    manifest = {"schema": 1, "files": {f: sha(f) for f in FILES}}

    if a.write:
        (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print("wrote manifest.json (%d files)" % len(FILES))
        sys.exit(0)

    current = json.loads((HERE / "manifest.json").read_text())
    if current["files"] != manifest["files"]:
        print("FAIL: manifest.json is stale relative to the current authored files")
        for f in FILES:
            if current["files"].get(f) != manifest["files"][f]:
                print("  drifted:", f)
        sys.exit(1)
    print("manifest: PASS (%d files match manifest.json)" % len(FILES))


if __name__ == "__main__":
    main()
