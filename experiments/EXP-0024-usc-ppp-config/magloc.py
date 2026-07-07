#!/usr/bin/env python3
# magloc.py -- locate the VS/FS magic immediates in the captured code BO (0x10000000000),
# and correlate USC (0x10000130000) word values to each shader's code GPU-VA.
#
# The gvar.m VS embeds 0x51a2b3c4, the FS embeds 0x62c3d4e5, each forced into the code
# stream via a data-dependent XOR. Grepping the code BO for those 4-byte LE patterns gives
# the exact byte offset (=> GPU VA) of each shader's body. Doing this across a --pad / --vsz
# sweep gives (shaderVA -> USC-word) pairs; we then solve for the shift N in the graphics
# analogue of compute's `shaderVA>>6`.
#
# Usage:
#   magloc.py <capdir> [<capdir> ...]         # per-dir: magic offsets + USC words
#   magloc.py --corr <capdirA> <capdirB>      # correlate USC word deltas to VA deltas
#
# CLEAN-ROOM: DATA only. No Apple code inspected.
import glob, os, re, sys

HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
VS_MAGIC=bytes.fromhex('c4b3a251')  # 0x51a2b3c4 LE
FS_MAGIC=bytes.fromhex('e5d4c362')  # 0x62c3d4e5 LE
CODE_VA=0x10000000000
USC_VA =0x10000130000

def load(path):
    gpu_va=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu_va,_,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'gpu_va':gpu_va,'size':size,'data':bytes(data)}

def find_bo(capdir, va):
    for p in glob.glob(os.path.join(capdir,'*.hex')):
        b=load(p)
        if b['gpu_va']==va: return b
    return None

def find_all(data, needle):
    out=[]; i=data.find(needle)
    while i!=-1: out.append(i); i=data.find(needle,i+1)
    return out

def words(data):
    return [int.from_bytes(data[o:o+4],'little') for o in range(0,len(data)-3,4)]

def report(capdir):
    code=find_bo(capdir,CODE_VA); usc=find_bo(capdir,USC_VA)
    print(f"\n=== {capdir} ===")
    if code:
        vs=find_all(code['data'],VS_MAGIC); fs=find_all(code['data'],FS_MAGIC)
        print(f"  code BO 0x{CODE_VA:x} size=0x{len(code['data']):x}")
        for o in vs: print(f"    VS magic @ +{o:#06x}  -> VA {CODE_VA+o:#014x}")
        for o in fs: print(f"    FS magic @ +{o:#06x}  -> VA {CODE_VA+o:#014x}")
    if usc:
        # print the per-stage leading words of each 0x240 sub-block
        d=usc['data']
        for blk,base in enumerate((0x00,0x240,0x480)):
            ws=[int.from_bytes(d[base+o:base+o+4],'little') for o in range(0,0x40,4)]
            print(f"  USC block{blk} @+{base:#05x}: "+' '.join(f'{w:08x}' for w in ws[:8]))
    return code,usc

def corr(dirA,dirB):
    ca,ua=report(dirA); cb,ub=report(dirB)
    if not(ca and cb and ua and ub): print("missing BOs"); return
    # measure VA shift of each shader via magic
    def mag(code,needle):
        f=find_all(code['data'],needle); return f[0] if f else None
    vsA,vsB=mag(ca['data'] and ca,VS_MAGIC),None
    # simpler:
    vsA=find_all(ca['data'],VS_MAGIC); vsB=find_all(cb['data'],VS_MAGIC)
    fsA=find_all(ca['data'],FS_MAGIC); fsB=find_all(cb['data'],FS_MAGIC)
    dVS = (vsB[0]-vsA[0]) if (vsA and vsB) else None
    dFS = (fsB[0]-fsA[0]) if (fsA and fsB) else None
    print(f"\n=== CORR {os.path.basename(dirA)} -> {os.path.basename(dirB)} ===")
    print(f"  VS code VA shift = {dVS:#x}" if dVS is not None else "  VS magic missing")
    print(f"  FS code VA shift = {dFS:#x}" if dFS is not None else "  FS magic missing")
    # find USC words that changed, and for each, see if delta == VAshift>>N
    da,db=ua['data'],ub['data']; n=min(len(da),len(db))
    print("  changed USC words (off: A -> B  delta):")
    for o in range(0,n,4):
        wa=int.from_bytes(da[o:o+4],'little'); wb=int.from_bytes(db[o:o+4],'little')
        if wa!=wb:
            dw=wb-wa
            tags=[]
            for (nm,shift) in (('VS',dVS),('FS',dFS)):
                if shift is None: continue
                for N in range(0,13):
                    if (shift>>N)==dw and dw!=0: tags.append(f"{nm}>>{N}")
                    if shift==dw: tags.append(f"{nm}(raw)")
            t=('  <== '+','.join(sorted(set(tags)))) if tags else ''
            print(f"    +{o:#06x}: {wa:#010x} -> {wb:#010x}  d={dw:#x}{t}")

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--corr':
        corr(sys.argv[2],sys.argv[3])
    else:
        for d in sys.argv[1:]: report(d)

if __name__=='__main__': main()
