#!/usr/bin/env python3
# solve.py — anchored region solver to recover TRUE instruction boundaries.
# Trust only high-confidence "anchor" ops (distinctive multi-byte signatures).
# Between consecutive anchors, DFS-tile the gap: each op's allowed lengths come
# from a per-signature hypothesis map (sig = (b0&0x0f, b2)); unknown sigs allow
# all even lengths 2..16. If exactly ONE tiling bridges the gap, its boundaries
# are ground truth; harvest (sig -> length) from it. Iterate to convergence.
# CLEAN-ROOM: our own shader bytes only.
import sys, os, glob, collections
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
sys.path.insert(0, '/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census')
import isadb, agxparse

HEXDIR = '/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census/hex'

def trim(b):
    end=len(b)
    while end>=2 and b[end-2:end]==b'\x06\x00': end-=2
    return b[:end]

def B(b,off,k): return b[off+k] if 0<=off+k<len(b) else -1

# ---- HIGH-CONFIDENCE anchors: return (length, name) or None -------------------
def anchor(b, off):
    n=len(b); b0=b[off]
    def ok(L): return off+L<=n
    if b0==0x0e and B(b,off,1)==0 and B(b,off,2)==0:
        if ok(4): return 4,'stop'
    if b0==0x67 and B(b,off,1) in (0x00,0x10) and B(b,off,2) in (0x44,0x54,0x56) and ok(14):
        return 14,'device_load'
    if b0==0xe7 and B(b,off,1)==0x00 and B(b,off,2) in (0x54,0x56) and ok(14):
        return 14,'device_store'
    if b0==0xa7 and B(b,off,1)==0x07 and ok(8): return 8,'cvt_i2f'
    if b0==0x27 and B(b,off,1)==0x07 and ok(10): return 10,'cvt_f2i'
    # get_sr: 0xNc a0 10 06 style OR 0xN4 .. with byte+3 low nibble 6
    if (b0&0x07)==0x04 and B(b,off,1) not in (0xea,) and B(b,off,1)&0x0f==0x0 and (B(b,off,3)&0x0f)==0x06 and B(b,off,2)==0x10 and ok(4):
        return 4,'get_sr'
    # iadd2 / imad: 0x9f/0x1f, byte+2 in {0x54,0x56}
    if b0 in (0x9f,0x1f) and B(b,off,2) in (0x54,0x56):
        if (B(b,off,1)&0x01)==1 and ok(10): return 10,'iadd2'
        if (B(b,off,1)&0x01)==0 and ok(12): return 12,'imad'
    return None

def load(binpath, stage='compute'):
    buf=open(binpath,'rb').read()
    _,st=agxparse.extract_all_stages(buf)
    return trim(st[stage]['_agc.main'])

CAND=(2,4,6,8,10,12,14,16,18,20)

def tile(b, start, end, hyp):
    """Return list of ALL tilings (each a list of (off,len)) of [start,end)."""
    results=[]
    def dfs(off, acc):
        if off==end:
            results.append(list(acc)); return
        if off>end or len(results)>8: return
        b0=b[off]; b2=B(b,off,2); sig=(b0&0x0f, b2)
        allowed = hyp.get(sig)
        if allowed is None:
            # also try a length that lands on an anchor (helps unknowns)
            allowed = CAND
        else:
            allowed = (allowed,)
        for L in allowed:
            if off+L<=end:
                acc.append((off,L)); dfs(off+L,acc); acc.pop()
    dfs(start,[])
    return results

def solve_kernel(b, hyp):
    """Walk anchors; between anchors, tile. Return (boundaries, harvested sigs, ambiguous_gaps)."""
    n=len(b); off=0
    # find anchor positions by scanning; but anchors are only trusted when reached in-sequence.
    bounds=[]; harvest=collections.Counter(); amb=0; gapsolved=0
    while off<n:
        a=anchor(b,off)
        if a:
            L,name=a; bounds.append((off,L,name)); off+=L; continue
        # gap until next anchor position
        # find the next offset >off that is an anchor AND reachable
        nxt=None
        probe=off+2
        while probe<=n:
            if probe==n or anchor(b,probe):
                nxt=probe; break
            probe+=2
        if nxt is None: nxt=n
        tilings=tile(b, off, nxt, hyp)
        if len(tilings)==1:
            for (o,L) in tilings[0]:
                b0=b[o]; b2=B(b,o,2); bounds.append((o,L,f'gap:{b0:02x}/{b2:02x}'))
                harvest[(b0&0x0f,b2)] += 1 if hyp.get((b0&0x0f,b2)) is None else 0
            gapsolved+=1
        else:
            bounds.append((off,nxt-off,f'AMBIG({len(tilings)})')); amb+=1
        off=nxt
    return bounds, harvest, amb, gapsolved

# harvested length per sig: from unique tilings, record the observed length
def harvest_lengths(b, hyp):
    n=len(b); off=0; found={}
    while off<n:
        a=anchor(b,off)
        if a: off+=a[0]; continue
        nxt=None; probe=off+2
        while probe<=n:
            if probe==n or anchor(b,probe): nxt=probe; break
            probe+=2
        if nxt is None: nxt=n
        tilings=tile(b,off,nxt,hyp)
        if len(tilings)==1:
            for (o,L) in tilings[0]:
                sig=(b[o]&0x0f, B(b,o,2))
                found.setdefault(sig, set()).add(L)
        off=nxt
    return found

if __name__=='__main__':
    import glob
    binp=sys.argv[1] if len(sys.argv)>1 else None
    hyp={}
    if binp:
        b=load(binp)
        bounds,harv,amb,gs=solve_kernel(b,hyp)
        for (o,L,nm) in bounds:
            print(f"  @{o:4d} L={L:2d} {nm}   {b[o:o+L].hex(' ')}")
        print(f"gaps solved={gs} ambiguous={amb}")
