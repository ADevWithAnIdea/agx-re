#!/usr/bin/env python3
# For a target byte0, over both corpora, for each undec-leader occurrence compute
# the smallest L>=2 where off+L decodes to a REAL (non-filler) NAMED op. Bucket by
# a signature (default byte+2). Reveals the true op extent per sub-encoding.
import sys, os, glob, collections, hashlib, argparse
sys.path.insert(0, os.path.expanduser("~/cleanroom_work/tools/agx-isa-m5"))
import isadb
FILLER={'operand_word','pad_operand'}
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
def real_named_at(buf,off,n):
    L=isadb.instr_length(buf,off)
    if L is None or off+L>n: return None
    try:
        rec,_=isadb.decode_one(buf,off)
        return (L, rec['mnemonic'])
    except ValueError:
        return (L, None)
def walk(buf):
    recs=[];off=0;n=len(buf)
    while off<n:
        r=real_named_at(buf,off,n)
        if r is not None:
            L,mn=r; recs.append((off,buf[off],L,mn,'named' if mn else 'raw'));off+=L;continue
        st=off;off+=2
        while off<n:
            r2=real_named_at(buf,off,n)
            if r2 is not None and r2[1] is not None: break
            off+=2
        recs.append((st,buf[st],off-st,None,'undec'))
    return recs
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dirs',nargs='+')
    ap.add_argument('--b0',required=True)
    ap.add_argument('--sig',default='b2',choices=['b1','b2','b3','b1hi','b3lo'])
    args=ap.parse_args()
    b0t=int(args.b0,16)
    progs=[]
    for d in args.dirs: progs+=load(d)
    # per-signature: histogram of smallest-real-resync-L
    bysig=collections.defaultdict(collections.Counter)
    sigtot=collections.Counter()
    for buf in progs:
        n=len(buf); recs=walk(buf)
        for i,(off,b0,L,mn,stt) in enumerate(recs):
            if stt!='undec' or b0!=b0t: continue
            b1=buf[off+1] if off+1<n else -1
            b2=buf[off+2] if off+2<n else -1
            b3=buf[off+3] if off+3<n else -1
            sig={'b1':b1,'b2':b2,'b3':b3,'b1hi':(b1>>4)&0xf if b1>=0 else -1,'b3lo':b3&0xf if b3>=0 else -1}[args.sig]
            # smallest L where a REAL named op begins
            found=None
            for L2 in range(2,20,2):
                if off+L2>n: break
                r=real_named_at(buf,off+L2,n)
                if r is not None and r[1] is not None:
                    found=L2; break
            bysig[sig][found]+=1; sigtot[sig]+=1
    print("byte0=0x%02x  sig=%s  (smallest-L-to-REAL-named-op histogram per sig value)"%(b0t,args.sig))
    for sig,c in sigtot.most_common(20):
        dist=dict(bysig[sig].most_common())
        print("  sig=0x%02x n=%4d  L-dist=%s"%(sig&0xff if sig>=0 else 0, c, dist))
if __name__=='__main__': main()
