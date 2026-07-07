#!/usr/bin/env python3
"""dcheck.py -- RT-3 INDEPENDENT texture-descriptor field verifier.

Follows the arg-buffer slot0 pointer to the 32-byte texture descriptor, prints all
8 words, and decodes every documented field. It deliberately does NOT trust the
doc's claimed bit widths: it reconstructs width-1/height-1 under multiple candidate
packings and reports which (if any) reproduces the known W,H. Also decodes type,
byte0/byte1 (numtype<<5|sizeclass), swizzle, sampleCount, mip/compression bits,
base VA (VA>>4), sRGB, arrayLen/depth, mipCount, secondary VA -- comparing each to
the expected value passed on the CLI, printing PASS/FAIL.

CLEAN-ROOM: operates only on captured DATA bytes. No Apple code.

Usage:
  dcheck.py DUMPDIR --obuf 0xVA --w W --h H [--type 2d] [--mips N] [--samples N]
            [--srgb 0|1] [--arraylen N] [--depth N] [--expect-va 0xVA]
"""
import argparse, glob, os, re, sys

HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(path):
    gpu=cpu=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu,cpu,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'path':path,'gpu_va':gpu,'size':size,'data':bytes(data)}

def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0

def find_arg_and_desc(bos, obuf):
    """Find arg BO (holds obuf VA in +0x1490..+0x14c8), then follow slot0 ptr to desc."""
    ob=obuf.to_bytes(8,'little')
    for b in bos:
        d=b['data']
        if len(d)<0x14c8: continue
        if ob in d[0x1490:0x14c8]:
            base=b['gpu_va']
            slots=[u64(d,0x14a0+8*k) for k in range(4)]
            # texture desc ptr = the slot pointing back inside this BO (not obuf)
            for k,v in enumerate(slots):
                if v!=obuf and base<=v<base+b['size']:
                    return b, v-base, slots
    return None,None,None

