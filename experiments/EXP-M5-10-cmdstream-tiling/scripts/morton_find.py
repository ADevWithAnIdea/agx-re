#!/usr/bin/env python3
# morton_find.py DIR -> find the r32u texture backing whose tile(0,0) is Morton-ordered
# texel(x,y)=(y<<16)|x, and report the byte->texel map for the first tile.
import sys,re,glob,os,struct
def load(path):
    d=bytearray()
    for line in open(path):
        m=re.match(r'^([0-9a-f]{8}): (.*)',line)
        if not m:continue
        b=int(m.group(1),16);by=bytes.fromhex(m.group(2).replace(' ',''))
        if b+len(by)>len(d):d.extend(b'\x00'*(b+len(by)-len(d)))
        d[b:b+len(by)]=by
    return bytes(d)
def morton(a,b,bits=6):
    v=0
    for i in range(bits): v|=((a>>i)&1)<<(2*i); v|=((b>>i)&1)<<(2*i+1)
    return v
sig=[0,1,0x10000,0x10001,2,3,0x10002,0x10003]
d=sys.argv[1]
for f in sorted(glob.glob(os.path.join(d,'bo_*'))):
    data=load(f)
    if len(data)<0x2000: continue
    n=len(data)//4
    u=struct.unpack('<%dI'%n,data[:n*4])
    for base in range(0,min(n-8, 0x30000//4)):
        if list(u[base:base+8])==sig:
            print("MATCH %s at u32 index %d (byte 0x%x)"%(os.path.basename(f)[:40],base,base*4))
            # verify full first 64-tile Morton
            ok=0;bad=0
            for pos in range(4096):
                x=pos # placeholder
            # decode: at morton position p within 64x64 tile, texel (x,y). invert:
            for p in range(64):
                val=u[base+p]; x=val&0xffff; y=val>>16
                exp=morton(x,y)
                mark="" if exp==p else " <-MISMATCH exp_pos=%d"%exp
                if p<16: print("   pos %2d: val=0x%06x -> texel(%d,%d) morton=%d%s"%(p,val,x,y,exp,mark))
                if exp!=p: bad+=1
            print("   first-64 morton check: %d mismatch"%bad)
            sys.exit(0)
print("NO MATCH in %s"%d)
