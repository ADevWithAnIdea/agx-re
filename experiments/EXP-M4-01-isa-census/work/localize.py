#!/usr/bin/env python3
# localize.py — walk each corpus stream with the DB, using anchors as checkpoints.
# When the DB walk does NOT land exactly on the next anchor (desync in a gap),
# brute-force the MINIMAL single-op length correction that makes the gap tile from
# its start to the next anchor using DB lengths for all OTHER ops. Report the op
# whose DB length is wrong and its corrected length. CLEAN-ROOM: own shaders only.
import sys, os, glob, collections
# --- portable repo root (repo was relocated; anchor to a sentinel, not a hardcoded path) ---
import os
def _repo_root(start):
    d = os.path.abspath(start)
    while d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, 'CLAUDE.md')) and os.path.isdir(os.path.join(d, 'tools', 'agx-isa')):
            return d
        d = os.path.dirname(d)
    raise RuntimeError('repo root not found from ' + start)
_REPO = _repo_root(os.path.dirname(os.path.abspath(__file__)))
# --- end portable repo root ---
sys.path.insert(0,os.path.join(_REPO, 'tools', 'agx-isa'))
sys.path.insert(0,os.path.join(_REPO, 'experiments', 'EXP-M4-01-isa-census', 'census'))
import isadb, solve

HEXDIR=os.path.join(_REPO, 'experiments', 'EXP-M4-01-isa-census', 'census', 'hex')
A18DIR=os.path.join(_REPO, 'experiments', 'EXP-0036-consolidation-census', 'hex')

def dbl(b,off):
    L=isadb.instr_length(b,off)
    if L is None or off+L>len(b): return None
    return L

def anchors_of(b):
    """positions that are anchors, walking from 0 with DB, but validated as anchor."""
    n=len(b); res=[]
    off=0
    while off<n:
        a=solve.anchor(b,off)
        if a: res.append((off,off+a[0])); off+=a[0]
        else: off+=2   # scan
    return res

def next_anchor_at_or_after(b, pos):
    n=len(b)
    while pos<=n:
        if pos==n: return n
        a=solve.anchor(b,pos)
        if a: return pos
        pos+=2
    return n

def db_walk_reaches(b, start, target):
    """Walk with DB lengths from start; return True if lands exactly on target."""
    off=start
    while off<target:
        L=dbl(b,off)
        if L is None: return False
        off+=L
    return off==target

def find_gap_fix(b, start, target, tries):
    """Brute force: which single op (position) in [start,target), if its length
       is changed to some candidate, makes the DB-walk reach target? Returns list
       of (pos, dblen, fixed_len, sig)."""
    fixes=[]
    # get the DB walk op positions until it desyncs or passes target
    positions=[]
    off=start
    while off<target+40:
        positions.append(off)
        L=dbl(b,off)
        if L is None:
            break
        off+=L
        if off>=target: break
    # try changing each op's length
    for i,pos in enumerate(positions):
        Lorig=dbl(b,pos)
        for cand in (2,4,6,8,10,12,14,16,18,20):
            if cand==Lorig: continue
            # walk with DB up to pos, then cand at pos, then DB after
            off=start; ok=True
            while off<pos:
                L=dbl(b,off)
                if L is None: ok=False; break
                off+=L
            if not ok or off!=pos: continue
            off=pos+cand
            while off<target:
                L=dbl(b,off)
                if L is None: ok=False; break
                off+=L
            if ok and off==target:
                sig=(b[pos]&0x0f, b[pos+2] if pos+2<len(b) else -1)
                fixes.append((pos, Lorig, cand, sig, b[pos:pos+cand].hex(' ')))
    return fixes

def main(which):
    hexdir = HEXDIR if which=='m4' else A18DIR
    seen=set(); allfixes=collections.Counter(); examples={}
    for f in sorted(glob.glob(os.path.join(hexdir,'*.hex'))):
        h=open(f).read().strip()
        if not h: continue
        b=solve.trim(bytes.fromhex(h)); hh=hash(b)
        if hh in seen: continue
        seen.add(hh)
        name=os.path.basename(f)[:-4]
        # find anchor checkpoints
        n=len(b); off=0
        while off<n:
            a=solve.anchor(b,off)
            if a: off+=a[0]; continue
            # gap start = off; find next anchor
            tgt=next_anchor_at_or_after(b, off+2)
            # does DB reach tgt from off?
            if db_walk_reaches(b, off, tgt):
                # advance by DB to tgt
                off=tgt; continue
            # desync: localize
            fixes=find_gap_fix(b, off, tgt, 10)
            uniq=set((p,c,sig) for (p,l,c,sig,hx) in fixes)
            for (p,l,c,sig,hx) in fixes:
                allfixes[(sig[0],sig[1],l,c)] += 1
                examples.setdefault((sig[0],sig[1],l,c), (name,p,hx))
            off=tgt
    print(f"[{which}] candidate single-op length corrections (b0lo, b2, dblen->fixed): count")
    for (ln,b2,l,c),cnt in allfixes.most_common(40):
        nm,p,hx=examples[(ln,b2,l,c)]
        print(f"  b0lo={ln:x} b2={b2:02x}  {l}->{c}  x{cnt:3d}   e.g. {nm}@{p}: {hx}")

if __name__=='__main__':
    main(sys.argv[1] if len(sys.argv)>1 else 'm4')
