#!/usr/bin/env python3
import sys, importlib.util
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]; REPO = EXP.parents[1]
sys.path.insert(0, str(REPO/"tools"/"agx-isa")); import isadb
def load(n,p):
    s=importlib.util.spec_from_file_location(n,str(p)); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse = load("agxparse", REPO/"tools"/"shdump"/"agxparse.py")
for fn in sys.argv[1:]:
    buf = (HERE/("recon_%s.bin"%fn)).read_bytes()
    _, pieces = agxparse.extract_agx(buf); mb = pieces["_agc.main"]
    recs, leftover = isadb.disassemble(mb); off=0
    print("=== %s (%dB)"%(fn,len(mb)))
    for r in recs:
        print("  +0x%03x %-16s %s %s"%(off, r["mnemonic"], mb[off:off+r["length"]].hex(), r["fields"]))
        off+=r["length"]
    if leftover: print("  LEFTOVER", leftover.hex())
