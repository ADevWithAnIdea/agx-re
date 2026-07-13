#!/usr/bin/env python3
# extract.py DIR VA START END  -> print absolute words [START,END) of BO at gpu-va VA in DIR
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
d,va,s,e=sys.argv[1],sys.argv[2],int(sys.argv[3],0),int(sys.argv[4],0)
g=glob.glob(os.path.join(d,'bo_*va%s_*.hex'%va))
if not g: print("  MISSING",d,va); sys.exit(0)
b=load(g[0])
for off in range(s,min(e,len(b)),4):
    w=int.from_bytes(b[off:off+4].ljust(4,b'\0'),'little')
    print("  +0x%04x: %08x"%(off,w))
