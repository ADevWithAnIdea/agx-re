#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT={"CAPTURE_CONTRACT.json","PRE_REGISTRATION.md","README.md","RESULTS.md","kernels","harness","run.py","analysis.py","make_manifest.py","verify.py","manifest.json"}
AUTH=("PRE_REGISTRATION.md","README.md","RESULTS.md","CAPTURE_CONTRACT.json","kernels/abi_matrix.metal","harness/probe.m","run.py","analysis.py","make_manifest.py","verify.py")
CASES=("sep_f32","interleaved_f32","interleaved_offset","separate_offset","u8norm_to_f32","u8raw_to_u32","u16norm_to_f32","center_perspective","center_no_perspective","flat_varying","direct_constant")
def req(v,s):
 if not v:raise SystemExit("FAIL "+s)
def sh(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def static():
 req(not HERE.is_symlink() and {p.name for p in HERE.iterdir()}==ROOT,"closed root")
 for p in AUTH+("manifest.json",):req((HERE/p).is_file() and not(HERE/p).is_symlink(),"regular "+p)
 for d,n in (("kernels","abi_matrix.metal"),("harness","probe.m")):req((HERE/d).is_dir() and not(HERE/d).is_symlink() and {p.name for p in(HERE/d).iterdir()}=={n},"closed "+d)
 c=json.loads((HERE/"CAPTURE_CONTRACT.json").read_text());req(c["state"]=="PRE_GPU" and tuple(c["cases"])==CASES and tuple(c["authored"])==AUTH and c["boundary"]["binary_archive_bo_inspection"]=="NONE" and c["backings"]["float"]["bytes"]==c["backings"]["uint"]["bytes"]==1152,"contract")
 k=(HERE/"kernels/abi_matrix.metal").read_text();h=(HERE/"harness/probe.m").read_text();req("center_perspective" in k and "center_no_perspective" in k and "f_flat" in k and "binary/archive/BO path" in h,"matrix source")
 want={"schema":1,"state":"PRE_GPU","artifacts":[{"path":p,"bytes":(HERE/p).stat().st_size,"sha256":sh(HERE/p)}for p in AUTH]};req(json.loads((HERE/"manifest.json").read_text())==want,"manifest")
a=argparse.ArgumentParser();g=a.add_mutually_exclusive_group(required=True);g.add_argument("--preflight",action="store_true");g.add_argument("--between-runs",action="store_true");g.add_argument("--captured",action="store_true");x=a.parse_args();static()
if x.preflight:print("PASS PRE_GPU contract; no GPU capture")
else:raise SystemExit("FAIL captured/between-runs unavailable before audited capture implementation")
