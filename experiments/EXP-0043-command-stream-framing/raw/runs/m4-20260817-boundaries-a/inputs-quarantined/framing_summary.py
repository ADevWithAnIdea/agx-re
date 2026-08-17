#!/usr/bin/env python3
"""Summarize repeated CDM/VDM record framing and segment links.

DATA-only: recognizes dimensions/counts authored by EXP-0043, then reports the
adjacent command words. It does not inspect or classify executable code.
"""

from __future__ import annotations

import argparse
import collections
import pathlib

from capturelib import Buffer, load_dir, u32


def cdm_offsets(buffer: Buffer) -> list[int]:
    result = []
    for off in range(0, max(0, len(buffer.data) - 0x2C + 1), 4):
        dims = tuple(u32(buffer.data, off + x) for x in (0x10, 0x14, 0x18, 0x1C, 0x20, 0x24))
        if dims == (64, 1, 1, 32, 1, 1) and u32(buffer.data, off + 0x28) == 0x60000160:
            result.append(off)
    return result


def vdm_offsets(buffer: Buffer) -> list[int]:
    result = []
    for off in range(0, max(0, len(buffer.data) - 16 + 1), 4):
        word = u32(buffer.data, off)
        if (word >> 16) == 0x61C4 and u32(buffer.data, off + 4) in (3, 6) \
                and u32(buffer.data, off + 8) == 1:
            result.append(off)
    return result


def describe_control(data: bytes, offset: int, link_opcode: int, terminal: int) -> str:
    if offset + 4 > len(data):
        return "OUT_OF_RANGE"
    first = u32(data, offset)
    if first == terminal:
        return f"TERMINATE word={first:#010x} off={offset:#x}"
    if first & 0xF0000000 == link_opcode:
        if offset + 8 > len(data):
            return f"TRUNCATED_LINK word={first:#010x} off={offset:#x}"
        low = u32(data, offset + 4)
        target = ((first & 0x0FFFFFFF) << 32) | low
        return (
            f"LINK off={offset:#x} words={first:#010x},{low:#010x} "
            f"target={target:#x}"
        )
    return f"OTHER off={offset:#x} words={first:#010x},{u32(data,offset+4):#010x}"


def summarize(directory: pathlib.Path) -> int:
    buffers = load_dir(directory)
    vas = {buffer.gpu_va for buffer in buffers}
    cdm_total = vdm_total = 0
    for buffer in buffers:
        offsets = cdm_offsets(buffer)
        if offsets:
            cdm_total += len(offsets)
            strides = collections.Counter(b - a for a, b in zip(offsets, offsets[1:]))
            control = describe_control(buffer.data, offsets[-1] + 0x2C, 0x20000000, 0x40000000)
            target_text = ""
            if "target=" in control:
                target = int(control.rsplit("target=", 1)[1], 16)
                target_text = f" target_captured={int(target in vas)}"
            print(
                f"CDM_SEGMENT va={buffer.gpu_va:#x} records={len(offsets)} "
                f"first={offsets[0]:#x} last={offsets[-1]:#x} "
                f"strides={dict(sorted(strides.items()))} {control}{target_text}"
            )

        draws = vdm_offsets(buffer)
        if draws:
            vdm_total += len(draws)
            headers = [
                off for off in range(0, len(buffer.data) - 3, 4)
                if u32(buffer.data, off) == 0x4000002E
            ]
            headers = [off for off in headers if off <= draws[-1]]
            draw_strides = collections.Counter(b - a for a, b in zip(draws, draws[1:]))
            prefixes = collections.Counter()
            for draw in draws:
                prior = [header for header in headers if header <= draw]
                if prior:
                    prefixes[draw - prior[-1]] += 1
            control = describe_control(buffer.data, draws[-1] + 0x10, 0x80000000, 0xC0000000)
            target_text = ""
            if "target=" in control:
                target = int(control.rsplit("target=", 1)[1], 16)
                target_text = f" target_captured={int(target in vas)}"
            vertices = [u32(buffer.data, off + 4) for off in draws]
            alternating = all(value == (3 if i % 2 == 0 else 6) for i, value in enumerate(vertices))
            print(
                f"VDM_SEGMENT va={buffer.gpu_va:#x} draws={len(draws)} "
                f"headers={len(headers)} first={draws[0]:#x} last={draws[-1]:#x} "
                f"draw_strides={dict(sorted(draw_strides.items()))} "
                f"header_to_draw={dict(sorted(prefixes.items()))} alternating_3_6={int(alternating)} "
                f"{control}{target_text}"
            )
    print(f"SUMMARY cdm_records={cdm_total} vdm_draws={vdm_total}")
    return 0 if cdm_total or vdm_total else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=pathlib.Path)
    args = parser.parse_args()
    return summarize(args.directory)


if __name__ == "__main__":
    raise SystemExit(main())
