#!/usr/bin/env python3
# regress.py -- apply the proposed instr_length overrides to EVERY corpus hex and
# report undecoded-byte deltas, to prove the S3 residues close with no regression.
import sys, os, glob
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
HEXDIR=os.path.join(_REPO, 'experiments', 'EXP-M4-01-isa-census', 'census', 'hex')

def trim(b):
    while len(b)>=2 and b[-2:]==b'\x06\x00': b=b[:-2]
    return b

def override(buf, off):
    b0=buf[off]; lo=b0&0x0f
    def g(k): return buf[off+k] if off+k<len(buf) else -1
    # 1. low-nibble-2 b2==0x25: register srcC (b4 bit1 clear) -> 8, else imm-select -> 10
    if lo==2 and g(2)==0x25:
        return 8 if (g(4)&0x02)==0 else 10
    # 2. low-nibble-2 icmpsel REGISTER-select (b2==0x2d & b3==0x80) -> 10 (const-form b2=0x1d/b3=0x05 stays 14)
    if lo==2 and g(2)==0x2d and g(3)==0x80:
        return 10
    # 3. low-nibble-b int-logic mask (b2==0x17) -> 10
    if lo==0x0b and g(2)==0x17:
        return 10
    # 4. low-nibble-0 half combine op (b2==0x39) -> 10
    if lo==0 and b0 not in (0x00,0x30,0x90,0xb0) and g(2)==0x39:
        return 10
    # 5. 0x87 BARE compute fence (b1==0x00, 0<b2<0x80 => b2 is next op's byte0) -> 2
    if b0==0x87 and g(1)==0x00 and 0<g(2)<0x80:
        return 2
    # 6. psel high-predicate-register variant (b0==0x85, tail 20 80) -> 4
    if b0==0x85 and g(2)==0x20 and g(3)==0x80:
        return 4
    # 7. 0x12 compare/select with op-select 0x3f -> 8
    if b0==0x12 and g(2)==0x3f:
        return 8
    # 8. 0x17 unpack_convert (byte+1 low-nibble 4) -> 8 (simd_ballot byte+1 low-nibble 7 stays 10)
    if b0==0x17 and (g(1)&0x0f)==0x04:
        return 8
    return None

def Lat(buf, off, use_ov):
    if use_ov:
        v=override(buf,off)
        if v is not None: return v
    return isadb.instr_length(buf, off)

def undecoded(b, use_ov):
    n=len(b); off=0; total=0; gaps=[]
    while off<n:
        L=Lat(b,off,use_ov)
        if L is None or off+L>n:
            start=off; off+=2
            while off<n:
                L2=Lat(b,off,use_ov)
                if L2 is not None and off+L2<=n:
                    try:
                        isadb.decode_one(b,off); break
                    except ValueError: pass
                off+=2
            total+=off-start; gaps.append((start,off-start))
        else:
            off+=L
    return total, gaps

def main():
    files=sorted(glob.glob(os.path.join(HEXDIR,'*.hex')))
    worse=[]; better=[]
    for f in files:
        name=os.path.basename(f)[:-4]
        h=open(f).read().strip()
        if not h: continue
        b=trim(bytes.fromhex(h))
        u0,_=undecoded(b, False)
        u1,g1=undecoded(b, True)
        flag=''
        if u1<u0: better.append((name,u0,u1)); flag='  <-- IMPROVED'
        if u1>u0: worse.append((name,u0,u1,g1)); flag='  *** REGRESSED ***'
        if u0 or u1:
            print(f"{name:26s} before={u0:4d}  after={u1:4d}{flag}")
    print("\n==== SUMMARY ====")
    print(f"improved: {len(better)}   regressed: {len(worse)}")
    for w in worse:
        print("REGRESSION", w)

if __name__=='__main__':
    main()
