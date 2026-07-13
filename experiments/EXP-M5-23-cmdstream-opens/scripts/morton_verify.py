#!/usr/bin/env python3
# morton_verify.py DUMPDIR [W H T bpp] -> byte-verify the A18 tiled-Morton curve on the
# captured r32u texture backing (pattern texel(x,y)=(y<<16)|x written by mortondraw.m).
# A18 model (docs/tiling/README.md 1.1):
#   element_index(x,y) = (ty*cols + tx)*T^2 + morton_T(x&(T-1), y&(T-1))
#   byte_offset        = element_index * bpp ;  morton bit i of x -> bit 2i, y -> 2i+1
# Verdict: report #mismatches over EVERY texel. 0 mismatch = M5 twiddle == A18 twiddle.
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
def morton(a,b,bits):
    v=0
    for i in range(bits): v|=((a>>i)&1)<<(2*i); v|=((b>>i)&1)<<(2*i+1)
    return v
D=sys.argv[1]
W=int(sys.argv[2]) if len(sys.argv)>2 else 192
H=int(sys.argv[3]) if len(sys.argv)>3 else 192
T=int(sys.argv[4]) if len(sys.argv)>4 else 64
bpp=int(sys.argv[5]) if len(sys.argv)>5 else 4
tbits=T.bit_length()-1
cols=(W+T-1)//T
sig=[0,1,0x10000,0x10001,2,3,0x10002,0x10003]  # morton positions 0..7 of tile(0,0)
cand=[]
for f in sorted(glob.glob(os.path.join(D,'bo_*'))):
    data=load(f)
    if len(data) < W*H*bpp: continue
    n=len(data)//4; u=struct.unpack('<%dI'%n,data[:n*4])
    # scan for the signature anywhere in the BO (tile(0,0) start); textures sub-allocate deep
    for base in range(0, n-8):
        if list(u[base:base+8])==sig:
            cand.append((f,base,data,u)); break
if not cand:
    print("NO signature match in",D); sys.exit(1)
f,base,data,u=cand[0]
print("MATCH %s  tile0 base=byte 0x%x  W=%d H=%d T=%d bpp=%d cols=%d"%(os.path.basename(f)[:44],base*4,W,H,T,bpp,cols))
mism=0; checked=0; firstbad=[]
for y in range(H):
    ty=y//T; iy=y&(T-1)
    for x in range(W):
        tx=x//T; ix=x&(T-1)
        ei=(ty*cols+tx)*(T*T)+morton(ix,iy,tbits)
        idx=base+ei
        if idx>=len(u): continue
        got=u[idx]; exp=((y<<16)|x)
        checked+=1
        if got!=exp:
            mism+=1
            if len(firstbad)<8: firstbad.append((x,y,hex(got),hex(exp),hex(idx*4)))
print("checked=%d mismatches=%d"%(checked,mism))
for b in firstbad: print("  MISMATCH x=%d y=%d got=%s exp=%s @byte %s"%b)
# show tile(1,0) start (first texel x=64,y=0) to prove row-major tile stride
if W>T:
    ei=(0*cols+1)*(T*T)+morton(0,0,tbits)
    print("tile(1,0) first texel expect byte 0x%x val=0x%08x got=0x%08x"%((base+ei)*4, 0x40, u[base+ei]))
print("VERDICT:", "M5 intra-tile Morton == A18 (byte-for-byte)" if mism==0 else "DIVERGES from A18")
