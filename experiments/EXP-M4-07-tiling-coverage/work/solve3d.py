#!/usr/bin/env python3
"""solve3d.py — EXP-M4-07 TIL-1 model-checker for 3D/2DArray/Cube/CubeArray/2DMS.

For a typrobe2 capture (element (x,y,s) holds words hh(x,y,s,k)), locate the backing
BO + base offset via the texture descriptor, then for EACH candidate layout model
predict the byte offset of every element and count mismatches over the FULL grid.
The 0-mismatch model is the true layout. Models parametrize:
  * tile edge T (32/64/128)         -> reveals whether T follows bpp inside a plane
  * intra-plane cols rule           -> ceil / nextpow2 / 16KiB-granule
  * plane/layer stride (planeElems) -> tile-padded(padW*padH) / nextpow2(W)*nextpow2(H)
For 2DMS: element = tiledMorton(x,y)*N + sample (sample-major), with T based on bpp
OR bpp*N, to test whether MSAA interleave interacts with T(bpp).

Clean-room: operates only on captured DATA bytes. No Apple code.
Usage: solve3d.py DUMPDIR --type <3d|2darray|cube|cubearray|2dms|2d> --fmt r8uint
                  --w W --h H --slices S [--label NAME]
"""
import argparse, glob, os, re, sys, math

HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
BPP={'r8uint':1,'r16uint':2,'r32uint':4,'rg32uint':8,'rgba32uint':16}
WORDS={'r8uint':1,'r16uint':1,'r32uint':1,'rg32uint':2,'rgba32uint':4}
# texture-type nibble (byte0 low nibble), doc tiling/README §1.6
TYPECODE={'2d':2,'2darray':3,'2dms':4,'3d':5,'cube':6,'cubearray':7}

def load(path):
    gpu_va=cpu=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu_va,cpu,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'gpu_va':gpu_va,'cpu':cpu,'size':size,'data':bytes(data)}

def hh(x,y,s,k):
    h=2166136261
    for v in (x,y,s,k): h=((h^v)*16777619)&0xffffffff
    return h

def expect_bytes(fmt,x,y,s):
    w=WORDS[fmt]; bpp=BPP[fmt]
    if fmt=='r8uint':  return bytes([hh(x,y,s,0)&0xff])
    if fmt=='r16uint': return (hh(x,y,s,0)&0xffff).to_bytes(2,'little')
    out=b''.join(hh(x,y,s,k).to_bytes(4,'little') for k in range(w))
    return out

def nextpow2(n): return 1<<((n-1).bit_length()) if n>1 else 1
def morton(a,b,D):
    r=0
    for i in range(D): r|=((a>>i)&1)<<(2*i)|((b>>i)&1)<<(2*i+1)
    return r

