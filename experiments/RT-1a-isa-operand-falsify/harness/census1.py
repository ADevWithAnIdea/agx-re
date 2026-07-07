#!/usr/bin/env python3
# Resync census over one _agc.main hex (given as argv or read big.bin). Reports
# coverage, and enumerates: named ops, LENGTH_ONLY (length rule fires but NO DB
# descriptor -> mis-decode), and UNDECODED (no length rule) byte0 leaders.
import sys, os, subprocess, collections
sys.path.insert(0,'/Users/user/cleanroom_work/rt1a')
import isadb

def named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off+L > n: return None, None
    try:
        rec,_ = isadb.decode_one(buf, off); return L, rec['mnemonic']
    except ValueError:
        return L, None

def walk(buf):
    recs=[]; off=0; n=len(buf)
    while off<n:
        b0=buf[off]; L,mn=named_at(buf,off,n)
        if L is not None:
            recs.append((off,b0,L,mn,'named' if mn else 'length_only')); off+=L; continue
        start=off; off+=2
        while off<n:
            L2,mn2=named_at(buf,off,n)
            if mn2 is not None: break
            off+=2
        recs.append((start,b0,off-start,None,'undecoded'))
    return recs

arch=sys.argv[1] if len(sys.argv)>1 else "big.bin"
sym=sys.argv[2] if len(sys.argv)>2 else "_agc.main"
hexs=subprocess.check_output(["python3","agxparse.py",arch,"--extract-hex","--symbol",sym],text=True).strip()
# trim trailing 06 00 padding
b=bytearray.fromhex(hexs)
while len(b)>=2 and b[-2:]==b'\x06\x00': b=b[:-2]
b=bytes(b)
recs=walk(b)
named=sum(1 for r in recs if r[4]=='named')
lenonly=[r for r in recs if r[4]=='length_only']
undec=[r for r in recs if r[4]=='undecoded']
cov=sum(r[2] for r in recs if r[4] in('named','length_only'))
undbytes=sum(r[2] for r in undec)
print(f"total bytes={len(b)} instrs={len(recs)} named={named} length_only={len(lenonly)} undecoded={len(undec)}")
print(f"byte coverage(named+lenonly)={cov}/{len(b)} = {100*cov/len(b):.1f}%  undecoded_bytes={undbytes} ({100*undbytes/len(b):.1f}%)")
print("--- LENGTH_ONLY (length rule fires, NO descriptor = MIS-DECODE): byte0 -> count, sample ---")
lc=collections.Counter(); ls={}
for off,b0,L,mn,st in lenonly:
    lc[b0]+=1; ls.setdefault(b0,b[off:off+min(L,8)].hex(' '))
for b0,c in lc.most_common():
    print(f"  byte0=0x{b0:02x} count={c} sample={ls[b0]}")
print("--- UNDECODED (no length rule) byte0 leaders -> count, 16B sample ---")
uc=collections.Counter(); us={}
for off,b0,L,mn,st in undec:
    uc[b0]+=1; us.setdefault(b0,b[off:off+16].hex(' '))
for b0,c in uc.most_common():
    print(f"  byte0=0x{b0:02x} count={c} sample={us[b0]}")
