#!/usr/bin/env python3
# ab.py — A/B test a length-rule override against the whole corpus + a chosen
# kernel walk, WITHOUT editing isadb.py. Monkeypatches isadb.instr_length.
# CLEAN-ROOM: our own shader bytes only.
import sys, os, glob
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb

HEXDIR = '/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census/hex'
A18DIR = '/Users/user/cleanroom_gpu/experiments/EXP-0036-consolidation-census/hex'
_orig = isadb.instr_length

def trim(b):
    end=len(b)
    while end>=2 and b[end-2:end]==b'\x06\x00': end-=2
    return b[:end]

def named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off+L>n: return None,None
    try:
        rec,_=isadb.decode_one(buf,off); return L,rec['mnemonic']
    except ValueError: return L,None

def walk_counts(b):
    n=len(b); off=0; undec=0; undec_bytes=0; instr=0
    while off<n:
        L=isadb.instr_length(b,off)
        if L is not None and off+L<=n:
            off+=L; instr+=1; continue
        start=off; off+=2
        while off<n:
            _,mn2=named_at(b,off,n)
            if mn2 is not None: break
            off+=2
        undec+=1; undec_bytes+=off-start; instr+=1
    return instr, undec, undec_bytes

def census(hexdir):
    files=sorted(glob.glob(os.path.join(hexdir,'*.hex')))
    seen=set(); ti=tu=tub=tb=0; groups={}
    for f in files:
        h=open(f).read().strip()
        if not h: continue
        b=trim(bytes.fromhex(h))
        hh=hash(b)
        if hh in seen: continue
        seen.add(hh)
        i,u,ub=walk_counts(b); ti+=i; tu+=u; tub+=ub; tb+=len(b)
    return ti,tu,tub,tb

def group_report(hexdir):
    import collections
    files=sorted(glob.glob(os.path.join(hexdir,'*.hex')))
    seen=set(); byte0_undec=collections.Counter(); samples={}
    for f in files:
        h=open(f).read().strip()
        if not h: continue
        b=trim(bytes.fromhex(h)); hh=hash(b)
        if hh in seen: continue
        seen.add(hh)
        n=len(b); off=0
        while off<n:
            b0=b[off]; L=isadb.instr_length(b,off)
            if L is not None and off+L<=n: off+=L; continue
            start=off; off+=2
            while off<n:
                _,mn2=named_at(b,off,n)
                if mn2 is not None: break
                off+=2
            byte0_undec[b0]+=1; samples.setdefault(b0,b[start:start+16].hex(' '))
    return byte0_undec, samples

def report(tag):
    ti,tu,tub,tb=census(HEXDIR)
    print(f"[{tag}] M4 : instr={ti} undec_groups={tu} undec_bytes={tub}/{tb} ({100*(tb-tub)/tb:.1f}% bytes, {100*(ti-tu)/ti:.1f}% tokens)")
    try:
        ai,au,aub,ab_=census(A18DIR)
        print(f"[{tag}] A18: instr={ai} undec_groups={au} undec_bytes={aub}/{ab_} ({100*(ab_-aub)/ab_:.1f}% bytes, {100*(ai-au)/ai:.1f}% tokens)")
    except Exception as e:
        print(f"[{tag}] A18: (skip: {e})")

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='groups':
        g,s=group_report(HEXDIR)
        for b0,c in g.most_common():
            print(f"  0x{b0:02x}: count={c:3d}  {s[b0]}")
    else:
        report('baseline')
