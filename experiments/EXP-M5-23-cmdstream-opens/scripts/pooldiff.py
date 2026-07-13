#!/usr/bin/env python3
# pooldiff.py DIR_A DIR_B VA [maxlen]  -> word-diff BO at gpu-va VA between two capture dirs
import sys,re,glob,os
def load(path):
    d=bytearray()
    for line in open(path):
        m=re.match(r'^([0-9a-f]{8}): (.*)',line)
        if not m:continue
        b=int(m.group(1),16);by=bytes.fromhex(m.group(2).replace(' ',''))
        if b+len(by)>len(d):d.extend(b'\x00'*(b+len(by)-len(d)))
        d[b:b+len(by)]=by
    return bytes(d)
def find(dirp,va):
    g=glob.glob(os.path.join(dirp,'bo_sigusr1_h0_va%s_*.hex'%va))
    return g[0] if g else None
da,db,va=sys.argv[1],sys.argv[2],sys.argv[3]
maxlen=int(sys.argv[4],0) if len(sys.argv)>4 else 0x2000
fa,fb=find(da,va),find(db,va)
if not fa or not fb:
    print("  MISSING va %s (a=%s b=%s)"%(va,bool(fa),bool(fb)));sys.exit(0)
a,b=load(fa),load(fb);n=min(len(a),len(b),maxlen)
nd=0
for i in range(0,n,4):
    if a[i:i+4]!=b[i:i+4]:
        print("   +0x%04x: %s -> %s"%(i,a[i:i+4].hex(),b[i:i+4].hex()));nd+=1
print("  va %s: %d word-diffs (a=%s b=%s len=%d)"%(va,nd,os.path.basename(da),os.path.basename(db),n))
