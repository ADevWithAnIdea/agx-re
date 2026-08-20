#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
P=("PRE_REGISTRATION.md","README.md","RESULTS.md","CAPTURE_CONTRACT.json","kernels/abi_matrix.metal","harness/probe.m","run.py","analysis.py","make_manifest.py","verify.py")
def r():return {"schema":1,"state":"PRE_GPU","artifacts":[{"path":p,"bytes":(HERE/p).stat().st_size,"sha256":hashlib.sha256((HERE/p).read_bytes()).hexdigest()}for p in P]}
a=argparse.ArgumentParser();a.add_argument("--write",action="store_true");a.add_argument("--check",action="store_true");x=a.parse_args();m=HERE/"manifest.json"
if x.write:m.write_text(json.dumps(r(),indent=2,sort_keys=True)+"\n")
elif x.check:
 if not m.exists() or json.loads(m.read_text())!=r():raise SystemExit("manifest stale")
 print("PASS PRE_GPU manifest")
else:print(json.dumps(r(),indent=2,sort_keys=True))
