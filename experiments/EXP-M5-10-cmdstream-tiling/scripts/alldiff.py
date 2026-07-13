#!/usr/bin/env python3
# alldiff.py DIR_A DIR_B [maxlen] -> for every BO present in both dirs, list word-diffs.
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
def va(fn):
    m=re.search(r'_va([0-9a-f]+)_',fn);return m.group(1) if m else None
da,db=sys.argv[1],sys.argv[2]
maxlen=int(sys.argv[3],0) if len(sys.argv)>3 else 0x4000
A={va(os.path.basename(f)):f for f in glob.glob(os.path.join(da,'bo_*'))}
B={va(os.path.basename(f)):f for f in glob.glob(os.path.join(db,'bo_*'))}
for v in sorted(set(A)&set(B), key=lambda x:int(x,16)):
    a,b=load(A[v]),load(B[v]);n=min(len(a),len(b),maxlen);diffs=[]
    for i in range(0,n,4):
        if a[i:i+4]!=b[i:i+4]:diffs.append((i,a[i:i+4].hex(),b[i:i+4].hex()))
    if diffs:
        print("va %s: %d diffs"%(v,len(diffs)))
        for (i,x,y) in diffs[:40]:print("   +0x%04x: %s -> %s"%(i,x,y))
        if len(diffs)>40:print("   ...(%d more)"%(len(diffs)-40))
