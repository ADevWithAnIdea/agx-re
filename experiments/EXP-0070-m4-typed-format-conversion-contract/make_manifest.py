#!/usr/bin/env python3
"""Create/check a manifest for the authored PRE_GPU bundle, never raw results."""
import argparse, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
PATHS=("PRE_REGISTRATION.md","README.md","RESULTS.md","CAPTURE_CONTRACT.json","kernels/format_matrix.metal","harness/probe.m","run.py","analysis.py","make_manifest.py","verify.py")
def captured_paths():
    return tuple(sorted(str(p.relative_to(HERE)) for p in HERE.rglob("*") if p.is_file() and not p.is_symlink() and p.name!="manifest.json"))
def record():
    captured=(HERE/"raw").is_dir()
    paths=captured_paths() if captured else PATHS
    return {"schema":1,"state":"CAPTURED" if captured else "PRE_GPU","artifacts":[{"path":p,"bytes":(HERE/p).stat().st_size,"sha256":hashlib.sha256((HERE/p).read_bytes()).hexdigest()} for p in paths]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--write",action="store_true");ap.add_argument("--check",action="store_true");a=ap.parse_args();x=record();dst=HERE/"manifest.json"
    if a.write: dst.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
    elif a.check:
        if not dst.exists() or json.loads(dst.read_text()) != x: raise SystemExit("manifest stale or absent")
        print("PASS manifest state="+x["state"])
    else: print(json.dumps(x,indent=2,sort_keys=True))
if __name__=="__main__": main()
