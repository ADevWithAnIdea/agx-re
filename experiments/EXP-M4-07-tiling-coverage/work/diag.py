#!/usr/bin/env python3
# diagnostic: for bpp1/2 3D, show actual mismatch under the T=128/ceil/padW*padH model,
# and locate where texel (x,y,s) markers really are. Uses r16 (invertible-ish low bits).
import sys,glob,os,re,math
sys.path.insert(0,os.path.dirname(__file__))
from solve3d import load,hh,expect_bytes,morton,find_backing,TYPECODE,BPP,WORDS

dumpdir=sys.argv[1]; typ=sys.argv[2]; fmt=sys.argv[3]
W=int(sys.argv[4]); H=int(sys.argv[5]); S=int(sys.argv[6])
bpp=BPP[fmt]
bos=[load(p) for p in glob.glob(os.path.join(dumpdir,'*.hex'))]
bva,w,bo=find_backing(bos,W,H,TYPECODE[typ])
base=bva-bo['gpu_va']; d=bo['data']
print(f"backing sz=0x{bo['size']:x} base_off=0x{base:x} desc={' '.join(f'{x:08x}' for x in w)}")

# choose model
T=128 if bpp==1 else 64 if bpp==2 else 32
D=int(round(math.log2(T)))
cols=-(-W//T)
padW=cols*T; padH=(-(-H//T))*T
planeElems=padW*padH
print(f"model T={T} cols={cols} padW={padW} padH={padH} planeElems={planeElems}")

# forward map: predicted offset for a handful of anchors, show stored vs expected
def pred(x,y,s):
    tx,ty=x>>D,y>>D
    tm=(ty*cols+tx)*(T*T)+morton(x&(T-1),y&(T-1),D)
    return s*planeElems+tm
for (x,y,s) in [(0,0,0),(1,0,0),(0,1,0),(1,1,0),(T,0,0),(0,T,0),(0,0,1),(5,7,0),(200,3,0)]:
    e=pred(x,y,s); off=base+e*bpp
    eb=expect_bytes(fmt,x,y,s); sb=d[off:off+bpp]
    print(f"  ({x:3d},{y:3d},{s}) e={e} off=0x{off:x} exp={eb.hex()} got={sb.hex()} {'OK' if eb==sb else 'X'}")

# full mismatch count for this model
miss=0; tot=0
for s in range(S):
    for y in range(H):
        for x in range(W):
            tot+=1; e=pred(x,y,s); off=base+e*bpp
            if d[off:off+bpp]!=expect_bytes(fmt,x,y,s): miss+=1
print(f"FULL mismatch {miss}/{tot}")

# For r16: invert. Find, for the r16 low-16 hash, the first offset whose stored u16 == hh(x,y,0,0)&0xffff for a few anchors
if fmt=='r16uint':
    n=(min(len(d),bo['size'])-base)//2
    def firste(val):
        for e in range(n):
            o=base+e*2
            if int.from_bytes(d[o:o+2],'little')==val: return e
        return None
    print("--- invert (first element index whose stored u16 == hash) ---")
    for (x,y,s) in [(0,0,0),(1,0,0),(0,1,0),(T,0,0),(0,T,0),(0,0,1),(2*T,0,0)]:
        val=hh(x,y,s,0)&0xffff
        print(f"  first e[hash({x},{y},{s})=0x{val:04x}] = {firste(val)}  (pred {pred(x,y,s)})")
