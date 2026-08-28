#!/usr/bin/env python3
import subprocess, sys, importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]; REPO=EXP.parents[1]
sys.path.insert(0,str(REPO/"tools"/"agx-isa")); import isadb
def load(n,p):
    s=importlib.util.spec_from_file_location(n,str(p)); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse=load("agxparse",REPO/"tools"/"shdump"/"agxparse.py")
TARGETS=set("iadd2 ibfe ibfe_mesh_attr ibfins ibitcount icmp_pred icmpsel imad iminmax isel10 isel10_c isel8 isel_reg isel_reg8 ishift iunary irotate".split())
src=EXP/"kernels"/"ialu_probes.metal"
funcs=[l.split("void ")[1].split("(")[0] for l in src.read_text().splitlines() if l.startswith("kernel void ")]
seen={}
for fn in funcs:
    out=HERE/("r3_%s.bin"%fn)
    r=subprocess.run([str(EXP/"work"/"bin"/"shdump"),"-o",str(out),"-f",fn,"--no-fast-math",str(src)],capture_output=True,text=True)
    if r.returncode!=0: print("== %-12s FAIL"%fn); continue
    _,pieces=agxparse.extract_agx(out.read_bytes()); mb=pieces["_agc.main"]
    recs,left=isadb.disassemble(mb); off=0; hits=[]
    for rec in recs:
        if rec["mnemonic"] in TARGETS:
            hits.append((off,rec["mnemonic"],mb[off:off+rec["length"]].hex()))
            seen.setdefault(rec["mnemonic"],[]).append((fn,off,len(mb)))
        off+=rec["length"]
    print("== %-12s %dB %d instrs :: %s"%(fn,len(mb),len(recs)," ".join("+0x%03x %s(%s)"%h for h in hits)))
print()
for m in sorted(TARGETS):
    print("%-16s %s"%(m, seen.get(m,"** NO ANCHOR **")))
