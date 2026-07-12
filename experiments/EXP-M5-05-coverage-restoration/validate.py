#!/usr/bin/env python3
# EXP-M5-05 validation census: walk a hex corpus with the FORK DB (agx-isa-m5),
# emit machine-readable coverage + FULL per-mnemonic named counts + per-byte0
# desync. Used to prove each length-rule change strictly reduces desync while NOT
# dropping any pre-existing REAL-op named count (the anti-chopping invariant).
# CLEAN-ROOM: own/permissive compiled bytes + our own fork DB only.
import sys, os, glob, hashlib, collections, json
sys.path.insert(0, os.path.expanduser("~/cleanroom_work/tools/agx-isa-m5"))
import isadb

def trim_padding(b):
    end=len(b)
    while end>=2 and b[end-2:end]==b'\x06\x00': end-=2
    return b[:end]

def load(hexdir):
    seen={}
    for fp in sorted(glob.glob(os.path.join(hexdir,"*.hex"))):
        try: h=open(fp).read().strip()
        except Exception: continue
        if not h: continue
        try: buf=trim_padding(bytes.fromhex(h))
        except ValueError: continue
        sig=hashlib.sha256(buf).hexdigest()
        if sig not in seen: seen[sig]=buf
    return list(seen.values())

def named_at(buf,off,n):
    L=isadb.instr_length(buf,off)
    if L is None or off+L>n: return None,None
    try:
        rec,_=isadb.decode_one(buf,off); return L,rec['mnemonic']
    except ValueError:
        return L,None

def walk(buf):
    recs=[]; off=0; n=len(buf)
    while off<n:
        b0=buf[off]
        L,mn=named_at(buf,off,n)
        if L is not None:
            recs.append((off,b0,L,mn,'named' if mn else 'raw')); off+=L; continue
        start=off; off+=2
        while off<n:
            L2,mn2=named_at(buf,off,n)
            if mn2 is not None: break
            off+=2
        recs.append((start,b0,off-start,None,'undec'))
    return recs

def main():
    dirs=sys.argv[1:]
    bufs=[]
    for d in dirs: bufs+=load(d)
    tot=named_b=raw_b=des_b=0
    mnem=collections.Counter()
    b0_des_regions=collections.Counter(); b0_des_bytes=collections.Counter()
    n_named=n_raw=n_des=0
    for buf in bufs:
        for off,b0,L,mn,st in walk(buf):
            if st=='named': named_b+=L; mnem[mn]+=1; n_named+=1
            elif st=='raw': raw_b+=L; n_raw+=1
            else: des_b+=L; b0_des_regions[b0]+=1; b0_des_bytes[b0]+=L; n_des+=1
        tot+=len(buf)
    out=dict(
        dirs=dirs, programs=len(bufs), total_bytes=tot,
        named_bytes=named_b, raw_bytes=raw_b, desync_bytes=des_b,
        cov_pct=100*(named_b+raw_b)/tot, desync_pct=100*des_b/tot,
        tokens=dict(named=n_named, raw=n_raw, desync=n_des),
        mnem=dict(mnem),
        byte0_desync={"0x%02x"%g: dict(regions=b0_des_regions[g], bytes=b0_des_bytes[g])
                      for g in sorted(b0_des_bytes, key=lambda x:-b0_des_bytes[x])},
    )
    print(json.dumps(out))

if __name__=='__main__': main()
