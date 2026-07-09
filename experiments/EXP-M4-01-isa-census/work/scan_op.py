#!/usr/bin/env python3
# scan_op.py <byte0hex...> -- across the corpus, find every IN-SEQUENCE occurrence
# of an op whose byte0 is in the given set, print byte+1/+2, current length, and the
# NEXT op's byte0 (to sanity-check the length by what follows). Only reports ops the
# walk reaches in-sequence (i.e. real instruction heads), not resync interiors.
# CLEAN-ROOM: our own compiled shader bytes only.
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
sys.path.insert(0, os.path.join(_REPO, 'tools', 'agx-isa'))
import isadb
HEXDIR = os.path.join(_REPO, 'experiments', 'EXP-M4-01-isa-census', 'census', 'hex')
def trim(b):
    e=len(b)
    while e>=2 and b[e-2:e]==b'\x06\x00': e-=2
    return b[:e]
def named_at(buf,off,n):
    L=isadb.instr_length(buf,off)
    if L is None or off+L>n: return None,None
    try: rec,_=isadb.decode_one(buf,off); return L,rec['mnemonic']
    except ValueError: return L,None
targets = set(int(x,16) for x in sys.argv[1:]) if len(sys.argv)>1 else {0xa7,0x27}
hist = collections.Counter()
samples = collections.defaultdict(list)
for f in sorted(glob.glob(os.path.join(HEXDIR,'*.hex'))):
    name=os.path.basename(f)[:-4]; h=open(f).read().strip()
    if not h: continue
    b=trim(bytes.fromhex(h)); n=len(b); off=0
    while off<n:
        L=isadb.instr_length(b,off)
        if L is not None and off+L<=n:
            b0=b[off]
            if b0 in targets:
                b1=b[off+1] if off+1<n else -1
                b2=b[off+2] if off+2<n else -1
                nxt=b[off+L] if off+L<n else -1
                key=(b0,b1)
                hist[key]+=1
                if len(samples[key])<3:
                    samples[key].append((name,off,L,b2,nxt,b[off:off+min(L+2,16)].hex(' ')))
            off+=L; continue
        off+=2  # skip undecoded interior
print(f"scan byte0 in {sorted(hex(t) for t in targets)}:")
for (b0,b1),c in sorted(hist.items()):
    print(f"  {b0:02x} {b1:02x}  n={c:3d}")
    for (name,off,L,b2,nxt,hx) in samples[(b0,b1)]:
        print(f"      {name}@{off} L={L} b2={b2:02x} next=0x{nxt:02x}  {hx}")
