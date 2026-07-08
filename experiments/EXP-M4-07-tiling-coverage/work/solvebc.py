#!/usr/bin/env python3
"""solvebc.py — EXP-M4-07 TIL-2 block-tile/granule model-checker.

For a bcprobe2 capture (block (bx,by) first bytes [bx,by,0x5a,0xa5]), locate the
backing BO+base, then for each candidate (T_blk, cols-rule) predict the block-slot
index e = tiledMorton(bx,by,T_blk,cols)*blockBytes and count mismatches over the
full block grid. The 0-mismatch model reveals the block-tile edge and granule rule.
Mirrors the texel rule at BLOCK granularity: hypothesis T_blk = largest pow2 with
T_blk^2*blockBytes<=16KiB, cols granule G=0x4000/(T_blk^2*blockBytes).

Clean-room: captured DATA bytes only.
Usage: solvebc.py DUMPDIR --bx BX --by BY --bb BLOCKBYTES [--label NAME]
"""
import argparse, glob, os, re, sys
HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(p):
    gpu_va=cpu=size=0; data=bytearray()
    for line in open(p):
        if line.startswith('#'):
            m=HDR.search(line)
            if m: gpu_va,cpu,size=(int(m.group(i),16) for i in (1,2,3))
            continue
        m=HEXLINE.match(line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
        data[off:off+len(b)]=b
    return {'gpu_va':gpu_va,'size':size,'data':bytes(data)}

def morton(a,b,D):
    r=0
    for i in range(D): r|=((a>>i)&1)<<(2*i)|((b>>i)&1)<<(2*i+1)
    return r
def nextpow2(n): return 1<<((n-1).bit_length()) if n>1 else 1

def count_tag(d):
    return sum(1 for o in range(0,len(d)-4,4) if d[o+2]==0x5a and d[o+3]==0xa5)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--bx',type=int,required=True)
    ap.add_argument('--by',type=int,required=True); ap.add_argument('--bb',type=int,required=True)
    ap.add_argument('--label',default=None)
    a=ap.parse_args(); BX,BY,BB=a.bx,a.by,a.bb
    label=a.label or os.path.basename(a.dumpdir.rstrip('/'))
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    if not bos: print(f"{label}: no dumps"); return 1
    # backing = the BO densest in the marker tag
    ntag,bo=sorted(((count_tag(b['data']),b) for b in bos),key=lambda t:-t[0])[0]
    d=bo['data']; bosz=bo['size']
    # base offset: find a type-2 descriptor whose base VA lands in this BO
    base=0
    for b in bos:
        dd=b['data']
        for o in range(0,len(dd)-24,4):
            w=[int.from_bytes(dd[o+4*i:o+4*i+4],'little') for i in range(4)]
            if (w[0]&0xf)!=2: continue
            bva=(w[2]|((w[3]&0xfff)<<32))<<4
            if bo['gpu_va']<=bva<bo['gpu_va']+bosz:
                base=bva-bo['gpu_va']; break
        if base: break
    print(f"# {label}: BO=0x{bo['gpu_va']:x} sz=0x{bosz:x} base_off=0x{base:x} tagged={ntag} expect={BX*BY} bb={BB}")

    def cols_rule(BW,T,rule):
        nt=-(-BW//T)
        if rule=='ceil': return nt
        if rule=='nextpow2': return nextpow2(BW)//T if BW>T else 1
        if nt<=1: return nt
        G=max(1,0x4000//(T*T*BB)); return ((nt+G-1)//G)*G

    def check(T,cols,cap=200):
        import math; D=int(round(math.log2(T)))
        miss=0
        for by in range(BY):
            for bx in range(BX):
                tx,ty=bx>>D,by>>D
                e=(ty*cols+tx)*(T*T)+morton(bx&(T-1),by&(T-1),D)
                off=base+e*BB
                if off+4>len(d) or d[off]!=(bx&0xff) or d[off+1]!=(by&0xff) or d[off+2]!=0x5a or d[off+3]!=0xa5:
                    miss+=1
                    if miss>=cap: return miss
        return miss
    print(f"#  {'T_blk':>5} {'colsRule':>9} {'cols':>4} {'padBW':>5} {'padBH':>5} {'mismatch':>8} {'predTotalBO':>12}")
    winners=[]
    for T in (8,16,32,64):
        for rule in ('ceil','nextpow2','16KiB'):
            cols=cols_rule(BX,T,rule)
            padBW=cols*T if BX>=T else nextpow2(BX)
            padBH=(-(-BY//T))*T if BY>=T else nextpow2(BY)
            miss=check(T,cols)
            predTot=padBW*padBH*BB
            tag='  <== 0-MISMATCH' if miss==0 else ''
            print(f"#  {T:>5} {rule:>9} {cols:>4} {padBW:>5} {padBH:>5} {miss:>8} 0x{predTot:08x}{tag}")
            if miss==0: winners.append((T,rule,cols,padBW,padBH,predTot))
    print(f"# BO actual size = 0x{bosz:x}")
    for T,rule,cols,padBW,padBH,pt in winners:
        note='(matches BO)' if pt==bosz else f'(pred 0x{pt:x} vs BO 0x{bosz:x})'
        print(f"# CONFIRMED: T_blk={T} cols={cols}({rule}) padBW={padBW} padBH={padBH} predTotal=0x{pt:x} {note}")
    if not winners: print("# NO 0-mismatch model")
    return 0
if __name__=='__main__': sys.exit(main())
