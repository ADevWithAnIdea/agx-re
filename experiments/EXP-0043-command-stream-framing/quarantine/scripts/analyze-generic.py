#!/usr/bin/env python3
"""Repeatable structural analysis of EXP-0043 DATA-TRACE captures.

The output is deliberately restricted to command/state framing, observed BO
addresses, structural diffs, and pointer relocations. It never disassembles or
otherwise analyzes executable code, whether authored by us or not.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys

from capturelib import Buffer, by_va, load_dir, u32, u64


def command_candidates(buffer: Buffer) -> list[str]:
    out: list[str] = []
    data = buffer.data
    # CDM candidate: the authored probes use exact (grid,tg)=(64,32). Match the
    # six public dispatch dimensions and report the surrounding 0x2c framing.
    for off in range(0, max(0, len(data) - 0x2c + 1), 4):
        dims = tuple(u32(data, off + x) for x in (0x10, 0x14, 0x18, 0x1c, 0x20, 0x24))
        if dims == (64, 1, 1, 32, 1, 1):
            out.append(
                f"CDM_CANDIDATE va={buffer.gpu_va:#x} off={off:#x} "
                f"config={u32(data, off):#010x} word04={u32(data, off+4):#010x} "
                f"shader_shifted={u32(data, off+8):#010x} "
                f"word0c={u32(data, off+0xc):#010x} tail={u32(data, off+0x28):#010x}"
            )
    # VDM candidate: command word with the directly probed non-indexed opcode
    # and our alternating vertex counts. Include the following terminator word.
    for off in range(0, max(0, len(data) - 16 + 1), 4):
        word = u32(data, off)
        vertices = u32(data, off + 4)
        instances = u32(data, off + 8)
        if (word >> 16) == 0x61C4 and vertices in (3, 6) and instances == 1:
            out.append(
                f"VDM_DRAW va={buffer.gpu_va:#x} off={off:#x} word={word:#010x} "
                f"vertices={vertices} instances={instances} next={u32(data,off+12):#010x}"
            )
    return out


def inventory(directory: pathlib.Path) -> int:
    buffers = load_dir(directory)
    if not buffers:
        print(f"NO_BOS directory={directory}")
        return 1
    print("gpu_va size read complete nonzero path")
    for buffer in buffers:
        complete = buffer.read == buffer.size == len(buffer.data)
        nonzero = sum(byte != 0 for byte in buffer.data)
        print(
            f"{buffer.gpu_va:#014x} {buffer.size:#x} {buffer.read:#x} "
            f"{int(complete)} {nonzero} {buffer.path.name}"
        )
    print(
        f"SUMMARY bos={len(buffers)} complete={sum(b.read == b.size == len(b.data) for b in buffers)} "
        f"bytes={sum(b.read for b in buffers)}"
    )
    return 0


def scan(directory: pathlib.Path) -> int:
    found = []
    for buffer in load_dir(directory):
        found.extend(command_candidates(buffer))
    for line in found:
        print(line)
    counts = collections.Counter(line.split()[0] for line in found)
    print("SUMMARY " + " ".join(f"{key}={counts[key]}" for key in sorted(counts)))
    return 0 if found else 1


def diff(a_dir: pathlib.Path, b_dir: pathlib.Path) -> int:
    a, b = by_va(a_dir), by_va(b_dir)
    print("ONLY_A " + " ".join(f"{va:#x}" for va in sorted(set(a) - set(b))))
    print("ONLY_B " + " ".join(f"{va:#x}" for va in sorted(set(b) - set(a))))
    total = 0
    for va in sorted(set(a) & set(b)):
        left, right = a[va], b[va]
        length = min(len(left.data), len(right.data))
        offsets = [
            offset
            for offset in range(0, length, 4)
            if left.data[offset : offset + 4] != right.data[offset : offset + 4]
        ]
        if offsets or len(left.data) != len(right.data):
            total += len(offsets)
            ranges = []
            for offset in offsets:
                if not ranges or offset > ranges[-1][1] + 4:
                    ranges.append([offset, offset])
                else:
                    ranges[-1][1] = offset
            compact = ",".join(
                f"{lo:#x}" if lo == hi else f"{lo:#x}-{hi+3:#x}" for lo, hi in ranges
            )
            print(
                f"DIFF va={va:#x} words={len(offsets)} ranges={compact} "
                f"read_a={len(left.data):#x} read_b={len(right.data):#x}"
            )
    print(f"SUMMARY differing_words={total} paired_bos={len(set(a) & set(b))}")
    return 0


def pointer_edges(directory: pathlib.Path) -> set[tuple[int, int, int, int]]:
    buffers = load_dir(directory)
    windows = [
        (buffer.gpu_va, buffer.gpu_va + buffer.size, buffer.gpu_va)
        for buffer in buffers if buffer.gpu_va
    ]
    edges = set()
    for source in buffers:
        if not source.gpu_va:
            continue
        for offset in range(0, max(0, len(source.data) - 7), 4):
            value = u64(source.data, offset)
            for start, end, target in windows:
                if start <= value < end:
                    edges.add((source.gpu_va, offset, target, value - target))
                    break
    return edges


def relocations(a_dir: pathlib.Path, b_dir: pathlib.Path) -> int:
    a_edges = pointer_edges(a_dir)
    b_edges = pointer_edges(b_dir)
    a_slots = {(source, offset): (target, delta) for source, offset, target, delta in a_edges}
    b_slots = {(source, offset): (target, delta) for source, offset, target, delta in b_edges}
    common = set(a_slots) & set(b_slots)
    changed = 0
    for slot in sorted(common):
        if a_slots[slot] != b_slots[slot]:
            changed += 1
            print(
                f"RELOC_SLOT source={slot[0]:#x} off={slot[1]:#x} "
                f"a={a_slots[slot][0]:#x}+{a_slots[slot][1]:#x} "
                f"b={b_slots[slot][0]:#x}+{b_slots[slot][1]:#x}"
            )
    print(
        f"SUMMARY edges_a={len(a_edges)} edges_b={len(b_edges)} "
        f"common_slots={len(common)} changed_slots={changed}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "scan"):
        cmd = sub.add_parser(name)
        cmd.add_argument("directory", type=pathlib.Path)
    for name in ("diff", "relocations"):
        cmd = sub.add_parser(name)
        cmd.add_argument("a", type=pathlib.Path)
        cmd.add_argument("b", type=pathlib.Path)
    args = parser.parse_args()
    if args.command == "inventory":
        return inventory(args.directory)
    if args.command == "scan":
        return scan(args.directory)
    if args.command == "diff":
        return diff(args.a, args.b)
    if args.command == "relocations":
        return relocations(args.a, args.b)
    return 2


if __name__ == "__main__":
    sys.exit(main())
