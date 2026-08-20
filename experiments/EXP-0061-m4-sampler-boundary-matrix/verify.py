#!/usr/bin/env python3
import hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent; REPO=HERE.parents[1]; raw=HERE/"raw/m4-20260820-run01"
ROOT={".gitignore","PRE_REGISTRATION.md","README.md","RESULTS.md","harness","raw","run.py","verify.py"}
KEYS={"experiments/EXP-0061-m4-sampler-boundary-matrix/PRE_REGISTRATION.md":"68c3ad886ce103de37fc6eb39ebfddc9a96f86ba7587246f62f83cdac0652e73","experiments/EXP-0061-m4-sampler-boundary-matrix/harness/probe.m":"1c0551cd33946b8e6f36e4b7f8e2b42dbdf6dd7acbb736efe5f974403d5f5574","experiments/EXP-0061-m4-sampler-boundary-matrix/run.py":"b0add29c8776c437618af2f0116073d63e6cc222386541c7cf131ab85bd80189"}
assert not HERE.is_symlink() and {p.name for p in HERE.iterdir()} in (ROOT,ROOT|{"work"})
for n in ROOT-{"harness","raw"}:assert (HERE/n).is_file() and not (HERE/n).is_symlink()
assert not (HERE/"harness").is_symlink() and {p.name for p in (HERE/"harness").iterdir()}=={"probe.m"} and not (HERE/"harness/probe.m").is_symlink()
if (HERE/"work").exists():assert not (HERE/"work").is_symlink() and (HERE/"work").is_dir() and not list((HERE/"work").iterdir())
assert not (HERE/"raw").is_symlink() and {p.name for p in (HERE/"raw").iterdir()}=={"m4-20260820-run01"}
assert not raw.is_symlink() and {p.name for p in raw.iterdir()}=={"00_inputs.json","01_build.json"} and all(p.is_file() and not p.is_symlink() for p in raw.iterdir())
i=json.loads((raw/"00_inputs.json").read_text());assert i=={"inputs":KEYS,"revision":"cb29ed88b36025abe7a9204bb1a20d3a67cd1c55"}
assert subprocess.run(["git","cat-file","-e",i["revision"]+"^{commit}"],cwd=REPO).returncode==0 and subprocess.run(["git","merge-base","--is-ancestor",i["revision"],"HEAD"],cwd=REPO).returncode==0
for rel,want in KEYS.items():assert hashlib.sha256(subprocess.run(["git","show",i["revision"]+":"+rel],cwd=REPO,capture_output=True,check=True).stdout).hexdigest()==want
b=json.loads((raw/"01_build.json").read_text());assert set(b)=={"exit","stdout","stderr"} and b["exit"]==1 and b["stdout"]=="" and "simd_float4" in b["stderr"]
print("PASS stopped pre-GPU build failure retained")
