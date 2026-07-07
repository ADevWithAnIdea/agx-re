#!/usr/bin/env python3
# rt_controls.py -- prove rtrun splicing IS effective (control splices), so the
# inert AS-select/mode/result-reg splices in rt_test.py are real negative results.
import subprocess
SRC="kernels/rt_query.metal"; ARCH="rtq.bin"
o=subprocess.check_output(["python3","agxparse.py",ARCH,"--stage","compute","--locate","_agc.main"],text=True)
moff=int(o.split()[0]); base=bytearray(open(ARCH,"rb").read())
def run(a,ray="0.2,0.2,0,0,0,1"):
    try: out=subprocess.check_output(["./rtrun","--archive",a,"--source",SRC,"--function","k","--no-fast-math","--ray",ray,"--out","4"],text=True,stderr=subprocess.STDOUT,timeout=20)
    except subprocess.CalledProcessError as e: return "FAULT:"+(e.output.strip().splitlines()[-1] if e.output else "?")
    except subprocess.TimeoutExpired: return "HANG"
    for ln in out.splitlines():
        if ln.startswith("OUT "): return ln[4:]
    return [l for l in out.splitlines() if l.startswith("STATUS")]
print("baseline:", run(ARCH))
b=bytearray(base); b[moff+0x55]=0x00; open("c1.bin","wb").write(b); print("CTRL traverse byte+1 0xea->0x00 :", run("c1.bin"))
b=bytearray(base); b[moff+0x58d]=0x00; open("c2.bin","wb").write(b); print("CTRL result-read byte+1 0xea->0x00:", run("c2.bin"))
b=bytearray(base)
for i in range(8): b[moff+0x54+i]=0xff
open("c3.bin","wb").write(b); print("CTRL traverse op -> 0xff*8      :", run("c3.bin"))
