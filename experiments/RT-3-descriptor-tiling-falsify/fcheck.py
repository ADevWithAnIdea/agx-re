#!/usr/bin/env python3
"""fcheck.py -- RT-3 format-code rule falsifier.

Extracts byte0/byte1 from a captured texture descriptor and checks them against the
DOC's rule:  byte1 = (numtype<<5) | sizeclass  (numtype: unorm0 snorm1 uint2 sint3
float4 XR5), plus the sRGB flag = word3 bit12. For each obscure format the internal
table holds the doc-derived expectation (marked DOC where the doc gives a sizeclass,
or NEW where the code is a fresh observation we only sanity-check for numtype
orthogonality). Prints PASS/FAIL per format.

CLEAN-ROOM: DATA only. No Apple code.
Usage: fcheck.py DUMPDIR --obuf 0xVA --fmt NAME
"""
import argparse, glob, os, re, sys

HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
def load(path):
    gpu=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu,_,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'gpu_va':gpu,'size':size,'data':bytes(data)}
def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0

NT={'unorm':0,'snorm':1,'uint':2,'sint':3,'float':4,'xr':5}
# format -> (numtype, sizeclass_or_None, srgb, source)   sizeclass None = NEW (record only)
EXP={
 'r16snorm':('snorm',0x02,0,'DOC'), 'rg16unorm':('unorm',0x08,0,'DOC'),
 'rg16snorm':('snorm',0x08,0,'DOC'),'rgba16snorm':('snorm',0x0c,0,'DOC'),
 'r16sint':('sint',0x02,0,'DOC'),   'rg16sint':('sint',0x08,0,'DOC'),
 'rg16uint':('uint',0x08,0,'DOC'),  'rgba16sint':('sint',0x0c,0,'DOC'),
 'rg8snorm':('snorm',0x02,0,'DOC'), 'rg8sint':('sint',0x02,0,'DOC'),
 'r8unorm_srgb':('unorm',0x00,1,'DOC'), 'rgba8sint':('sint',0x0a,0,'DOC'),
 'rgb10a2uint':('uint',0x09,0,'DOC'),
 'bgr10_xr':('xr',0x09,0,'DOC'), 'bgra10_xr':('xr',0x09,0,'DOC'),
 'bgr10_xr_srgb':('xr',0x09,1,'DOC'),
 'rg32uint':('uint',0x0c,0,'DOC'), 'rg32sint':('sint',0x0c,0,'DOC'),
 'rgba32sint':('sint',0x0e,0,'DOC'),
 'depth16unorm':('unorm',0x02,0,'DOC'), 'stencil8':('uint',0x00,0,'DOC'),
 'depth32float_stencil8':('float',None,0,'NEW'),
 'bc1_rgba':('unorm',0x1d,0,'DOC'), 'bc3_rgba':('unorm',0x1d,0,'DOC'),
 'bc4_runorm':('unorm',0x1d,0,'DOC'), 'bc4_rsnorm':('snorm',0x1d,0,'DOC'),
 'bc5_rgunorm':('unorm',0x1e,0,'DOC'), 'bc6h_float':('float',0x1e,0,'DOC'),
 'bc7_rgba':('unorm',0x1e,0,'DOC'), 'bc7_srgb':('unorm',0x1e,1,'DOC'),
 'astc_5x5':('unorm',0x18,0,'DOC'), 'astc_6x6':('unorm',0x19,0,'DOC'),
 'astc_10x10':('unorm',0x1a,0,'DOC'), 'astc_8x8_hdr':('float',0x19,0,'DOC'),
 'astc_6x6_srgb':('unorm',0x19,1,'DOC'),
 'eac_r11unorm':('unorm',None,0,'NEW'), 'eac_r11snorm':('snorm',None,0,'NEW'),
 'eac_rg11unorm':('unorm',0x17,0,'DOC'),
 'etc2_rgb8':('unorm',0x16,0,'DOC'), 'etc2_rgb8a1':('unorm',0x16,0,'NEW'),
 'rgba8unorm':('unorm',0x0a,0,'DOC'), 'rgba8unorm_srgb':('unorm',0x0a,1,'DOC'),
 'bgra8unorm':('unorm',0x0a,0,'DOC'), 'bgra8unorm_srgb':('unorm',0x0a,1,'DOC'),
 'r8unorm':('unorm',0x00,0,'DOC'), 'r32uint':('uint',0x08,0,'DOC'),
}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('dumpdir')
    ap.add_argument('--obuf',required=True); ap.add_argument('--fmt',required=True)
    a=ap.parse_args(); obuf=int(a.obuf,0); ob=obuf.to_bytes(8,'little')
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    desc=None
    for b in bos:
        d=b['data']
        if len(d)<0x14c8 or ob not in d[0x1490:0x14c8]: continue
        base=b['gpu_va']
        for k in range(4):
            v=u64(d,0x14a0+8*k)
            if v!=obuf and base<=v<base+b['size']:
                doff=v-base
                desc=[int.from_bytes(d[doff+4*i:doff+4*i+4],'little') for i in range(8)]; break
        if desc: break
    if not desc: print(f'{a.fmt}: DESC NOT FOUND'); return 1
    byte0=desc[0]&0xff; byte1=(desc[0]>>8)&0xff; srgb=(desc[3]>>12)&1
    numtype=(byte1>>5)&0x7; sizeclass=byte1&0x1f
    exp=EXP.get(a.fmt)
    tag=f'byte0=0x{byte0:02x} byte1=0x{byte1:02x} (numtype={numtype} sizeclass=0x{sizeclass:02x}) srgb={srgb}'
    if not exp: print(f'{a.fmt:22s} {tag}  [no expectation]'); return 0
    ent,esc,esr,src=exp
    ent_n=NT[ent]
    ok_nt=(numtype==ent_n); ok_sr=(srgb==esr)
    if esc is None:
        verdict='NEW-obs'; ok_sc=True; exp_b1=f'nt={ent_n} sc=?'
    else:
        exp_b1=(ent_n<<5)|esc; ok_sc=(byte1==exp_b1)
        verdict='PASS' if (ok_sc and ok_sr) else 'FAIL'
        exp_b1=f'0x{exp_b1:02x}'
    flags=('' if ok_nt else ' NUMTYPE!')+('' if ok_sc else ' SIZECLASS!')+('' if ok_sr else ' SRGB!')
    print(f'{a.fmt:22s} {tag}  exp[{src}] numtype={ent}({ent_n}) byte1={exp_b1} srgb={esr} -> {verdict}{flags}')
    return 0
if __name__=='__main__': sys.exit(main())
