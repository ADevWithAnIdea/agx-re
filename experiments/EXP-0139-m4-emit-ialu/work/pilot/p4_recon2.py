#!/usr/bin/env python3
import subprocess, sys, importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]; REPO=EXP.parents[1]
sys.path.insert(0,str(REPO/"tools"/"agx-isa")); import isadb
def load(n,p):
    s=importlib.util.spec_from_file_location(n,str(p)); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse=load("agxparse",REPO/"tools"/"shdump"/"agxparse.py")
src=HERE/"probes2.metal"
funcs=[l.split("void ")[1].split("(")[0] for l in src.read_text().splitlines() if l.startswith("kernel void ")]
for fn in funcs:
    out=HERE/("r2_%s.bin"%fn)
    r=subprocess.run([str(EXP/"work"/"bin"/"shdump"),"-o",str(out),"-f",fn,"--no-fast-math",str(src)],capture_output=True,text=True)
    if r.returncode!=0: print("== %-12s FAIL %s"%(fn,r.stderr[-150:])); continue
    _,pieces=agxparse.extract_agx(out.read_bytes()); mb=pieces["_agc.main"]
    recs,left=isadb.disassemble(mb); off=0; body=[]
    for rec in recs:
        body.append("+0x%03x %s(%s)"%(off,rec["mnemonic"],mb[off:off+rec["length"]].hex()))
        off+=rec["length"]
    print("== %-12s %s"%(fn," ".join(body)))
