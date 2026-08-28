#!/usr/bin/env python3
"""EXP-0126 whole-tree artifact manifest. --check (pre-GPU: authored files
present + hashed) or --write (post-capture: adds raw/ tree hashes too)."""
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as RUN  # noqa: E402


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build(include_raw):
    m = {"schema": 1, "authored_code_sha256": {f: sha(HERE / f) for f in RUN.AUTH_CODE},
         "authored_kernel_sha256": {f: sha(HERE / f) for f in RUN.AUTH_KERNELS},
         "authored_doc_sha256": {f: sha(HERE / f) for f in RUN.AUTH_DOC}}
    if include_raw:
        raw = {}
        for rid in RUN.RUNS:
            d = HERE / "raw" / rid
            if d.exists():
                raw[rid] = {p.name: sha(p) for p in sorted(d.glob("*")) if p.is_file()}
        m["raw_sha256"] = raw
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.check:
        m = build(include_raw=False)
        missing = [f for f in RUN.AUTH_CODE + RUN.AUTH_KERNELS + RUN.AUTH_DOC if not (HERE / f).exists()]
        if missing:
            print("MISSING:", missing)
            sys.exit(1)
        print("manifest --check: PASS (%d authored files present)" %
              (len(RUN.AUTH_CODE) + len(RUN.AUTH_KERNELS) + len(RUN.AUTH_DOC)))
        return
    m = build(include_raw=True)
    (HERE / "manifest.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    print("wrote manifest.json")


if __name__ == "__main__":
    main()
