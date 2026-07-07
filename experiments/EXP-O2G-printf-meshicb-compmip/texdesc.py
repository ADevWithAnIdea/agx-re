#!/usr/bin/env python3
"""texdesc.py -- decode ALL 32-byte texture descriptors in an iotrace BO dump and
correlate each to its backing BO (allocation size) for the compression x mipmap / NPOT
probe (EXP-O2G part 3).

A G17P texture descriptor (docs/descriptors + docs/tiling §3/§4, EXP-0015/O2B):
  word0 @0x00  format+swizzle+type   (byte0 low nibble = texture type; 2 = 2D)
  word1 @0x04  bit26=mipmapped  bit27=compression-aux-present  bits[28:29]=sparse
  word2 @0x08  base VA low   |  word3 @0x0c  bit31=aux-metadata, [0:11]=base VA high
  word4 @0x10  aux VA low    |  word5 @0x14  [0:11]=aux VA high, [16:19]=mipCount-1
  baseVA = (word2 | ((word3 & 0xfff)<<32)) << 4      (16-byte units)
  auxVA  = (word4 | ((word5 & 0xfff)<<32)) << 4      (0 if no aux)

We do NOT rely on a fixed argument-buffer offset: we scan every BO for 32-byte windows
whose decoded baseVA equals a captured BO's gpu_va and whose byte0 low nibble == 2, which
robustly isolates the real texture descriptors. Each is matched back to that BO's size.

CLEAN-ROOM: operates only on DATA (bytes our own Metal process handed the kernel).

Usage: texdesc.py DUMPDIR [--specs "16x16x1,..."] [--fmt rgba8unorm] [--bpp 4]
"""
import argparse, glob, os, re, sys

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

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
    return {'path':os.path.basename(path),'gpu_va':gpu_va,'size':size,'data':bytes(data)}

def u32(d,o): return int.from_bytes(d[o:o+4],'little') if o+4<=len(d) else 0

def padpow2(n):
    p=1
    while p<n: p<<=1
    return p

def exp_total(W,H,M,bpp):
    tot=0; levels=[]
    for L in range(M):
        lw=max(1,W>>L); lh=max(1,H>>L)
        lb=padpow2(lw)*padpow2(lh)*bpp
        if lb<0x80: lb=0x80
        levels.append((L,lw,lh,lb)); tot+=lb
    return tot, levels

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir')
    ap.add_argument('--specs', default='')
    ap.add_argument('--fmt', default='rgba8unorm')
    ap.add_argument('--bpp', type=int, default=4)
    a=ap.parse_args()

    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    bos=[b for b in bos if b['gpu_va']]
    by_va={b['gpu_va']:b for b in bos}
    vaset=set(by_va)
    print(f'# {a.dumpdir}: {len(bos)} BOs')

    # expected sizes per spec (for labeling)
    specs=[]
    for tok in a.specs.split(','):
        tok=tok.strip()
        if not tok: continue
        parts=tok.replace('x',' ').split()
        if len(parts)<2: continue
        W=int(parts[0]); H=int(parts[1]); M=int(parts[2]) if len(parts)>2 else 1
        tot,levels=exp_total(W,H,M,a.bpp)
        specs.append(dict(W=W,H=H,M=M,tot=tot,levels=levels,aux=tot//128))

    found=[]
    seen=set()
    for b in bos:
        d=b['data']
        for off in range(0, max(0,len(d)-32), 4):
            w0=u32(d,off); w1=u32(d,off+4); w2=u32(d,off+8); w3=u32(d,off+12)
            w4=u32(d,off+16); w5=u32(d,off+20)
            if w0==0: continue
            if (w0 & 0xf) != 2:  # texture type nibble: 2 = 2D
                continue
            baseVA=(w2 | ((w3 & 0xfff)<<32))<<4
            if baseVA not in vaset:
                continue
            key=(b['gpu_va'],off)
            if key in seen: continue
            seen.add(key)
            auxVA=(w4 | ((w5 & 0xfff)<<32))<<4 if w4 or (w5&0xfff) else 0
            found.append(dict(argbo=b['gpu_va'],off=off,w0=w0,w1=w1,w3=w3,w5=w5,
                              baseVA=baseVA,auxVA=auxVA,basesize=by_va[baseVA]['size']))

    found.sort(key=lambda f:(f['argbo'],f['off']))
    print(f'# {len(found)} texture descriptors found\n')
    hdr=f"{'#':>2} {'argBO@off':>20} {'word0':>9} {'word1':>9} {'mip':>3} {'cmp':>3} {'sps':>3} {'w3.b31':>6} {'baseVA':>13} {'baseSz':>9} {'auxVA':>13} {'auxOff':>9} {'auxSz':>8} {'mipCt':>5}"
    print(hdr); print('-'*len(hdr))
    for i,f in enumerate(found):
        mip=(f['w1']>>26)&1; cmp=(f['w1']>>27)&1; sps=(f['w1']>>28)&3
        b31=(f['w3']>>31)&1
        mipct=((f['w5']>>16)&0xf)+1
        auxoff=f['auxVA']-f['baseVA'] if f['auxVA'] else 0
        auxsz=(f['basesize']-auxoff) if (f['auxVA'] and auxoff>0 and auxoff<f['basesize']) else 0
        print(f"{i:>2} {f['argbo']:#013x}+{f['off']:04x} {f['w0']:08x} {f['w1']:08x} "
              f"{mip:>3} {cmp:>3} {sps:>3} {b31:>6} {f['baseVA']:#013x} {f['basesize']:#08x} "
              f"{f['auxVA']:#013x} {auxoff:#08x} {auxsz:#07x} {mipct:>5}")
        # label against specs by matching backing-BO size to expected total
        if specs:
            best=min(specs,key=lambda s:abs(s['tot']-f['basesize']) if not cmp else abs(s['tot']+s['aux']-f['basesize']))
            exp_alloc = best['tot']+best['aux'] if cmp else best['tot']
            note='ALL-MIPS' if (cmp and abs(auxsz-best['aux'])<=0x10) else ''
            print(f"     -> spec {best['W']}x{best['H']}x{best['M']} expImg={best['tot']:#x} "
                  f"expAux(all)={best['aux']:#x} expAlloc={exp_alloc:#x} {note}")
            if best['M']>1:
                print(f"        levels: "+', '.join(f"L{L}={lb:#x}({lw}x{lh})" for L,lw,lh,lb in best['levels']))

if __name__=='__main__':
    sys.exit(main() or 0)
