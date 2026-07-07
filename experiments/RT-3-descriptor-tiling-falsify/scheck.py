#!/usr/bin/env python3
"""scheck.py -- RT-3 INDEPENDENT sampler-descriptor field verifier.

Follows the arg-buffer slot1 pointer to the 8-byte sampler descriptor, decodes it as
a 64-bit LE bitfield per docs/descriptors, and checks each field against the config
passed on the CLI. Prints raw u64 + PASS/FAIL per field.

Doc bitmap under test:
  lodMin[0:12]=x64  lodMax[13:19]=x8  aniso[20:22]=log2  magF@23 minF@25 mipF[27:28]
  sAddr[29:31] tAddr[32:34] rAddr[35:37]  unnorm@38  cmp-sense@39 cmp-test[40:42]
  border byte7[5:6]=bits[61:62]

CLEAN-ROOM: DATA only. No Apple code.
Usage: scheck.py DUMPDIR --obuf 0xVA [--saddr edge --taddr .. --raddr ..]
       [--magf nearest --minf nearest --mipf none --aniso 1 --lodmin 0 --lodmax -1]
       [--cmp never --border tblack --unnorm 0]
"""
import argparse, glob, os, re, sys
HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$'); HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
def load(path):
    gpu=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu,_,size=(int(m.group(i),16) for i in(1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'gpu_va':gpu,'size':size,'data':bytes(data)}
def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0

ADDR={'edge':0,'repeat':1,'mirror':2,'clampzero':3,'border':3,'mirroredge':5}
# compare: (sense,test)
CMP={'never':(1,7),'always':(0,7),'less':(0,5),'greater':(1,5),
     'lequal':(0,4),'gequal':(1,4),'equal':(0,6),'nequal':(1,6)}
BORDER={'tblack':0,'oblack':1,'owhite':2}

def bits(v,lo,hi): return (v>>lo)&((1<<(hi-lo+1))-1)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('dumpdir'); ap.add_argument('--obuf',required=True)
    ap.add_argument('--saddr',default='edge'); ap.add_argument('--taddr',default='edge'); ap.add_argument('--raddr',default='edge')
    ap.add_argument('--magf',default='nearest'); ap.add_argument('--minf',default='nearest'); ap.add_argument('--mipf',default='none')
    ap.add_argument('--aniso',type=int,default=1); ap.add_argument('--lodmin',type=float,default=0.0); ap.add_argument('--lodmax',type=float,default=-1.0)
    ap.add_argument('--cmp',default='never'); ap.add_argument('--border',default='tblack'); ap.add_argument('--unnorm',type=int,default=0)
    a=ap.parse_args(); obuf=int(a.obuf,0); ob=obuf.to_bytes(8,'little')
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    S=None; raw=None
    for b in bos:
        d=b['data']
        if len(d)<0x14c8 or ob not in d[0x1490:0x14c8]: continue
        base=b['gpu_va']; sptr=u64(d,0x14a8)
        if base<=sptr<base+b['size']:
            soff=sptr-base; S=u64(d,soff); raw=d[soff:soff+8]
        break
    if S is None: print('!! sampler descriptor not found via slot1'); return 1
    print(f'# sampler u64=0x{S:016x} bytes={raw.hex()}')
    np=[0,0]
    def chk(name,got,exp):
        ok=got==exp; np[0]+=1; np[1]+=ok
        print(f'  {"PASS" if ok else "FAIL"} {name}: got={got} exp={exp}')
    lodmin=bits(S,0,11); lodmax=bits(S,13,19); aniso=bits(S,20,22)
    magf=bits(S,23,23); minf=bits(S,25,25); mipf=bits(S,27,28)
    sA=bits(S,29,31); tA=bits(S,32,34); rA=bits(S,35,37); unn=bits(S,38,38)
    sense=bits(S,39,39); test=bits(S,40,42); border=bits(S,61,62)
    print(f'  INFO lodMin[0:12]={lodmin}(->{lodmin/64:.3f}) lodMax[13:19]={lodmax}(->{lodmax/8:.3f}) '
          f'aniso[20:22]={aniso} mag@23={magf} min@25={minf} mip[27:28]={mipf}')
    print(f'  INFO sAddr={sA} tAddr={tA} rAddr={rA} unnorm@38={unn} cmp(sense@39={sense},test[40:42]={test}) border[61:62]={border}')
    chk('sAddr',sA,ADDR[a.saddr]); chk('tAddr',tA,ADDR[a.taddr]); chk('rAddr',rA,ADDR[a.raddr])
    chk('magFilter',magf,1 if a.magf=='linear' else 0)
    chk('minFilter',minf,1 if a.minf=='linear' else 0)
    chk('mipFilter',mipf,{'none':0,'nearest':1,'linear':2}[a.mipf])
    chk('aniso log2',aniso,max(0,(a.aniso.bit_length()-1)))
    chk('unnorm',unn,a.unnorm)
    es,et=CMP[a.cmp]; chk('cmp-sense',sense,es); chk('cmp-test',test,et)
    chk('border',border,BORDER[a.border])
    if a.lodmin>0: chk('lodMin x64',lodmin,round(a.lodmin*64))
    if a.lodmax>=0: chk('lodMax x8',lodmax,round(a.lodmax*8))
    print(f'# SUMMARY {np[1]}/{np[0]} PASS')
    return 0
if __name__=='__main__': sys.exit(main())
