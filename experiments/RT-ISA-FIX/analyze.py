#!/usr/bin/env python3
"""Tokenize extracted kernels with the CURRENT isadb length rule and list ops,
highlighting the 0x0f exec-mask family, 0x07 fence, 0x32 carry-gen, ballot, shuffle."""
import sys, os
sys.path.insert(0, "/Users/user/cleanroom_gpu/tools/agx-isa")
import isadb

def toks(hx):
    b = bytes.fromhex(hx)
    off = 0
    out = []
    while off < len(b):
        n = isadb.instr_length(b, off)
        if n is None or n <= 0:
            out.append((off, None, b[off:off+2].hex()))
            off += 2
            continue
        out.append((off, n, b[off:off+n].hex()))
        off += n
    return out

def try_disasm(hx):
    try:
        d = isadb.disassemble(bytes.fromhex(hx))
        return d
    except Exception as e:
        return f"ERR: {e}"

hexes = {}
with open(os.path.join(os.path.dirname(__file__), "raw/all_hex.txt")) as f:
    for line in f:
        parts = line.split()
        if len(parts) == 2:
            hexes[parts[0]] = parts[1]

focus = sys.argv[1] if len(sys.argv) > 1 else None
for name, hx in hexes.items():
    if focus and focus not in name:
        continue
    print(f"\n===== {name} =====")
    for off, n, tok in toks(hx):
        b0 = tok[:2]
        b1 = tok[2:4] if len(tok) >= 4 else "??"
        b2 = tok[4:6] if len(tok) >= 6 else "??"
        flag = ""
        if b0 == "0f":
            flag = "  <-- 0x0F EXEC-MASK"
        elif b0 == "07":
            flag = "  <-- 0x07 FENCE"
        elif b0 == "32":
            flag = "  <-- 0x32 CARRY"
        elif b0 == "17":
            flag = "  <-- 0x17 BALLOT?"
        elif b0 in ("47", "c7"):
            flag = "  <-- SHUFFLE"
        lenstr = str(n) if n else "NONE"
        print(f"  +0x{off:03x} len={lenstr:>4} {tok}{flag}")
