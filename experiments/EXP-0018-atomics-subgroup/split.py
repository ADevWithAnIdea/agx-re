#!/usr/bin/env python3
# EXP-0018 precise structural splitter. Walks a _agc.main body applying an
# EXTENDED length table (adds the atomic/simd/shuffle groups discovered in this
# experiment) and prints each instruction with byte offsets, so the atomic
# memory op, its operation selector, and the SIMD reduce ops can be read exactly.
# CLEAN-ROOM: hex of OUR OWN compiled shaders only.
import sys, os

def ilen(b, o):
    b0 = b[o]; lo = b0 & 0x0f
    if b0 == 0x0e: return 4
    if lo == 0x0c: return 4                 # get_sr
    if b0 in (0x67, 0xe7): return 14        # memory load/store/ATOMIC
    if lo == 0x0f: return 8                 # bf/3f SIMD reduce/scan (this exp)
    if b0 in (0x47, 0xc7): return 10        # SIMD/quad shuffle/broadcast (this exp)
    if lo == 0x07 and b0 in (0x17, 0x07): return 10  # ballot/vote source (this exp)
    if b0 in (0x9f, 0x1f): return 10 if (b[o+1] & 1) else 12
    if b0 == 0xa7: return 8 if b[o+1] == 0x07 else (10 if (b[o+1] & 1) else 12)
    if b0 == 0x27: return 10 if b[o+1] == 0x07 else (12 if b[o+1] in (0,0x10) else 8)
    if b0 == 0x0b: return 10
    if b0 == 0x2c: return 8                 # observed post-atomic mov (this exp, tentative)
    if b0 == 0x24: return 4                 # observed 0x24.. prefix (tentative)
    if b0 == 0x02: return 6
    if b0 == 0x12: return 14 if (b[o+2] & 0x0f) == 0x0d else 6
    if b0 == 0x0a: return 6
    if b0 in (0x05, 0x16): return 4
    if b0 == 0x1b: return 4                 # observed (tentative)
    if b0 == 0x13: return 4
    if b0 in (0x11,): return 8 if (b[o+2] & 0x02) else 6
    if b0 in (0x2f, 0xaf): return 10
    if b0 == 0x0f:
        sub = b[o+1]
        if sub == 0x00: return 10           # jump
        if sub == 0x05: return 8            # mask push (this exp: 0f 05 54 xx xx xx xx xx)
        if sub == 0x06: return 6            # reconverge (0f 06 xx xx xx xx)
        return None
    return None

def walk(hexs, start=0):
    b = bytes.fromhex(hexs); o = start; out = []
    while o < len(b):
        L = ilen(b, o)
        if L is None or o + L > len(b):
            out.append((o, None, b[o:].hex())); break
        out.append((o, L, b[o:o+L].hex())); o += L
    return out

if __name__ == "__main__":
    hexs = sys.argv[1]
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    for o, L, h in walk(hexs, start):
        tag = f"len={L}" if L else "UNKNOWN-TAIL"
        b0 = h[:2]
        print(f"  @{o:3d} {b0}  {tag:12s} {h}")
