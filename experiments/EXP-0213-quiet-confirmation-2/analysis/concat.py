#!/usr/bin/env python3
"""EXP-0213 -- concatenate the per-arm captures of one order into ONE logical capture file.

    python3 analysis/concat.py <glob> <out.jsonl>

Phase 1 dispatches EXP-0204's own run.py once per arm (its own `--arms` selector), so one
logical capture is spread over 22 run directories.  This joins them, in a deterministic
arm-sorted order, into a single derived file under analysis/out/.  `raw/` is never modified:
these are DERIVED files and are regenerable from the raw at any time.

Every source run directory and its sha256 are recorded in <out.jsonl>.manifest.json.
"""
import glob
import hashlib
import json
import os
import sys


def main():
    pat, out = sys.argv[1], sys.argv[2]
    dirs = sorted(glob.glob(pat))
    src = []
    n = 0
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        for d in dirs:
            p = os.path.join(d, "sweep.jsonl")
            if not os.path.exists(p):
                src.append({"dir": d, "error": "no sweep.jsonl"})
                continue
            b = open(p, "rb").read()
            src.append({"dir": os.path.basename(d), "sha256": hashlib.sha256(b).hexdigest(),
                        "bytes": len(b)})
            for ln in b.decode().splitlines():
                if ln.strip():
                    f.write(ln + "\n")
                    n += 1
    json.dump({"pattern": pat, "out": out, "records": n, "sources": src},
              open(out + ".manifest.json", "w"), indent=1)
    print("%s  <- %d dirs, %d records" % (out, len(dirs), n))


if __name__ == "__main__":
    main()
