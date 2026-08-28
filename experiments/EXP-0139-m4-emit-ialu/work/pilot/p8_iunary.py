#!/usr/bin/env python3
"""PILOT: find a LIVE `iunary`-tokenizing member (8-byte, byte0=0x27) whose
`operand` bytes reach the output, so the field can actually be swept."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]
sys.path.insert(0,str(EXP/"harness")); import sweeprun as S
sys.path.insert(0,str(EXP.parents[1]/"tools"/"agx-isa")); import isadb
SRC=EXP/"kernels"/"ialu_probes.metal"
A=[0x12345678,0xFFFFFFFF,0x0000FF00,0xDEADBEEF,1,0,0x80000000,0x7FFFFFFF]
B=[3,5,8,1,31,32,2,0]
POP=[bin(x).count("1") for x in A]
c=S.Carrier(SRC,"k_pop",HERE/"work",timeout=8.0)
a=c.write_input("a.bin",A); b=c.write_input("b.bin",B)
r,base,_=c.run([],{0:a,1:b},2,8,8,8)
print("baseline",base,"expect",POP)
live=[]
for b1 in range(0,64):
    for b2 in (0x56,0x54,0x10,0x22,0x26,0x07,0x66,0x46,0x76):
        blob=bytes([0x27,b1,b2,0x00,0x02,0x00,0x5c,0x04])
        recs,_=isadb.disassemble(blob)
        if not recs or recs[0]["mnemonic"]!="iunary" or recs[0]["length"]!=8: continue
        r,iw,_=c.run([(0x012,blob)],{0:a,1:b},2,8,8,8)
        if r["status"]!="OK": print("  b1=%02x b2=%02x %s"%(b1,b2,r["status"])); continue
        if all(x==0 for x in iw): continue
        # is `operand` live? change byte+5 (src) and see if the answer moves
        blob2=bytes([0x27,b1,b2,0x00,0x02,0x04,0x5c,0x04])
        r2,iw2,_=c.run([(0x012,blob2)],{0:a,1:b},2,8,8,8)
        tag="LIVE-OPERAND" if iw2!=iw else "operand-inert"
        live.append((b1,b2,iw[:4],iw2[:4],tag))
        print("  b1=%02x b2=%02x -> %s | src=4 -> %s  %s"%(b1,b2,[hex(x) for x in iw[:4]],[hex(x) for x in iw2[:4]],tag))
print("live members:",len(live))
c.close()
