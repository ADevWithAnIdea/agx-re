#!/usr/bin/env python3
"""EXP-0139 pilot: compile the carrier once, report _agc.main geometry."""
import subprocess, sys, os, importlib.util
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
REPO = EXP.parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
agxparse = load("agxparse", REPO/"tools"/"shdump"/"agxparse.py")
src = EXP/"kernels"/"carrier_dag.metal"
base = HERE/"base.bin"
r = subprocess.run([str(EXP/"work"/"bin"/"shdump"), "-o", str(base), "-f", "k",
                    "--no-fast-math", str(src)], capture_output=True, text=True)
print("shdump rc", r.returncode, r.stderr[-400:] if r.returncode else "")
buf = base.read_bytes()
loc = agxparse.locate_region(buf, "_agc.main")
print("locate_region:", loc)
_, pieces = agxparse.extract_agx(buf)
mb = pieces["_agc.main"]
print("main len", len(mb))
print("head hex", mb[:64].hex())