def find_backing(bos,W,H,typecode):
    cands=[]
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w0=int.from_bytes(d[o:o+4],'little'); w1=int.from_bytes(d[o+4:o+8],'little')
            w2=int.from_bytes(d[o+8:o+12],'little'); w3=int.from_bytes(d[o+12:o+16],'little')
            if (w0&0xf)!=typecode: continue
            width=(((w0>>28)&0xf)|((w1&0x3ff)<<4))+1
            height=((w1>>10)&0x3fff)+1
            if width!=W or height!=H: continue
            bva=(w2|((w3&0xfff)<<32))<<4
            tgt=[bb for bb in bos if bb['gpu_va'] and bb['gpu_va']<=bva<bb['gpu_va']+bb['size']]
            if tgt:
                cands.append((bva,[w0,w1,w2,w3],max(tgt,key=lambda bb:bb['size'])))
    if not cands: return None,None,None
    # prefer the candidate whose backing BO is largest (the image, not a small view/desc BO)
    bva,w,bo=max(cands,key=lambda c:c[2]['size'])
    return bva,w,bo

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--type',required=True)
    ap.add_argument('--fmt',required=True); ap.add_argument('--w',type=int,required=True)
    ap.add_argument('--h',type=int,required=True); ap.add_argument('--slices',type=int,default=1)
    ap.add_argument('--label',default=None)
    a=ap.parse_args()
    typ=a.type; fmt=a.fmt; W=a.w; H=a.h; S=a.slices; bpp=BPP[fmt]
    label=a.label or os.path.basename(a.dumpdir.rstrip('/'))
    isMS = (typ=='2dms')
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    bva,w,bo=find_backing(bos,W,H,TYPECODE[typ])
    if bva is None:
        print(f"{label}: descriptor {W}x{H} type={typ} NOT FOUND"); return 1
    base=bva-bo['gpu_va']; d=bo['data']; bosz=bo['size']
    print(f"# {label}: type={typ} fmt={fmt} bpp={bpp} {W}x{H} slices/samples={S}")
    print(f"#   backing BO=0x{bo['gpu_va']:x} sz=0x{bosz:x} baseVA=0x{bva:x} base_off=0x{base:x} desc={' '.join(f'{x:08x}' for x in w)}")

    # precompute expected bytes for every element
    exp={}
    for s in range(S):
        for y in range(H):
            for x in range(W):
                exp[(x,y,s)]=expect_bytes(fmt,x,y,s)

    def cols_rule(W,T,rule):
        nt=-(-W//T)
        if rule=='ceil': return nt
        if rule=='nextpow2': return nextpow2(W)//T if W>T else 1
        # 16KiB-granule
        if nt<=1: return nt
        G=max(1,0x4000//(T*T*bpp)); return ((nt+G-1)//G)*G

    def check(pred, cap=200):
        """pred: (x,y,s)->element_index. returns mismatch count (early-out at cap)."""
        miss=0; maxe=0
        for (x,y,s),eb in exp.items():
            e=pred(x,y,s); maxe=max(maxe,e)
            off=base+e*bpp
            if off+len(eb)>len(d) or d[off:off+len(eb)]!=eb:
                miss+=1
                if miss>=cap: return miss,maxe
        return miss,maxe

    Ts=(16,32,64,128)
    rules=('ceil','nextpow2','16KiB')
    winners=[]
    print(f"#  {'T':>3} {'colsRule':>9} {'planeStride':>16} {'cols':>4} {'padW':>5} {'padH':>5} {'planeElems':>10} {'mismatch':>8} {'predTotalBO':>11}")
    for T in Ts:
        D=int(round(math.log2(T)))
        for rule in rules:
            cols=cols_rule(W,T,rule)
            padW=cols*T if W>=T else nextpow2(W)
            padH=(-(-H//T))*T if H>=T else nextpow2(H)
            # candidate plane strides (element counts)
            planestrides={
                'padW*padH':      padW*padH,
                'np2(W)*np2(H)':  nextpow2(W)*nextpow2(H),
            }
            for psname,planeElems in planestrides.items():
                if isMS:
                    # element = tiledMorton(x,y)*N + sample ; s is the sample
                    def mk(T=T,D=D,cols=cols,N=S):
                        def pred(x,y,s):
                            tx,ty=x>>D,y>>D
                            tm=(ty*cols+tx)*(T*T)+morton(x&(T-1),y&(T-1),D)
                            return tm*N+s
                        return pred
                    pred=mk()
                    # for MSAA planeElems/plane stride is not a layer multiplier; skip dup
                    if psname!='padW*padH': continue
                    miss,maxe=check(pred)
                    predTotal=padW*padH*S*bpp
                    tag='  <== 0-MISMATCH' if miss==0 else ''
                    print(f"#  {T:>3} {rule:>9} {'MSAA*N+samp':>16} {cols:>4} {padW:>5} {padH:>5} {planeElems:>10} {miss:>8} 0x{predTotal:08x}{tag}")
                    if miss==0: winners.append((T,rule,'MSAA',cols,padW,padH,planeElems,predTotal))
                else:
                    def mk(T=T,D=D,cols=cols,pe=planeElems):
                        def pred(x,y,s):
                            tx,ty=x>>D,y>>D
                            tm=(ty*cols+tx)*(T*T)+morton(x&(T-1),y&(T-1),D)
                            return s*pe+tm
                        return pred
                    pred=mk()
                    miss,maxe=check(pred)
                    predTotal=planeElems*S*bpp
                    tag='  <== 0-MISMATCH' if miss==0 else ''
                    print(f"#  {T:>3} {rule:>9} {psname:>16} {cols:>4} {padW:>5} {padH:>5} {planeElems:>10} {miss:>8} 0x{predTotal:08x}{tag}")
                    if miss==0: winners.append((T,rule,psname,cols,padW,padH,planeElems,predTotal))
    print(f"# BO actual size = 0x{bosz:x}")
    if winners:
        for W_ in winners:
            T,rule,ps,cols,padW,padH,pe,pt=W_
            note='(matches BO size)' if pt==bosz else f'(pred 0x{pt:x} vs BO 0x{bosz:x})'
            print(f"# CONFIRMED: T={T} cols={cols}({rule}) planeStride={ps} planeElems={pe} padW={padW} padH={padH} predTotal=0x{pt:x} {note}")
    else:
        print("# NO 0-mismatch model found (check dims/pattern)")
    return 0

if __name__=='__main__': sys.exit(main())
