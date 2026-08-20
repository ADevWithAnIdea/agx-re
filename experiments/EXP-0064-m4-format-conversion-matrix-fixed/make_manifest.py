#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
RUNS=("m4_20260820_run01","m4_20260820_run02"); CASES=("rgba8unorm_edges","bgra8unorm_edges","rgba8srgb_threshold","r16unorm_midpoint","rgba16float_edges","r32uint_exact")
def expected():
 p={".gitignore","PRE_REGISTRATION.md","README.md","RESULTS.md","run.py","analysis.py","make_manifest.py","verify.py","kernels/format_matrix.metal","harness/probe.m","analysis.json"}
 for r in RUNS:p|={f"raw/{r}/00_environment.json",f"raw/{r}/01_build.json",f"raw/{r}/format_matrix.metal",f"raw/{r}/run_manifest.json"}|{f"raw/{r}/case_{c}.json" for c in CASES}
 return p
def check(manifest_required=True):
 want=expected()|{"manifest.json"}; seen=set()
 dirs={"kernels","harness","raw"}|{f"raw/{r}" for r in RUNS}
 seen_dirs=set()
 for x in HERE.rglob('*'):
  if x.is_symlink() or (not x.is_dir() and not x.is_file()):raise SystemExit(f"bad type {x}")
  if x.is_dir():seen_dirs.add(str(x.relative_to(HERE)))
  if x.is_file():seen.add(str(x.relative_to(HERE)))
 if seen!=want:raise SystemExit(f"path mismatch {sorted(seen^want)}")
 if seen_dirs!=dirs:raise SystemExit(f"directory mismatch {sorted(seen_dirs^dirs)}")
def main():
 check(False); out=[]
 for rel in sorted(expected()):
  x=HERE/rel;out.append({"path":rel,"bytes":x.stat().st_size,"sha256":hashlib.sha256(x.read_bytes()).hexdigest()})
 (HERE/'manifest.json').write_text(json.dumps({"artifacts":out,"runs":RUNS,"cases":CASES,"clean_room":"public Metal + own source/readbacks only"},indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
