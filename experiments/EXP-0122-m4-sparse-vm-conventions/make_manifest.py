#!/usr/bin/env python3
"""EXP-0122 manifest: hashes every authored file and every raw/ artifact. --write regenerates
manifest.json; --check verifies it against what's currently on disk (fails closed on drift)."""
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as R  # noqa: E402

MANIFEST = HERE / "manifest.json"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    authored = {}
    for rel in R.AUTH_CODE + R.AUTH_DOC:
        p = HERE / rel
        if p.exists():
            authored[rel] = {"sha256": sha(p), "size": p.stat().st_size}
    raw = {}
    raw_dir = HERE / "raw"
    if raw_dir.exists():
        for p in sorted(raw_dir.rglob("*")):
            if p.is_file():
                rel = str(p.relative_to(HERE))
                raw[rel] = {"sha256": sha(p), "size": p.stat().st_size}
    contract = {}
    cc = HERE / "CAPTURE_CONTRACT.json"
    if cc.exists():
        contract["CAPTURE_CONTRACT.json"] = {"sha256": sha(cc), "size": cc.stat().st_size}
    return {"schema": R.SCHEMA, "experiment": R.EXPERIMENT, "authored": authored,
            "contract": contract, "raw": raw}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cur = build()
    if args.write:
        MANIFEST.write_text(json.dumps(cur, indent=2, sort_keys=True))
        print("manifest written:", MANIFEST)
    if args.check:
        if not MANIFEST.exists():
            print("FAIL no manifest.json to check against (run --write first)")
            sys.exit(1)
        prev = json.loads(MANIFEST.read_text())
        if prev != cur:
            print("FAIL manifest drift detected")
            pk = set(prev.get("raw", {})) ^ set(cur.get("raw", {}))
            if pk:
                print("  raw key differences:", sorted(pk)[:20])
            for k in set(prev.get("authored", {})) & set(cur.get("authored", {})):
                if prev["authored"][k] != cur["authored"][k]:
                    print("  authored drift:", k)
            sys.exit(1)
        print("manifest check: OK (%d authored, %d raw)" % (len(cur["authored"]), len(cur["raw"])))
    if not args.write and not args.check:
        print(__doc__)


if __name__ == "__main__":
    main()
