#!/usr/bin/env python3
# ilogic 2-input LUT: sweep op_base(byte+2) in {0x1e xor-base,0x1f andor-base} x
# invert byte+4 (0..255) x byte+5 bit3, decode truth table from out&0xF (a=0xC,b=0xA).
# Report which of the 16 boolean functions are reachable and the minimal encoding
# for each canonical function (FALSE,AND,OR,XOR,NAND,NOR,XNOR,~a,~b,a,b,andn,orn,...).
import sys, os, subprocess, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner
ARCH="iand.bin"; SRC="kernels/rt1a_iand.metal"
OFF=int(subprocess.check_output(["python3","agxparse.py",ARCH,"--locate","_agc.main"],text=True).split()[0])
B2=OFF+0x20+2; B4=OFF+0x20+4; B5=OFF+0x20+5
base=open(ARCH,"rb").read()
open("ca.bin","wb").write(struct.pack("<I",0xC)); open("cb.bin","wb").write(struct.pack("<I",0xA))
names={0:"FALSE",1:"NOR",2:"andn(~a&b)",3:"~a",4:"andn(a&~b)",5:"~b",6:"XOR",7:"NAND",
       8:"AND",9:"XNOR",10:"b",11:"orn(~a|b)",12:"a",13:"orn(a|~b)",14:"OR",15:"TRUE"}
r=PersistRunner(source=SRC,function="k",fast_math=False,agxrun_persist="./agxrun_persist")
reach={}   # tt -> (b2,b4,b5)
try:
    for b2 in (0x1e,0x1f):
        for b5bit in (0,0x08):
            for b4 in range(256):
                sp=bytearray(base); sp[B2]=b2; sp[B4]=b4; sp[B5]=(base[B5]&~0x08)|b5bit
                open("lc.bin","wb").write(sp)
                resp=r.request(archive="lc.bin",grid=1,tg=1,ins={1:"ca.bin",2:"cb.bin"},outs={0:4},timeout=5)
                if resp["status"]!="OK" or 0 not in resp["outs"]: continue
                tt=struct.unpack("<I",resp["outs"][0])[0]&0xF
                reach.setdefault(tt,(b2,b4,base[B5]|b5bit if b5bit else base[B5]&~0x08))
finally:
    r.close()
print(f"# reachable boolean functions: {len(reach)}/16")
for tt in range(16):
    if tt in reach:
        b2,b4,b5=reach[tt]
        print(f"  tt=0x{tt:x} {names[tt]:12s}  via b+2=0x{b2:02x} b+4=0x{b4:02x} b+5=0x{b5:02x}")
    else:
        print(f"  tt=0x{tt:x} {names[tt]:12s}  NOT REACHED")
