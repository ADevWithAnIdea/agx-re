#!/usr/bin/env python3
"""Read nominated offsets from one explicitly named descriptor/state BO."""

from __future__ import annotations

import argparse
import pathlib

from capturelib import load, u32, u64


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=pathlib.Path)
    parser.add_argument("--u32", nargs="*", default=[])
    parser.add_argument("--u64", nargs="*", default=[])
    args = parser.parse_args()
    if not args.file.is_file():
        parser.error("input must be one explicit BO snapshot file")
    buffer = load(args.file)
    if buffer is None:
        parser.error("input is not a BO snapshot")
    print(f"INPUT path={args.file} va={buffer.gpu_va:#x}")
    for value in args.u32:
        offset = int(value, 0)
        print(f"U32 off={offset:#x} value={u32(buffer.data, offset):#010x}")
    for value in args.u64:
        offset = int(value, 0)
        print(f"U64 off={offset:#x} value={u64(buffer.data, offset):#018x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
