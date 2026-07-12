#!/usr/bin/env python3
# Derive which byte0 values are NEVER the leader of a SPECIFIC non-loose real op in the
# ALIGNED stream (step5 fork), and which byte0 DO lead real ops. A byte0 that only ever
# appears as an undec/filler leader is safe to chain-step over. Also report, for each
# candidate filler byte0, how its undec occurrences resync (to confirm it's a 2-byte word).
import sys, os, glob, hashlib, collections
sys.path.insert(0, os.path.expanduser("~/cleanroom_work/tools/agx-isa-m5"))
import isadb
LOOSE=isadb._M5_LOOSE
def trim(b):
    e=len(b)
    while e>=2 and b[e-2:e]==b'\x06\x00': e-=2
    return b[:e]
def load(d):
    s={}
    for fp in sorted(glob.glob(os.path.join(d,"*.hex"))):
        try:h=open(fp).read().strip()
        except:continue
        if not h:continue
        try:b=trim(bytes.fromhex(h))
        except:continue
        k=hashlib.sha256(b).hexdigest()
        if k not in s:s[k]=b
    return list(s.values())
def named_at(buf,off,n):
    L=isadb.instr_length(buf,off)
    if L is None or off+L>n: return None,None
    try: rec,_=isadb.decode_one(buf,off); return L,rec['mnemonic']
    except ValueError: return L,None
def walk(buf):
    recs=[];off=0;n=len(buf)
    while off<n:
        L,mn=named_at(buf,off,n)
        if L is not None: recs.append((off,buf[off],L,mn,'named' if mn else 'raw'));off+=L;continue
        st=off;off+=2
        while off<n:
            L2,mn2=named_at(buf,off,n)
            if mn2 is not None: break
            off+=2
        recs.append((st,buf[st],off-st,None,'undec'))
    return recs
progs=[]
for d in sys.argv[1:]: progs+=load(d)
real_leader=collections.Counter()   # byte0 -> count as non-loose named leader
undec_leader=collections.Counter()  # byte0 -> count as undec leader
for buf in progs:
    for off,b0,L,mn,st in walk(buf):
        if st=='named' and mn not in LOOSE: real_leader[b0]+=1
        elif st=='undec': undec_leader[b0]+=1
allb0=set(real_leader)|set(undec_leader)
pure_filler=sorted(b0 for b0 in undec_leader if real_leader.get(b0,0)==0)
mixed=sorted(b0 for b0 in undec_leader if 0<real_leader.get(b0,0))
print("PURE-FILLER byte0 (undec only, NEVER a non-loose real leader) -- safe to chain over:")
print("  ",[ "0x%02x(%d)"%(b,undec_leader[b]) for b in sorted(pure_filler,key=lambda x:-undec_leader[x]) ])
print("MIXED byte0 (both real-leader AND undec) -- do NOT chain over (real op family):")
print("  ",[ "0x%02x(u%d/r%d)"%(b,undec_leader[b],real_leader[b]) for b in sorted(mixed,key=lambda x:-undec_leader[x])[:30] ])
# low-nibble summary of pure fillers
ln=collections.Counter()
for b in pure_filler: ln[b&0xf]+=undec_leader[b]
print("pure-filler undec by low-nibble:", dict(sorted(ln.items(),key=lambda kv:-kv[1])))
