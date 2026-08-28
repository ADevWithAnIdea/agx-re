#!/usr/bin/env python3
"""EXP-0093 authored splice helper. Mirrors tools/agxtest/agxtest.py's splice
convention: locate a stage's _agc.main region via agxparse.py --locate, patch
bytes at an in-region offset on a SCRATCH COPY of the compiled archive file,
leave the original archive untouched. Used for the 0x07-family fence-byte
neutering splices (GLFS-A08 / ATOM-07..11 causal controls).

Usage:
  python3 splice.py --archive IN.bin --stage fragment --out OUT.bin \
      --splice OFF=HEXBYTES [--splice OFF=HEXBYTES ...]

OFF is a byte offset relative to the START of the located _agc.main region
(not an absolute file offset) -- the caller does not need to know the file's
absolute layout.
"""
import argparse, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AGXPARSE = REPO / "tools" / "shdump" / "agxparse.py"


def locate(archive, stage):
    p = subprocess.run(["python3", str(AGXPARSE), str(archive), "--stage", stage, "--locate", "_agc.main"],
                        capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"agxparse --locate failed: {p.stderr}")
    off, ln = p.stdout.strip().split()
    return int(off), int(ln)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--stage", required=True, choices=["fragment", "vertex", "compute"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--splice", action="append", default=[], help="OFF=HEXBYTES, repeatable")
    args = ap.parse_args()

    region_off, region_len = locate(args.archive, args.stage)
    shutil.copyfile(args.archive, args.out)
    with open(args.out, "r+b") as f:
        for spec in args.splice:
            off_s, hex_s = spec.split("=", 1)
            off = int(off_s, 0)
            patch = bytes.fromhex(hex_s)
            if off < 0 or off + len(patch) > region_len:
                raise RuntimeError(f"splice at {off} len {len(patch)} exceeds region_len {region_len}")
            f.seek(region_off + off)
            f.write(patch)
    print(f"REGION off={region_off} len={region_len}")
    print(f"WROTE {args.out}")


if __name__ == "__main__":
    main()
