#!/usr/bin/env python3
# EXP-M5-05 leader analysis: for a target byte0 (or low-nibble), over the M5
# corpora, dump (a) region-length dist, (b) top predecessors, (c) (b0,b1[,b2])
# histogram, (d) for the FIRST undecoded op, which existing DB descriptor WOULD
# match at each candidate even length (relocated-match / missing-length-rule case),
# and (e) rich context samples [prev named op | UNDEC region | next named ops].
# CLEAN-ROOM: own compiled bytes + our own fork DB only.
import sys, os, glob, collections, argparse, hashlib
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
        if sig not in seen: seen[sig]=(os.path.basename(fp),buf)
    return list(seen.values())

def named_at(buf,off,n):
    L=isadb.instr_length(buf,off)
    if L is None or off+L>n: return None,None
    try:
        rec,_=isadb.decode_one(buf,off)
        return L,rec['mnemonic']
    except ValueError:
        return L,None

def walk(buf):
    recs=[]; off=0; n=len(buf)
    while off<n:
        b0=buf[off]
        L,mn=named_at(buf,off,n)
        if L is not None:
            recs.append((off,b0,L,mn,'named' if mn else 'length_only')); off+=L; continue
        start=off; off+=2
        while off<n:
            L2,mn2=named_at(buf,off,n)
            if mn2 is not None: break
            off+=2
        recs.append((start,b0,off-start,None,'undecoded'))
    return recs

def desc_matches_at(buf, off, L, n):
    """Return list of mnemonics of DB descriptors of length L that match bytes[off:off+L]."""
    if off+L>n: return []
    v=int.from_bytes(bytes(buf[off:off+L]),'little')
    out=[]
    for d in isadb.DB:
        if d["length"]==L and isadb._matches(d,v):
            out.append(d["mnemonic"])
    return out

def match_target(b0, spec):
    if spec.startswith('lo:'): return (b0 & 0x0f)==int(spec[3:],16)
    if spec.startswith('hi:'): return (b0>>4)==int(spec[3:],16)
    return b0==int(spec,16)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--target', required=True)  # '0x3e' | 'lo:e' | 'hi:3'
    ap.add_argument('--n', type=int, default=30)
    args=ap.parse_args()
    progs=[]
    for d in args.dirs: progs+=load(d)
    pred=collections.Counter(); reglen=collections.Counter()
    b1hist=collections.Counter(); b12hist=collections.Counter()
    would_match=collections.Counter()   # (L, mnem) -> count  for FIRST op in region
    would_len=collections.Counter()      # L -> count (any descriptor matches)
    samples=[]
    for name,buf in progs:
        recs=walk(buf); n=len(buf)
        for i,(off,b0,L,mn,st) in enumerate(recs):
            if st!='undecoded' or not match_target(b0,args.target): continue
            prev = recs[i-1][3] if i>0 else None
            pred[prev]+=1; reglen[L]+=1
            b1=buf[off+1] if off+1<n else -1
            b2=buf[off+2] if off+2<n else -1
            b1hist[(b0,b1)]+=1; b12hist[(b0,b1,b2)]+=1
            # probe candidate lengths for FIRST op
            hit=False
            for cand in (2,4,6,8,10,12,14,16):
                ms=desc_matches_at(buf,off,cand,n)
                if ms:
                    would_len[cand]+=1
                    for m in ms: would_match[(cand,m)]+=1
                    hit=True; break
            if not hit: would_len[None]+=1
            if len(samples)<args.n:
                # show prev op bytes + region + a bit past
                pstart=recs[i-1][0] if i>0 else off
                ctx=buf[off:off+min(L+8,24)].hex(' ')
                samples.append((name,off,L,prev,ctx))
    tot=sum(reglen.values())
    print(f"=== target={args.target}  undecoded regions matched: {tot} ===")
    print("region-length dist:", dict(reglen.most_common()))
    print("FIRST-op smallest matching descriptor length:", dict(would_len.most_common()))
    print("FIRST-op would-match (len,mnem):")
    for (L,m),c in would_match.most_common(14):
        print(f"    L={L:2d} {m:20s} {c}")
    print("top predecessors:", pred.most_common(10))
    print("top (b0,b1):", [(f'{a:02x}{b&0xff:02x}',c) for (a,b),c in b1hist.most_common(16)])
    print("top (b0,b1,b2):", [(f'{a:02x}{b&0xff:02x}{cc&0xff:02x}',c) for (a,b,cc),c in b12hist.most_common(16)])
    print("--- samples: [region bytes + 8B past] (prev-op | file) ---")
    for name,off,L,prev,ctx in samples:
        print(f"  L={L:2d} {ctx:56s}  <{prev or '?'} | {name[:34]}>")

if __name__=='__main__': main()
