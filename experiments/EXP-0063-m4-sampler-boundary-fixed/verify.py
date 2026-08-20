#!/usr/bin/env python3
import hashlib,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
ROOT={".gitignore","PRE_REGISTRATION.md","README.md","RESULTS.md","harness","raw","run.py","verify.py"}
KEYS={"experiments/EXP-0063-m4-sampler-boundary-fixed/PRE_REGISTRATION.md","experiments/EXP-0063-m4-sampler-boundary-fixed/harness/probe.m","experiments/EXP-0063-m4-sampler-boundary-fixed/run.py"}
assert not HERE.is_symlink() and {p.name for p in HERE.iterdir()}==ROOT
assert all((HERE/n).is_file() and not (HERE/n).is_symlink() for n in ROOT-{"harness","raw"})
assert not (HERE/"harness").is_symlink() and {p.name for p in (HERE/"harness").iterdir()}=={"probe.m"}
assert (HERE/"harness/probe.m").is_file() and not (HERE/"harness/probe.m").is_symlink()
assert not (HERE/"raw").is_symlink() and {p.name for p in (HERE/"raw").iterdir()}=={"m4-20260820-run01","m4-20260820-run02"}
outs=[]
for run in ("m4-20260820-run01","m4-20260820-run02"):
 d=HERE/"raw"/run;assert not d.is_symlink() and {p.name for p in d.iterdir()}=={"00_inputs.json","01_build.json","02_run.json"} and all(p.is_file() and not p.is_symlink() for p in d.iterdir())
 i=json.loads((d/"00_inputs.json").read_text());assert set(i)=={"revision","inputs"} and set(i["inputs"])==KEYS
 assert subprocess.run(["git","cat-file","-e",i["revision"]+"^{commit}"],cwd=REPO).returncode==0 and subprocess.run(["git","merge-base","--is-ancestor",i["revision"],"HEAD"],cwd=REPO).returncode==0
 for rel,want in i["inputs"].items():assert hashlib.sha256(subprocess.run(["git","show",i["revision"]+":"+rel],cwd=REPO,capture_output=True,check=True).stdout).hexdigest()==want
 b=json.loads((d/"01_build.json").read_text());assert b=={"exit":0,"stdout":"","stderr":""}
 r=json.loads((d/"02_run.json").read_text());assert set(r)=={"exit","stdout","stderr"} and r["exit"]==0 and r["stderr"]=="";outs.append(r["stdout"])
assert outs[0]==outs[1] and "CASE mode=zero filter=nearest 0,0,0,0" in outs[0] and "CASE mode=edge filter=nearest 1,0,0,1" in outs[0] and "CASE mode=repeat filter=nearest 0,1,0,1" in outs[0]
lines=outs[0].splitlines();assert len(lines)==8 and all(re.fullmatch(r"CASE mode=(zero|edge|repeat) filter=(nearest|linear)(?: [0-9.,-]+){4}",x) for x in lines[:6]) and lines[6]=="DEVICE Apple M4" and lines[-1]=="RESULT ok=1"
for line in lines[:6]:
 for vector in line.split()[3:]:assert len(vector.split(","))==4 and all(re.fullmatch(r"-?(?:\d+(?:\.\d*)?|\.\d+)",x) for x in vector.split(","))
assert [x.split(" filter=")[0] for x in lines[:6]]==["CASE mode=zero","CASE mode=zero","CASE mode=edge","CASE mode=edge","CASE mode=repeat","CASE mode=repeat"]
assert lines[0].replace("nearest","linear")==lines[1] and lines[2].replace("nearest","linear")==lines[3] and lines[4].replace("nearest","linear")==lines[5]
print("PASS public runs repeat; filter distinction falsified")
