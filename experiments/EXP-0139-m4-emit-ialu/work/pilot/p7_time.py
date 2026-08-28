#!/usr/bin/env python3
import sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]
sys.path.insert(0,str(EXP/"harness")); import sweeprun as S
SRC=EXP/"kernels"/"ialu_probes.metal"
A=[0x12345678,0xFFFFFFFF,0x0000FF00,0xDEADBEEF,1,0,0x80000000,0x7FFFFFFF]
B=[3,5,8,1,31,32,2,0]
c=S.Carrier(SRC,"k_pop",HERE/"work",timeout=8.0)
a=c.write_input("a.bin",A); b=c.write_input("b.bin",B)
r,iw,fw=c.run([],{0:a,1:b},2,8,8,8)
print("baseline popcount",[hex(x) for x in iw],r["status"])
t0=time.time()
NC=64
for v in range(NC):
    c.run([(0x012+7, bytes([v]))],{0:a,1:b},2,8,8,8)
dt=time.time()-t0
print("%d cases in %.2fs -> %.1f ms/case" % (NC,dt,1000*dt/NC))
# iunary probe: set byte+1 bit1 so the tight ibitcount match fails
import importlib.util
sys.path.insert(0,str(EXP.parents[1]/"tools"/"agx-isa")); import isadb
for b1 in (0x05,0x07,0x0d,0x45):
    blob=bytes([0x27,b1,0x56,0x00,0x02,0x00,0x5c,0x04])
    recs,left=isadb.disassemble(blob)
    r,iw,_=c.run([(0x012,blob)],{0:a,1:b},2,8,8,8)
    print("b1=%02x tok=%s len=%s -> %s %s"%(b1,recs[0]["mnemonic"],recs[0]["length"],r["status"],[hex(x) for x in iw[:4]]))
c.close()
