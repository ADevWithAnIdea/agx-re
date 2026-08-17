#!/usr/bin/env python3
"""Analyze only explicitly named, pre-classified command BO snapshots.

Clean-room safety property: this tool accepts files, never a capture directory.
It opens only the paths listed on its command line and does not dereference or
follow any encoded address. Callers must pre-classify every input as CDM or VDM
command data from independent authored-workload correlation.
"""

from __future__ import annotations

import argparse
import collections
import pathlib

from capturelib import Buffer, load, u32


def describe_control(data: bytes, offset: int, link_opcode: int, terminal: int) -> str:
    first = u32(data, offset)
    if first == terminal:
        return f"TERMINATE off={offset:#x} word={first:#010x}"
    second = u32(data, offset + 4)
    if first & 0xF0000000 == link_opcode:
        encoded_target = ((first & 0x0FFFFFFF) << 32) | second
        return (
            f"LINK off={offset:#x} words={first:#010x},{second:#010x} "
            f"encoded_target={encoded_target:#x}"
        )
    return f"OTHER off={offset:#x} words={first:#010x},{second:#010x}"


def cdm(buffer: Buffer) -> str:
    offsets = []
    for off in range(0, max(0, len(buffer.data) - 0x2C + 1), 4):
        dims = tuple(u32(buffer.data, off + x) for x in (0x10, 0x14, 0x18, 0x1C, 0x20, 0x24))
        if dims == (64, 1, 1, 32, 1, 1) and u32(buffer.data, off + 0x28) == 0x60000160:
            offsets.append(off)
    if not offsets:
        return f"CDM_EXPLICIT va={buffer.gpu_va:#x} records=0"
    strides = collections.Counter(b - a for a, b in zip(offsets, offsets[1:]))
    control_offset = offsets[-1] + 0x2C
    control = describe_control(buffer.data, control_offset, 0x20000000, 0x40000000)
    tail_start = control_offset + (8 if control.startswith("LINK") else 4)
    return (
        f"CDM_EXPLICIT va={buffer.gpu_va:#x} records={len(offsets)} "
        f"first={offsets[0]:#x} last={offsets[-1]:#x} "
        f"strides={dict(sorted(strides.items()))} {control} "
        f"tail_bytes={len(buffer.data)-tail_start} tail_nonzero="
        f"{sum(byte != 0 for byte in buffer.data[tail_start:])}"
    )


def vdm(buffer: Buffer) -> str:
    draws = []
    for off in range(0, max(0, len(buffer.data) - 16 + 1), 4):
        word = u32(buffer.data, off)
        if (word >> 16) == 0x61C4 and u32(buffer.data, off + 4) in (3, 6) \
                and u32(buffer.data, off + 8) == 1:
            draws.append(off)
    if not draws:
        return f"VDM_EXPLICIT va={buffer.gpu_va:#x} draws=0"
    headers = [
        off for off in range(0, draws[-1] + 1, 4)
        if u32(buffer.data, off) == 0x4000002E
    ]
    prefixes = collections.Counter()
    header_index = 0
    for draw in draws:
        while header_index + 1 < len(headers) and headers[header_index + 1] <= draw:
            header_index += 1
        prefixes[draw - headers[header_index]] += 1
    strides = collections.Counter(b - a for a, b in zip(draws, draws[1:]))
    vertices = [u32(buffer.data, off + 4) for off in draws]
    alternating = all(value == (3 if i % 2 == 0 else 6) for i, value in enumerate(vertices))
    control_offset = draws[-1] + 0x10
    control = describe_control(buffer.data, control_offset, 0x80000000, 0xC0000000)
    tail_start = control_offset + (8 if control.startswith("LINK") else 4)
    return (
        f"VDM_EXPLICIT va={buffer.gpu_va:#x} draws={len(draws)} headers={len(headers)} "
        f"first={draws[0]:#x} last={draws[-1]:#x} "
        f"draw_strides={dict(sorted(strides.items()))} "
        f"header_to_draw={dict(sorted(prefixes.items()))} alternating_3_6={int(alternating)} "
        f"{control} tail_bytes={len(buffer.data)-tail_start} "
        f"tail_nonzero={sum(byte != 0 for byte in buffer.data[tail_start:])}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("cdm", "vdm"), required=True)
    parser.add_argument("files", type=pathlib.Path, nargs="+")
    args = parser.parse_args()
    total = 0
    for path in args.files:
        if not path.is_file():
            parser.error(f"not a file: {path}")
        buffer = load(path)
        if buffer is None:
            parser.error(f"not a BO snapshot: {path}")
        line = cdm(buffer) if args.kind == "cdm" else vdm(buffer)
        print(f"INPUT path={path}")
        print(line)
        field = "records=" if args.kind == "cdm" else "draws="
        total += int(line.split(field, 1)[1].split()[0])
    print(f"SUMMARY explicit_files={len(args.files)} {args.kind}_total={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
