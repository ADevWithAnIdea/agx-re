#!/usr/bin/env python3
# EXP-0022 structural analysis of simdgroup_matrix _agc.main streams.
# Walks each stream with the known G17P length rule (from tools/agx-isa) and
# flags novel opcode groups (matrix candidates). For an unknown byte0 it tries a
# range of lengths and reports which makes the remainder re-tokenize cleanly to
# the trailing store + stop word.  CLEAN-ROOM: OUR OWN compiled bytes only.
import sys, os

# Known length rule (mirrors tools/agx-isa db.json byte0_table + EXP-0018 split).
def B(b, o):
    return b[o] if o < len(b) else 0

def known_len(b, o):
    b0 = b[o]; lo = b0 & 0x0f
    if b0 == 0x0e: return 4
    # preamble/get-special-register: byte+2==0x10 && byte+3==0x06 (X4../Xc.. 1006)
    if B(b, o+2) == 0x10 and B(b, o+3) == 0x06: return 4
    if lo == 0x0c: return 4                        # get_sr
    if b0 == 0x1b: return 2                        # 2-byte marker/wait (EXP-0022)
    if b0 == 0x13: return 4
    if b0 in (0x05, 0x16): return 4
    if b0 in (0x67, 0xe7): return 14              # memory load/store/atomic
    if b0 in (0x47, 0xc7): return 10              # simd/quad shuffle
    if b0 == 0x17: return 10                      # ballot
    if b0 == 0xcf: return 12                       # *** matrix MAC (EXP-0022) ***
    if b0 in (0x2c, 0x3c): return 8                # matrix fill / result-move (EXP-0022)
    if b0 in (0xbf, 0x3f, 0xb7) and B(b, o+2) == 0x56: return 8   # reduce/scan
    if b0 == 0x37: return 8 if B(b, o+2) == 0x56 else 10
    if b0 in (0x9f, 0x1f): return 10 if (b[o+1] & 1) else 12
    if b0 == 0xa7: return 8 if b[o+1] == 0x07 else (10 if (b[o+1] & 1) else 12)
    if b0 == 0x27: return 10 if b[o+1] == 0x07 else (12 if b[o+1] in (0, 0x10) else 8)
    if b0 == 0x0b: return 10
    if b0 == 0x02: return 6
    if b0 == 0x12: return 14 if (B(b, o+2) & 0x0f) == 0x0d else 6
    if b0 == 0x0a: return 6
    if b0 in (0x2f, 0xaf): return 10
    if b0 == 0x11: return 8 if (B(b, o+2) & 0x02) else 6
    if b0 == 0x09: return 8 if (B(b, o+2) & 0x02) else 6
    if b0 == 0x0f:
        sub = b[o+1]
        return {0x00:10, 0x05:8, 0x06:6}.get(sub)
    return None   # UNKNOWN group

NOVEL = {}

def walk(hexs):
    b = bytes.fromhex(hexs); o = 0; out = []
    while o < len(b):
        b0 = b[o]
        L = known_len(b, o)
        novel = L is None
        if novel:
            # try to guess a length that lets the remainder tokenize cleanly
            L = guess_len(b, o)
        out.append((o, b0, L, novel, b[o:o+L].hex() if L else b[o:].hex()))
        if L is None or o + L > len(b):
            o = o + L if L else len(b)
            if L is None: break
            continue
        o += L
    return out

def tail_clean(b, o):
    """Return True if from o the stream tokenizes cleanly to end using known_len."""
    while o < len(b):
        L = known_len(b, o)
        if L is None or o + L > len(b):
            return False
        o += L
    return o == len(b)

def guess_len(b, o):
    for L in range(2, 40, 2):
        if o + L > len(b): break
        if tail_clean(b, o + L):
            return L
    return None

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "raw/mains.txt")
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"): continue
        parts = line.split()
        if len(parts) < 3: continue
        grp, fn, hexs = parts[0], parts[1], parts[-1]
        if not all(c in "0123456789abcdef" for c in hexs.lower()): continue
        print(f"\n===== {grp}/{fn}  ({len(hexs)//2} bytes) =====")
        recs = walk(hexs)
        counts = {}
        for o, b0, L, novel, h in recs:
            tag = "  <<< NOVEL" if novel else ""
            Ls = f"len={L}" if L else "UNKNOWN"
            print(f"  @{o:4d}  {b0:#04x}  {Ls:8s} {h}{tag}")
            if novel:
                counts[b0] = counts.get(b0, 0) + 1
        if counts:
            print(f"  NOVEL GROUPS: " + ", ".join(f"{k:#04x} x{v}" for k, v in sorted(counts.items())))

if __name__ == "__main__":
    main()
