#!/usr/bin/env python3
# a_reg.py -- RT-12: print a byte region of the fw-ctx/client BO at a given low-VA from an
# iotrace dump dir. Also supports scanning a whole BO for a u16/u32 opcode. DATA only.
# usage:  a_reg.py DUMPDIR VA_HEX START_HEX END_HEX
#         a_reg.py DUMPDIR VA_HEX --scan16 0x6404 0x6432 0x61c4 0x61f2 ...
#         a_reg.py DUMPDIR VA_HEX --scan32 0x70000600 ...
import sys, re, glob, os
HEXLINE=re.compile(r"^([0-9a-f]{8}):\s+(.*)$")
def load(path):
    data=bytearray()
    for line in open(path):
        m=HEXLINE.match(line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(" ",""))
        if len(data)<off+len(b): data.extend(b"\x00"*(off+len(b)-len(data)))
        data[off:off+len(b)]=b
    return bytes(data)
def find_bo(d,va):
    g=glob.glob(os.path.join(d,f"bo_*_va{va}_*.hex"))
    return g[0] if g else None
d=sys.argv[1]; va=sys.argv[2]
p=find_bo(d,va)
if not p: print("NO BO",va,"in",d); sys.exit(1)
data=load(p)
if len(sys.argv)>3 and sys.argv[3]=="--scan16":
    for t in sys.argv[4:]:
        tv=int(t,16); nb=tv.to_bytes(2,"little"); hits=[]
        i=data.find(nb)
        while i!=-1: hits.append(f"0x{i:x}"); i=data.find(nb,i+2)
        print(f"  op16 0x{tv:04x}: {len(hits)} hit(s) at {hits[:12]}")
elif len(sys.argv)>3 and sys.argv[3]=="--scan32":
    for t in sys.argv[4:]:
        tv=int(t,16); nb=tv.to_bytes(4,"little"); hits=[]
        i=data.find(nb)
        while i!=-1: hits.append(f"0x{i:x}"); i=data.find(nb,i+4)
        print(f"  op32 0x{tv:08x}: {len(hits)} hit(s) at {hits[:12]}")
else:
    start=int(sys.argv[3],16); end=int(sys.argv[4],16)
    for off in range(start,end,4):
        w=data[off:off+4]; le=int.from_bytes(w,"little")
        print(f"  +0x{off:03x}: bytes={w.hex()} le32=0x{le:08x}")
