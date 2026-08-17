#!/usr/bin/env python3
"""Compare two explicitly named, pre-classified command/state BO files."""

from __future__ import annotations

import argparse
import pathlib

from capturelib import load


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("a", type=pathlib.Path)
    parser.add_argument("b", type=pathlib.Path)
    parser.add_argument("--limit", default=None)
    args = parser.parse_args()
    if not args.a.is_file() or not args.b.is_file():
        parser.error("both inputs must be explicit BO snapshot files")
    a, b = load(args.a), load(args.b)
    if a is None or b is None:
        parser.error("both inputs must be BO snapshots")
    length = min(len(a.data), len(b.data))
    if args.limit:
        length = min(length, int(args.limit, 0))
    offsets = [
        off for off in range(0, length, 4)
        if a.data[off : off + 4] != b.data[off : off + 4]
    ]
    print(f"INPUT_A path={args.a} va={a.gpu_va:#x}")
    print(f"INPUT_B path={args.b} va={b.gpu_va:#x}")
    print(
        f"SUMMARY compared_bytes={length} differing_words={len(offsets)} "
        f"first_offsets={','.join(hex(off) for off in offsets[:32])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
