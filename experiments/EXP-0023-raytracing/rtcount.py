#!/usr/bin/env python3
# EXP-0023 RT op counter. Uses the (now fairly complete) rtlen.L length rule and
# RESYNCS on failure by scanning to the next offset that begins a run of >=RUN
# cleanly-parseable instructions. Counts the dedicated RT opcode groups, detects
# backward-jump traversal loops, and reports the clean-coverage fraction so we can
# judge how much of the stream we trust. CLEAN-ROOM: OUR OWN compiled bytes only.
import sys, importlib.util
spec=importlib.util.spec_from_file_location("rtlen","rtlen.py")
rtlen=importlib.util.module_from_spec(spec); spec.loader.exec_module(rtlen)
L=rtlen.L
RUN=4
def run_ok(b,o,need):
    c=0
    while o<len(b) and c<need:
        Lv=L(b,o)
        if Lv is None or o+Lv>len(b): break
        o+=Lv; c+=1
    return c
def tok(b):
    o=0; recs=[]; resync=0; uncov=0
    while o<len(b):
        Lv=L(b,o)
        if Lv is not None and o+Lv<=len(b):
            recs.append((o,b[o],Lv)); o+=Lv; continue
        start=o; oo=o+2
        while oo<len(b):
            if L(b,oo) is not None and run_ok(b,oo,RUN)>=min(RUN,(len(b)-oo)//4 or 1):
                break
            oo+=2
        resync+=1; uncov+=oo-start
        recs.append((-1,b[start],oo-start)); o=oo
    return recs,resync,uncov
def main():
    path=sys.argv[1] if len(sys.argv)>1 else 'raw/mains.txt'
    want=[a for a in sys.argv[2:] if not a.startswith('-')]
    for line in open(path):
        line=line.strip()
        if not line or line.startswith('#'): continue
        p=line.split(); grp,fn,h=p[0],p[1],p[-1]
        if want and fn not in want: continue
        if not all(c in '0123456789abcdef' for c in h.lower()): continue
        b=bytes.fromhex(h); recs,resync,uncov=tok(b)
        c04=sum(1 for o,b0,Lv in recs if o>=0 and (b0&0x0f)==0x4)
        cdf=sum(1 for o,b0,Lv in recs if o>=0 and b0==0xdf)
        c5f=sum(1 for o,b0,Lv in recs if o>=0 and b0==0x5f)
        c27=sum(1 for o,b0,Lv in recs if o>=0 and (b0&0x0f)==0x2 and rtlen.B(b,o+2)==0x27)
        backj=[]
        for o,b0,Lv in recs:
            if o>=0 and b0==0x0f and Lv==10 and b[o+1]==0x00 and b[o+2]==0x54:
                off=int.from_bytes(b[o+3:o+8],'little',signed=True)
                if off<0: backj.append((o,off))
        cov=100*(len(b)-uncov)/len(b)
        print(f"{fn:16s} {len(b):5d}B  cov={cov:5.1f}%  resyncs={resync:2d}  "
              f"RT(0x?4)={c04:3d} 0xdf={cdf:3d} 0x5f={c5f:3d} rt2/27={c27:3d}  backjumps={len(backj)} {backj[:4]}")
if __name__=='__main__': main()
