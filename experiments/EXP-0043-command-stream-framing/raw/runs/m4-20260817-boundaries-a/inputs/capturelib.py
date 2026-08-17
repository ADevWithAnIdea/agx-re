#!/usr/bin/env python3
"""DATA-only parser for iotrace BO hex snapshots.

This parser deliberately makes no attempt to recognize or decode shader code.
It is limited to headers, bytes, pointers, and known command-record candidates.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

HEXLINE = re.compile(r"^([0-9a-fA-F]{8}):\s+(.*)$")
HEADER = re.compile(
    r"gpu_va=0x([0-9a-fA-F]+) cpu=0x([0-9a-fA-F]+) "
    r"size=0x([0-9a-fA-F]+) read=0x([0-9a-fA-F]+)"
)


@dataclass(frozen=True)
class Buffer:
    path: pathlib.Path
    gpu_va: int
    cpu: int
    size: int
    read: int
    data: bytes


def load(path: pathlib.Path) -> Buffer | None:
    gpu_va = cpu = size = read = 0
    data = bytearray()
    with path.open(errors="replace") as stream:
        for line in stream:
            if line.startswith("#"):
                match = HEADER.search(line)
                if match:
                    gpu_va, cpu, size, read = (
                        int(match.group(i), 16) for i in range(1, 5)
                    )
                continue
            match = HEXLINE.match(line)
            if not match:
                continue
            offset = int(match.group(1), 16)
            raw = bytes.fromhex(match.group(2).replace(" ", ""))
            if len(data) < offset + len(raw):
                data.extend(b"\0" * (offset + len(raw) - len(data)))
            data[offset : offset + len(raw)] = raw
    if not size and not data:
        return None
    return Buffer(path, gpu_va, cpu, size, read, bytes(data))


def load_dir(directory: pathlib.Path) -> list[Buffer]:
    buffers = []
    for path in sorted(directory.glob("bo_*.hex")):
        buffer = load(path)
        if buffer:
            buffers.append(buffer)
    return buffers


def by_va(directory: pathlib.Path) -> dict[int, Buffer]:
    result: dict[int, Buffer] = {}
    for buffer in load_dir(directory):
        result.setdefault(buffer.gpu_va, buffer)
    return result


def u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def u64(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 8], "little")
