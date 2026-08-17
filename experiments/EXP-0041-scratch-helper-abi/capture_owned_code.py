#!/usr/bin/env python3
"""Append OWN-MSL _agc.main captures to an existing EXP-0041 raw run."""
import argparse
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent; H=HERE/"harness"; K=HERE/"kernels"
CASES=[("cs_nospill_k72","cs"),("cs_spill_k80","cs"),("cs_spill_k96","cs"),
       ("cs_spill_k112","cs"),("cs_spill_k160","cs"),("vs_nospill_k72","vs"),
       ("vs_spill_k112","vs"),("fs_nospill_k72","fs"),("fs_spill_k112","fs")]

def main():
    p=argparse.ArgumentParser(); p.add_argument("--run-dir",required=True); a=p.parse_args()
    raw=Path(a.run_dir).resolve()
    if not raw.is_dir(): raise SystemExit(f"missing raw run: {raw}")
    for name,stage in CASES:
        log=raw/f"code_capture_{name}.log"; out=raw/f"code_{name}"
        if log.exists() or out.exists(): raise SystemExit(f"append-only target already exists: {name}")
        cmd=[sys.executable,H/"metadata.py","--source",K/f"{name}.metal","--stage",stage,"--code-dir",out]
        cp=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=100)
        log.write_text(f"COMMAND {cmd!r}\nEXIT {cp.returncode}\nSTDOUT\n{cp.stdout}\nSTDERR\n{cp.stderr}")
        if cp.returncode: raise SystemExit(f"capture failed: {name}; see {log}")
    derived=HERE/"analysis"/(raw.name+"_code_census.txt")
    if derived.exists(): raise SystemExit(f"append-only target exists: {derived}")
    cp=subprocess.run([sys.executable,HERE/"analysis/code_census.py","--raw-dir",raw],capture_output=True,text=True,timeout=30)
    derived.write_text(cp.stdout+cp.stderr)
    if cp.returncode: raise SystemExit(f"census failed: {derived}")
    print(derived)
if __name__=="__main__": main()
