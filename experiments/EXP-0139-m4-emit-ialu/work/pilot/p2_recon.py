#!/usr/bin/env python3
"""EXP-0139 PILOT step 2 (disclosed, non-gated): compile our own probe MSL and
tokenize each _agc.main with tools/agx-isa to locate live anchors for every
target mnemonic. Compile-only; no dispatch."""
import subprocess, sys, importlib.util
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb
def load(n,p):
    s=importlib.util.spec_from_file_location(n,str(p)); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse = load("agxparse", REPO/"tools"/"shdump"/"agxparse.py")
TARGETS = set("iadd2 ibfe ibfe_mesh_attr ibfins ibitcount icmp_pred icmpsel imad iminmax isel10 isel10_c isel8 isel_reg isel_reg8 ishift iunary".split())
src = EXP/"kernels"/"ialu_probes.metal"
funcs = [l.split("void ")[1].split("(")[0] for l in src.read_text().splitlines() if l.startswith("kernel void ")]
for fn in funcs:
    out = HERE/("recon_%s.bin" % fn)
    r = subprocess.run([str(EXP/"work"/"bin"/"shdump"), "-o", str(out), "-f", fn,
                        "--no-fast-math", str(src)], capture_output=True, text=True)
    if r.returncode != 0:
        print("== %-14s SHDUMP FAIL %s" % (fn, r.stderr[-200:])); continue
    buf = out.read_bytes()
    _, pieces = agxparse.extract_agx(buf)
    mb = pieces["_agc.main"]
    recs, leftover = isadb.disassemble(mb)
    off = 0; hits=[]
    for rec in recs:
        if rec["mnemonic"] in TARGETS:
            hits.append((off, rec["mnemonic"], mb[off:off+rec["length"]].hex(), rec["fields"]))
        off += rec["length"]
    print("== %-14s main=%dB instrs=%d leftover=%d" % (fn, len(mb), len(recs), len(leftover)))
    for o,m,h,f in hits:
        print("     +0x%03x %-12s %s  %s" % (o, m, h, f))
