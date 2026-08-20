#!/usr/bin/env python3
"""Future opt-in runner; no device operation without explicit authorization."""
import argparse,hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
AUTH=("PRE_REGISTRATION.md","README.md","RESULTS.md","CAPTURE_CONTRACT.json","kernels/abi_matrix.metal","harness/probe.m","run.py","analysis.py","make_manifest.py","verify.py")
def main():
 a=argparse.ArgumentParser();a.add_argument("--run-id");a.add_argument("--execute",action="store_true");x=a.parse_args()
 if not x.execute:raise SystemExit("refusing device operation without --execute")
 if x.run_id not in ("m4-TODO-run01","m4-TODO-run02"):raise SystemExit("contracted append-only ID required")
 gate="--preflight" if x.run_id.endswith("01") else "--between-runs"
 if subprocess.run(["python3","-B","verify.py",gate],cwd=HERE).returncode:raise SystemExit("gate failed")
 raise SystemExit("capture implementation remains frozen pending audit; no operation performed")
if __name__=="__main__":main()
