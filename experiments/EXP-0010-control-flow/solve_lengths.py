#!/usr/bin/env python3
# solve_lengths.py -- EXP-0010 (host-side analysis). Deduce byte-lengths of NEW
# control-flow opcodes by anchoring on already-solved instructions and DP over
# valid instruction boundaries (reach-from-start AND reach-to-end). For each
# occurrence of an unknown opcode, the feasible lengths are those landing on a
# valid downstream boundary; intersect across all our own programs.
# CLEAN-ROOM: only OUR OWN compiled bytes are analysed.
import sys, re

def known_len(b, off):
    b0 = b[off]; lo = b0 & 0x0f
    if b0 == 0x0e: return 4
    if lo == 0x0c: return 4
    if b0 in (0x67, 0xe7): return 14
    if lo == 0x09: return 8 if (off+2 < len(b) and b[off+2] & 0x02) else 6
    if lo == 0x0b: return 10
    if b0 in (0x9f, 0x1f, 0xa7): return 10 if (off+1 < len(b) and b[off+1] & 0x01) else 12
    if b0 == 0x27: return 8
    if b0 == 0x02: return 6
    if b0 == 0x12: return 14 if (off+2 < len(b) and (b[off+2] & 0x0f) == 0x0d) else 6
    return None

CAND_LENS = [2,4,6,8,10,12,14,16]

def compute_reach_end(b):
    n = len(b)
    reach = [False]*(n+1)
    reach[n] = True
    for off in range(n-1, -1, -1):
        L = known_len(b, off)
        if L is not None:
            reach[off] = (off+L <= n and reach[off+L])
        else:
            reach[off] = any(off+L2 <= n and reach[off+L2] for L2 in CAND_LENS)
    return reach

def compute_reach_start(b):
    n = len(b)
    reach = [False]*(n+1)
    reach[0] = True
    for off in range(0, n):
        if not reach[off]:
            continue
        L = known_len(b, off)
        if L is not None:
            if off+L <= n: reach[off+L] = True
        else:
            for L2 in CAND_LENS:
                if off+L2 <= n: reach[off+L2] = True
    return reach

def feasible_lengths(b):
    """Return {byte0: set(lengths)} for unknown opcodes at valid boundaries."""
    n = len(b)
    re_end = compute_reach_end(b)
    re_start = compute_reach_start(b)
    valid = [re_start[o] and re_end[o] for o in range(n+1)]
    out = {}
    for off in range(n):
        if not valid[off]:
            continue
        if known_len(b, off) is not None:
            continue
        b0 = b[off]
        opts = set()
        for L in CAND_LENS:
            if off+L <= n and valid[off+L]:
                opts.add(L)
        out.setdefault(b0, set())
        if not out[b0]:
            out[b0] = opts
        else:
            # union across occurrences within a program (each occurrence any),
            # but we want intersection of "possible" -> keep union here; cross
            # program intersection handled by caller.
            out[b0] |= opts
    return out

def segment(b, hyp):
    off=0; out=[]; n=len(b)
    while off<n:
        L=known_len(b,off)
        if L is None: L=hyp.get(b[off])
        if L is None or off+L>n: return None
        out.append((off,L,b[off])); off+=L
    return out

def main():
    logs = sys.argv[1:] or ["raw/dump_nofast.log"]
    prog={}; name=None
    for logpath in logs:
        for line in open(logpath):
            m=re.match(r"=== (\S+)",line)
            if m: name=m.group(1)
            m=re.search(r"main:\s+([0-9a-f]+)",line)
            if m and name: prog[name+":"+logpath]=bytes.fromhex(m.group(1))
    print(f"loaded {len(prog)} programs")

    # Per program: unique-length opcodes are strong constraints. Intersect the
    # "must be" sets: an opcode's true length must be feasible in EVERY program
    # where it appears at a forced boundary. Use programs where the opcode has a
    # SINGLE feasible length as ground truth.
    global_feas={}
    forced={}
    for nm,b in prog.items():
        fl=feasible_lengths(b)
        for b0,s in fl.items():
            if b0 in global_feas: global_feas[b0]&=s if s else global_feas[b0]
            else: global_feas[b0]=set(s)
            if len(s)==1:
                forced.setdefault(b0,set()).add(next(iter(s)))
    print("\n=== opcodes forced to a UNIQUE length in some program ===")
    for b0 in sorted(forced):
        vals=forced[b0]
        tag = "" if len(vals)==1 else "  <-- CONFLICT"
        print(f"  byte0 {b0:#04x}: {sorted(vals)}{tag}")
    print("\n=== intersection of feasible lengths across all programs ===")
    for b0 in sorted(global_feas):
        print(f"  byte0 {b0:#04x}: {sorted(global_feas[b0])}")

    # Build best hyp: prefer forced unique, else min of intersection.
    hyp={}
    for b0 in global_feas:
        if b0 in forced and len(forced[b0])==1:
            hyp[b0]=next(iter(forced[b0]))
        elif global_feas[b0]:
            hyp[b0]=min(global_feas[b0])
    print("\n=== chosen hyp ===", {hex(k):v for k,v in sorted(hyp.items())})
    print("\n=== segmentations ===")
    for nm in sorted(prog):
        b=prog[nm]; seg=segment(b,hyp)
        if seg is None: print(f"{nm}: NO CLEAN SEG"); continue
        print(f"{nm.split(':')[0]:12s} ({len(b)}B): "+"  ".join(f"{b0:02x}/{L}" for _,L,b0 in seg))

if __name__=="__main__":
    main()
