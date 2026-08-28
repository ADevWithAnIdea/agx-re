#!/usr/bin/env python3
"""Minimal parser for tools/iotrace BODUMP .hex snapshot files (the same format used
by RT-4/RT-11/EXP-M4-03/EXP-0009 etc. across this repository). Reads one little-endian
32-bit word at a given byte offset within the dumped BO.

Format (one line per 16 bytes, from tools/iotrace.c's own dump routine):
  "# BODUMP reason=... handle=... gpu_va=0x... cpu=0x... size=0x... read=0x..."
  "<hex offset>: <8-hex word> <8-hex word> <8-hex word> <8-hex word> "
where each 8-hex-char word prints the bytes in ascending-address (memory) order, so
bytes.fromhex(word) recovers the original little-endian byte sequence directly.
"""
import re
import struct

LINE_RE = re.compile(r'^([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{8}\s*)+)$')


def read_word_bytes(path, offset):
    with open(path) as f:
        header = f.readline()
        for line in f:
            line = line.rstrip("\n")
            m = LINE_RE.match(line.strip())
            if not m:
                continue
            base = int(m.group(1), 16)
            words = m.group(2).split()
            for i, w in enumerate(words):
                addr = base + i * 4
                if addr == offset:
                    return bytes.fromhex(w), header.strip()
    return None, None


def read_f32(path, offset):
    b, header = read_word_bytes(path, offset)
    if b is None:
        return None, header
    return struct.unpack("<f", b)[0], header


if __name__ == "__main__":
    import sys
    p, off = sys.argv[1], int(sys.argv[2], 0)
    v, h = read_f32(p, off)
    print(h)
    print(off, v)
