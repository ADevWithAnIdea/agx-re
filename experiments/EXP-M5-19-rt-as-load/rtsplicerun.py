#!/usr/bin/env python3
# Device-side: splice bytes into rtk.bin archive's _agc.main region, run rtsplice (real AS).
# Usage: rtsplicerun.py OFF=HEX [OFF=HEX ...]   (offsets are into _agc.main)
import sys, os, subprocess, importlib.util
HERE=os.path.expanduser("~/cleanroom_work/EXP-M5-19")
PARSE=os.path.expanduser("~/cleanroom_work/tools/shdump/agxparse.py")
spec=importlib.util.spec_from_file_location("agxparse", PARSE)
ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

with open(os.path.join(HERE,"rtk.bin"),"rb") as f: buf=bytearray(f.read())
loc=ap.locate_region(bytes(buf),"_agc.main")
if loc is None: print("LOCATE_FAIL"); sys.exit(2)
base,length=loc
notes=[]
for sp in sys.argv[1:]:
    off,_,hx=sp.partition("=")
    off=int(off,0); nb=bytes.fromhex(hx)
    ao=base+off
    old=bytes(buf[ao:ao+len(nb)])
    buf[ao:ao+len(nb)]=nb
    notes.append(f"_agc.main@{off:#06x}: {old.hex()} -> {nb.hex()} (abs {ao:#x})")
outp=os.path.join(HERE,"rtk_spliced.bin")
with open(outp,"wb") as f: f.write(buf)
for n in notes: print("SPLICE",n)
r=subprocess.run(["./rtsplice","--archive","rtk_spliced.bin","--source","rtk.metal","--function","rtk"],
                 cwd=HERE, capture_output=True, text=True, timeout=30)
sys.stdout.write(r.stdout)
if r.stderr.strip(): sys.stderr.write(r.stderr)
