#!/usr/bin/env python3
# EXP-O2C: extract the specific RT instructions from each kernel's _agc.main for
# byte-diffing: rt_intersect (lo-nibble 4, +1=ea), 0x5f, 0xdf (first few), and
# the ray-move ops (lo-nibble b, +2 in {0x80,0x81}). Uses the analyze.py length
# rule so we walk real instruction boundaries. CLEAN-ROOM: our own bytes only.
import sys, importlib.util
an = importlib.util.spec_from_file_location("an", "analyze.py")
A = importlib.util.module_from_spec(an); an.loader.exec_module(A)
L = A.L

def ops(b):
    o = 0; out = []
    while o < len(b):
        Lv = L(b, o)
        if Lv is None or o+Lv > len(b):
            o += 2; continue
        out.append((o, b[o], b[o:o+Lv]))
        o += Lv
    return out

def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    want = sys.argv[2:]
    for line in open("raw/mains.txt"):
        line = line.strip()
        if not line or line.startswith('#'): continue
        p = line.split(); grp, fn, h = p[0], p[1], p[-1]
        if want and fn not in want and grp not in want: continue
        if not all(c in '0123456789abcdef' for c in h.lower()): continue
        b = bytes.fromhex(h)
        recs = ops(b)
        rti = [(o, x) for (o, b0, x) in recs if (b0 & 0x0f) == 0x4 and A.B(b, o+1) == 0xea]
        f5 = [(o, x) for (o, b0, x) in recs if b0 == 0x5f]
        df = [(o, x) for (o, b0, x) in recs if b0 == 0xdf]
        rmov = [(o, x) for (o, b0, x) in recs if (b0 & 0x0f) == 0xb and A.B(b, o+2) in (0x80, 0x81)]
        tr2 = [(o, x) for (o, b0, x) in recs if (b0 & 0x0f) == 0x2 and A.B(b, o+2) == 0x27]
        print(f"\n===== {grp}/{fn} ({len(b)}B) =====")
        if which in ("all", "rti"):
            for o, x in rti: print(f"  rt_intersect @{o:5d}: {x.hex()}")
        if which in ("all", "5f"):
            for o, x in f5[:6]: print(f"  0x5f         @{o:5d}: {x.hex()}")
            if len(f5) > 6: print(f"  0x5f ... ({len(f5)} total)")
        if which in ("all", "df"):
            for o, x in df[:4]: print(f"  0xdf         @{o:5d}: {x.hex()}")
            if len(df) > 4: print(f"  0xdf ... ({len(df)} total)")
        if which in ("all", "rmov"):
            for o, x in rmov[:6]: print(f"  raymov       @{o:5d}: {x.hex()}")
            if len(rmov) > 6: print(f"  raymov ... ({len(rmov)} total)")
        if which in ("all", "tr2"):
            for o, x in tr2[:4]: print(f"  rt2/27       @{o:5d}: {x.hex()}")

if __name__ == "__main__":
    main()
