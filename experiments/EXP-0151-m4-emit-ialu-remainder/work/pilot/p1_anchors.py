import sys, subprocess, importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parents[2]
REPO=HERE.parents[1]
sys.path.insert(0,str(REPO/"tools"/"agx-isa"))
import isadb
spec=importlib.util.spec_from_file_location("agxparse",REPO/"tools"/"shdump"/"agxparse.py")
ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
BIN=HERE/"work"/"bin"; SRC=HERE/"kernels"/"ialu_rem.metal"
fns=sys.argv[1:]
for fn in fns:
    out=HERE/"work"/"pilot"/("c_%s.bin"%fn)
    r=subprocess.run([str(BIN/"shdump"),"-o",str(out),"-f",fn,"--no-fast-math",str(SRC)],capture_output=True,text=True,timeout=180)
    if r.returncode: print(fn,"FAIL",r.stderr[-300:]); continue
    _,pieces=ap.extract_agx(out.read_bytes())
    m=pieces["_agc.main"]
    recs,left=isadb.disassemble(m)
    print("="*72); print(fn,"len",len(m),"leftover",len(left))
    off=0
    for rr in recs:
        print("  +%03d %-16s %-28s %s"%(off,rr["mnemonic"],m[off:off+rr["length"]].hex(),
             {k:v for k,v in rr["fields"].items()}))
        off+=rr["length"]
