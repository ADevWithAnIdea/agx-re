#!/usr/bin/env python3
# Falsify tex_write (0xd7) data-source byte by splicing the first write op and
# reading back the image. Baseline: texel(0,0)=(0.1,0.2,0.3,0.4).
import subprocess
ARCH="texw.bin"; SRC="kernels/tex_write.metal"
o=subprocess.check_output(["python3","agxparse.py",ARCH,"--stage","compute","--locate","_agc.main"],text=True)
moff=int(o.split()[0]); base=bytearray(open(ARCH,"rb").read())
def run(a):
    out=subprocess.check_output(["./texrun","--archive",a,"--source",SRC,"--function","k","--no-fast-math",
        "--grid","1","--tg","1","--rwtex","0=2,1","--buf","0=vw.bin"],text=True,stderr=subprocess.STDOUT)
    r=next((l for l in out.splitlines() if l.startswith("RWTEX")),None)
    return r if r else [l for l in out.splitlines() if l.startswith("STATUS")]
OP=0x58  # first 0xd7 tex_write
print("first-write op bytes:", bytes(base[moff+OP:moff+OP+16]).hex())
print("baseline:", run(ARCH))
for rel in [3,5,8,9,12,13]:
    for v in [0x00,0x02,0x08]:
        b=bytearray(base); b[moff+OP+rel]=v; open("tw.bin","wb").write(b)
        res=run("tw.bin")
        print("  byte+%d = 0x%02x -> %s" % (rel,v,res))