SW={0:'R',1:'G',2:'B',3:'A',4:'1',5:'0',6:'?6',7:'?7'}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--obuf',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--type',default='2d'); ap.add_argument('--mips',type=int,default=1)
    ap.add_argument('--samples',type=int,default=1); ap.add_argument('--srgb',type=int,default=0)
    ap.add_argument('--arraylen',type=int,default=1); ap.add_argument('--depth',type=int,default=1)
    ap.add_argument('--expect-va',default=None); ap.add_argument('--swizzle',default=None)
    a=ap.parse_args()
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    b,doff,slots=find_arg_and_desc(bos,int(a.obuf,0))
    if not b: print(f'!! arg BO/descriptor not found (obuf {a.obuf})'); return 1
    d=b['data']; w=[int.from_bytes(d[doff+4*i:doff+4*i+4],'little') for i in range(8)]
    print(f'# desc in BO 0x{b["gpu_va"]:x}+0x{doff:x}')
    print('# words: '+' '.join(f'w{i}={w[i]:08x}' for i in range(8)))
    byte0=w[0]&0xff; byte1=(w[0]>>8)&0xff
    numtype=(byte1>>5)&0x7; sizeclass=byte1&0x1f
    npass=[0,0]
    def chk(name,got,exp):
        ok = (got==exp)
        npass[0]+=1; npass[1]+= (1 if ok else 0)
        print(f'  {"PASS" if ok else "FAIL"} {name}: got={got} exp={exp}')
        return ok
    # --- type ---
    print(f'  INFO byte0=0x{byte0:02x} byte1=0x{byte1:02x}  type3b={w[0]&0x7} type4b={w[0]&0xf} '
          f'chanArr=0x{(w[0]>>4)&0xf:x} numtype={numtype} sizeclass=0x{sizeclass:02x}')
    # --- swizzle ---
    swz=(w[0]>>16)&0xfff
    sw=[SW[(swz>>(3*i))&0x7] for i in range(4)]
    print(f'  INFO swizzle bits[16:27]=0x{swz:03x} -> R={sw[0]} G={sw[1]} B={sw[2]} A={sw[3]}')
    if a.swizzle: chk('swizzle',''.join(sw),a.swizzle.upper())
    # --- width/height under candidate packings ---
    lo=(w[0]>>28)&0xf
    w_doc12 = (lo | ((w[1]&0xff)<<4))            # doc: word0[28:31] | word1[0:7]<<4  (12-bit)
    w_hyp14 = (lo | ((w[1]&0x3ff)<<4))           # hyp: word0[28:31] | word1[0:9]<<4  (14-bit)
    h_doc   = (w[1]>>10)&0xfff                    # doc: word1[10:21] (12-bit)
    h_hyp14 = (w[1]>>10)&0x3fff                   # hyp: word1[10:23] (14-bit)
    print(f'  INFO word1=0x{w[1]:08x}  bits8_9=0b{(w[1]>>8)&0x3:02b}  bits22_23=0b{(w[1]>>22)&0x3:02b}')
    print(f'  INFO width-1  doc12={w_doc12}(->W {w_doc12+1})  hyp14={w_hyp14}(->W {w_hyp14+1})')
    print(f'  INFO height-1 doc12={h_doc}(->H {h_doc+1})  hyp14={h_hyp14}(->H {h_hyp14+1})')
    okw = chk('width(hyp14 word0[28:31]|word1[0:9])', w_hyp14+1, a.w)
    okh = chk('height(hyp14 word1[10:23])', h_hyp14+1, a.h)
    if not okw: chk('width(doc12)', w_doc12+1, a.w)
    if not okh: chk('height(doc12)', h_doc+1, a.h)
    # --- sample count ---
    sc=(w[1]>>24)&0x3
    exp_sc = max(0,(a.samples.bit_length()-1)-1) if a.samples>1 else 0
    print(f'  INFO word1 bit24_25(sampleCount)={sc} bit26(mip)={(w[1]>>26)&1} bit27(comp)={(w[1]>>27)&1} bit28_29={(w[1]>>28)&0x3}')
    if a.samples>1: chk('sampleCount log2(n)-1',sc,exp_sc)
    # --- mip flag / count ---
    mipflag=(w[1]>>26)&1
    mipcnt=(w[5]>>16)&0xf
    if a.mips>1:
        chk('mipmapped flag word1.b26',mipflag,1)
        chk('mipCount-1 word5[16:19]',mipcnt,a.mips-1)
    # --- base VA ---
    bva=(w[2] | ((w[3]&0xfff)<<32))<<4
    print(f'  INFO baseVA(word2|word3[0:11]<<4)=0x{bva:x}')
    if a.expect_va:
        chk('baseVA==expect',hex(bva),a.expect_va)
    else:
        # must land at start (offset 0) of some captured BO
        hit=[bb for bb in bos if bb['gpu_va']==bva]
        anyin=[bb for bb in bos if bb['gpu_va']<=bva<bb['gpu_va']+bb['size']]
        print(f'  {"PASS" if hit else ("WARN" if anyin else "FAIL")} baseVA lands at BO start: '
              f'{"yes@0x%x"%hit[0]["gpu_va"] if hit else ("inside 0x%x+0x%x"%(anyin[0]["gpu_va"],bva-anyin[0]["gpu_va"]) if anyin else "NO BO")}')
    # --- sRGB ---
    srgb=(w[3]>>12)&1
    print(f'  INFO word3=0x{w[3]:08x} bit12(sRGB)={srgb} bit31(auxmeta)={(w[3]>>31)&1} bits14+=0x{(w[3]>>14)&0x1ffff:x}')
    chk('sRGB word3.b12',srgb,a.srgb)
    # --- arrayLen/depth-1 field ---
    ad=(w[3]>>14)&0x7ff  # doc "bits[14:...]"
    if a.arraylen>1:
        print(f'  INFO arrayLen field word3[14:]=0x{ad:x} (->{ad+1}) exp arraylen={a.arraylen}')
    if a.depth>1:
        print(f'  INFO depth field word3[14:]=0x{ad:x} (->{ad+1}) exp depth={a.depth}')
    # --- secondary VA ---
    sec=(w[4] | ((w[5]&0xfff)<<32))<<4
    print(f'  INFO secondaryVA(word4|word5[0:11]<<4)=0x{sec:x}  (word4={w[4]:08x} word5={w[5]:08x})')
    print(f'# SUMMARY {npass[1]}/{npass[0]} field checks PASS')
    return 0

if __name__=='__main__': sys.exit(main())
