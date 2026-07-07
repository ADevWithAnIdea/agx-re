#!/usr/bin/env python3
"""fmtx.py -- EXP-0028: extract & decode the 32-byte texture descriptor Metal
appends into the Tier-2 argument buffer, from an iotrace BO dump.

Locates the argument buffer robustly by scanning every captured BO for a u64 at
+0x14a0 (the EXP-0011 texture-descriptor slot) that points back INTO the same BO
(self-referential descriptor pointer). Follows it and decodes:
  byte0  = (numtype? no) type[0:2] | chan-arrangement hi-nibble
  byte1  = numtype<<5 | sizeclass
  swizzle, width-1, height-1, depth/arrayLen-1, sample-count, mip flags.

Falls back to a (type,W-1,H-1) anchor scan if the +0x14a0 slot isn't self-ref.

CLEAN-ROOM: operates only on captured DATA bytes. No Apple code.

Usage: fmtx.py DUMPDIR [--w W --h H --type CODE] [--label NAME]
"""
import argparse, glob, os, re, sys

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
NUMTYPE = {0:'unorm',1:'snorm',2:'uint',3:'sint',4:'float',5:'nt5',6:'nt6',7:'nt7'}
TYPECODE= {0:'1D',1:'1DArray?',2:'2D',3:'2DArray',4:'2DMS',5:'3D',6:'Cube',7:'CubeArray?'}

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
    return {'path':path,'gpu_va':gpu_va,'cpu':cpu,'size':size,'data':bytes(data)}

def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0

def find_desc_by_argslot(bos):
    """Return (bo, off) of the 32B descriptor pointed to by +0x14a0 (self-ref)."""
    for b in bos:
        d=b['data']
        if len(d) < 0x14a8: continue
        p=u64(d,0x14a0)
        if b['gpu_va'] and b['gpu_va'] <= p < b['gpu_va']+b['size']:
            return (b, p-b['gpu_va'])
    return None

def find_desc_by_anchor(bos, W, H, tcode):
    for b in bos:
        d=b['data']
        for o in range(0,max(0,len(d)-32),4):
            w0=int.from_bytes(d[o:o+4],'little'); w1=int.from_bytes(d[o+4:o+8],'little')
            if (w0&0x7)!=tcode: continue
            width  = (((w0>>28)&0xf) | ((w1&0xff)<<4)) + 1
            height = ((w1>>10)&0xfff) + 1
            nt=(int.from_bytes(d[o+1:o+2],'little')>>5)&0x7
            if width==W and height==H and nt<=4:
                return (b,o)
    return None

def decode(d, off, label):
    w=[int.from_bytes(d[off+4*i:off+4*i+4],'little') for i in range(8)]
    b0=d[off]&0xff; b1=d[off+1]&0xff
    tcode=w[0]&0x7
    chan=(b0>>4)&0xf
    numtype=(b1>>5)&0x7; sizeclass=b1&0x1f
    sw=[(w[0]>>(16+3*i))&0x7 for i in range(4)]
    width=(((w[0]>>28)&0xf)|((w[1]&0xff)<<4))+1
    height=((w[1]>>10)&0xfff)+1
    samp=(w[1]>>24)&0x3
    mipflag=(w[1]>>26)&1; auxpres=(w[1]>>27)&1
    srgb=(w[3]>>12)&1; deptharr=(w[3]>>14)&0x1ffff  # mask out bit31 (aux flag)
    b31=(w[3]>>31)&1; mipm1=(w[5]>>16)&0xf
    fmt16=(b1<<8)|b0
    print(f"{label}")
    print(f"  words: "+" ".join(f"{x:08x}" for x in w))
    print(f"  byte0=0x{b0:02x} byte1=0x{b1:02x} fmt16=0x{fmt16:04x}  "
          f"type={tcode}({TYPECODE.get(tcode,'?')}) chanArr=0x{chan:x} "
          f"numtype={numtype}({NUMTYPE[numtype]}) sizeclass=0x{sizeclass:02x}")
    print(f"  swizzle={sw} width={width} height={height} sampCnt2={samp} "
          f"mipFlag={mipflag} auxPres={auxpres} sRGB={srgb} depth/arr-1={deptharr} "
          f"w3b31={b31} mipCnt-1={mipm1}")
    return {'byte0':b0,'byte1':b1,'fmt16':fmt16,'type':tcode,'chan':chan,
            'numtype':numtype,'sizeclass':sizeclass,'sw':sw,'width':width,'height':height}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir')
    ap.add_argument('--w',type=int,default=0); ap.add_argument('--h',type=int,default=0)
    ap.add_argument('--type',type=int,default=-1)
    ap.add_argument('--label',default=None)
    a=ap.parse_args()
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    if not bos: print(f'no dumps in {a.dumpdir}'); return 1
    label=a.label or os.path.basename(a.dumpdir.rstrip('/'))
    r=find_desc_by_argslot(bos)
    how='argslot+0x14a0'
    if not r and a.w:
        tc = a.type if a.type>=0 else 2
        r=find_desc_by_anchor(bos,a.w,a.h,tc); how='anchor'
    if not r:
        print(f"{label}: DESCRIPTOR NOT FOUND (argslot & anchor failed)"); return 1
    b,off=r
    decode(b['data'],off,f"{label}  [via {how}, BO 0x{b['gpu_va']:x}+0x{off:x}]")
    return 0

if __name__=='__main__':
    sys.exit(main())
