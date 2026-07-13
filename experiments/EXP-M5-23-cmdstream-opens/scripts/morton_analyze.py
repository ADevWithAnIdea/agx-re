#!/usr/bin/env python3
# morton_analyze.py HEXFILE [W H T bpp] -> discover the ACTUAL M5 twiddle order from a raw
# texture-backing window (from texscan.m) and compare to the A18 tiled-Morton model, without
# assuming M5==A18. Builds value->offset for every u32 == (y<<16)|x (x<W,y<H), finds the base
# (offset of texel(0,0)) that makes the value set contiguous, then reports the empirical
# element_index(x,y) and how many match A18: element_index=(ty*cols+tx)*T^2+morton_T(ix,iy).
import sys,re,struct
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
F=sys.argv[1]
W=int(sys.argv[2]) if len(sys.argv)>2 else 192
H=int(sys.argv[3]) if len(sys.argv)>3 else 192
T=int(sys.argv[4]) if len(sys.argv)>4 else 64
bpp=int(sys.argv[5]) if len(sys.argv)>5 else 4
tbits=T.bit_length()-1; cols=(W+T-1)//T
d=load(F); n=len(d)//4; u=struct.unpack('<%dI'%n,d[:n*4])
# value -> offset(s) for values that are a valid (y<<16)|x with x<W,y<H
val2off={}
for i in range(n):
    v=u[i]; x=v&0xffff; y=v>>16
    if x<W and y<H and ((y<<16)|x)==v:
        val2off.setdefault(v,[]).append(i*4)
present=sum(1 for y in range(H) for x in range(W) if ((y<<16)|x) in val2off)
print("file=%s texels present as raw u32: %d / %d"%(F.split('/')[-1],present,W*H))
if present < W*H*0.5:
    print("too few texels present; backing likely not fully in window");
# derive base empirically: the texture is a contiguous [base, base+W*H*bpp) span holding each
# texel value once, so base = the smallest offset of any valid non-zero texel value present.
uval=((H-1)<<16)|(W-1)
if uval not in val2off: print("unique corner texel missing"); sys.exit(1)
allmin=min(min(o) for v,o in val2off.items() if v!=0)
base=allmin - ( (0) )  # smallest valid-texel offset marks texture start (element_index near 0)
# align base so texel(0,0)=value0 nearest to window start maps to a whole element
ei_corner=((H-1)//T*cols+(W-1)//T)*(T*T)+morton((W-1)&(T-1),(H-1)&(T-1),tbits)
base_a18=val2off[uval][0]-ei_corner*bpp
print("empirical base=0x%x ; A18-seed base=0x%x ; corner off=0x%x A18 ei=%d"%(base,base_a18,val2off[uval][0],ei_corner))
base=base_a18  # A18-seed is exact when order==A18; empirical printed for cross-check
# now measure empirical element_index for every texel and compare to A18
match=0; tot=0; mism=[]
empirical_ok=0
for y in range(H):
    for x in range(W):
        v=(y<<16)|x
        if v not in val2off: continue
        offs=val2off[v]
        # choose the offset closest to base+A18_ei (handles duplicate small values like 0/1)
        ei_a18=((y//T)*cols+(x//T))*(T*T)+morton(x&(T-1),y&(T-1),tbits)
        want=base+ei_a18*bpp
        best=min(offs,key=lambda o:abs(o-want))
        emp_ei=(best-base)//bpp
        tot+=1
        if emp_ei==ei_a18: match+=1
        elif len(mism)<8: mism.append((x,y,emp_ei,ei_a18,hex(best)))
print("A18-model match: %d / %d texels"%(match,tot))
for m in mism: print("  MISMATCH x=%d y=%d emp_ei=%d a18_ei=%d off=%s"%m)
# independent check: within tile(0,0), print empirical order of first 16 morton positions
print("--- tile(0,0) first 16 byte offsets by A18 morton position ---")
for p in range(16):
    # invert morton p -> (ix,iy)
    ix=iy=0
    for i in range(tbits): ix|=((p>>(2*i))&1)<<i; iy|=((p>>(2*i+1))&1)<<i
    v=(iy<<16)|ix
    o=val2off.get(v,[None])
    print("  pos %2d texel(%d,%d) val=0x%06x -> file-off %s (rel base +0x%x)"%(p,ix,iy,v,
        hex(o[0]) if o[0] is not None else '??', (o[0]-base) if o and o[0] is not None else -1))
print("VERDICT:", "M5 intra-tile twiddle == A18 tiled-Morton (byte-for-byte)" if match==tot and tot>=W*H*0.9 else "see mismatches / partial")
