#!/usr/bin/env python3
"""RT-10 census: walk each extracted _agc.main with the CURRENT isadb length rule,
counting bytes that are (a) tokenized [length known] and (b) descriptor-named
[decode_one succeeds]. Resyncs by +2 on an unknown byte0 (like RT-ISA-FIX analyze.py).
Reports per-kernel and aggregate %, plus a byte0 histogram of UNDECODED (length-None) leaders."""
import sys, os, collections
sys.path.insert(0, "/Users/user/cleanroom_gpu/tools/agx-isa")
import isadb

def walk(b):
    """Yield (off, length_or_None, named_bool, tokbytes)."""
    off = 0
    n = len(b)
    while off < n:
        L = isadb.instr_length(b, off)
        if L is None or L <= 0 or off + L > n:
            yield (off, None, False, bytes(b[off:off+2]))
            off += 2
            continue
        named = False
        try:
            rec, _ = isadb.decode_one(b, off)
            named = not rec.get("error")
        except Exception:
            named = False
        yield (off, L, named, bytes(b[off:off+L]))
        off += L

def census(hexes, verbose=False, focus=None):
    tot = tokd = named = 0
    undec = collections.Counter()
    unnamed = collections.Counter()
    per = {}
    for name, hx in hexes.items():
        if focus and focus not in name:
            continue
        b = bytes.fromhex(hx)
        kt = ktk = knm = 0
        toks = []
        for off, L, nm, tb in walk(b):
            if L is None:
                undec[tb[0]] += 2
                kt += 2
                toks.append((off, None, False, tb))
            else:
                kt += L; ktk += L
                if nm: knm += L
                else: unnamed[tb[0]] += L
                toks.append((off, L, nm, tb))
        per[name] = (kt, ktk, knm)
        tot += kt; tokd += ktk; named += knm
        if verbose:
            print(f"\n===== {name}  ({kt}B, tokenized {100*ktk/kt:.1f}%, named {100*knm/kt:.1f}%) =====")
            for off, L, nm, tb in toks:
                tag = ""
                b0 = tb[0]
                if L is None: tag = f"  <== UNDECODED byte0={b0:#04x}"
                elif not nm:  tag = f"  <-- length-known, UNNAMED byte0={b0:#04x}"
                mark = {0x0f:"0F-CF",0x17:"BALLOT/UNPACK",0x47:"SHUF",0xc7:"SHUF",0xcf:"MATRIX",
                        0xbf:"REDUCE",0x3f:"REDUCE",0x04:"RT?",0xea:"RT",0xdf:"RT-LOAD"}.get(b0,"")
                if mark: tag += f"  [{mark}]"
                print(f"  +0x{off:03x} len={str(L):>4} {tb.hex():<28s}{tag}")
    print(f"\n==================== AGGREGATE ====================")
    print(f"total instruction bytes : {tot}")
    print(f"tokenized (length known): {tokd}  = {100*tokd/tot:.1f}%")
    print(f"descriptor-named        : {named}  = {100*named/tot:.1f}%")
    print(f"per-kernel:")
    for name,(kt,ktk,knm) in per.items():
        print(f"  {name:22s} {kt:5d}B  tok {100*ktk/kt:5.1f}%  named {100*knm/kt:5.1f}%")
    print(f"\nUNDECODED (length-None) byte0 histogram (bytes):")
    for b0,c in undec.most_common():
        print(f"  byte0={b0:#04x}  {c}B")
    print(f"\nlength-known but UNNAMED byte0 histogram (bytes):")
    for b0,c in unnamed.most_common():
        print(f"  byte0={b0:#04x}  {c}B")

def load(path):
    h = {}
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) == 2:
                h[p[0]] = p[1]
    return h

if __name__ == "__main__":
    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    opts  = [a for a in sys.argv[1:] if a.startswith("-")]
    verbose = "-v" in opts
    focus = None
    for o in opts:
        if o.startswith("--focus="): focus = o.split("=",1)[1]
    hexes = {}
    for fp in files:
        hexes.update(load(fp))
    census(hexes, verbose=verbose, focus=focus)
