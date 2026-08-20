#!/usr/bin/env python3
"""Strict post-capture verifier for public-output-only EXP-0066."""
import datetime,hashlib,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
ROOT={"PRE_REGISTRATION.md","README.md","RESULTS.md","harness","raw","run.py","verify.py"}
KEYS={"experiments/EXP-0066-m4-sampler-filter-provenance/PRE_REGISTRATION.md","experiments/EXP-0066-m4-sampler-filter-provenance/run.py","experiments/EXP-0066-m4-sampler-filter-provenance/verify.py","experiments/EXP-0066-m4-sampler-filter-provenance/harness/probe.m"}
assert not HERE.is_symlink() and {p.name for p in HERE.iterdir()}==ROOT and all((HERE/x).is_file() and not (HERE/x).is_symlink() for x in ROOT-{"harness","raw"})
assert not (HERE/"harness").is_symlink() and {p.name for p in (HERE/"harness").iterdir()}=={"probe.m"} and (HERE/"harness/probe.m").is_file() and not (HERE/"harness/probe.m").is_symlink()
assert not (HERE/"raw").is_symlink() and {p.name for p in (HERE/"raw").iterdir()}=={"m4-20260820-run01","m4-20260820-run02"}
outs=[]
for rid in ("m4-20260820-run01","m4-20260820-run02"):
 d=HERE/"raw"/rid;assert d.is_dir() and not d.is_symlink() and {p.name for p in d.iterdir()}=={"00_inputs.json","01_build.json","02_run.json"} and all(p.is_file() and not p.is_symlink() for p in d.iterdir())
 i=json.loads((d/"00_inputs.json").read_text());assert set(i)=={"schema","revision","inputs","boundary"} and i["schema"]==1 and set(i["inputs"])==KEYS and i["boundary"]=={"binary_archive_bo_inspection":"NONE","target":"M4 public Metal only"}
 assert subprocess.run(["git","cat-file","-e",i["revision"]+"^{commit}"],cwd=REPO).returncode==0 and subprocess.run(["git","merge-base","--is-ancestor",i["revision"],"HEAD"],cwd=REPO).returncode==0
 for rel,want in i["inputs"].items():assert hashlib.sha256(subprocess.run(["git","show",i["revision"]+":"+rel],cwd=REPO,capture_output=True,check=True).stdout).hexdigest()==want
 b=json.loads((d/"01_build.json").read_text());r=json.loads((d/"02_run.json").read_text())
 for x,t in ((b,60),(r,45)):assert set(x)=={"argv","cwd","environment_overrides","timeout_seconds","started_utc","exit","stdout","stderr"} and x["environment_overrides"]=={} and x["timeout_seconds"]==t and x["exit"]==0 and datetime.datetime.fromisoformat(x["started_utc"]).utcoffset()==datetime.timedelta()
 root=b["cwd"];probe=root+"/raw/"+rid+"/probe-unretained";assert b["cwd"]==r["cwd"] and b["stdout"]==b["stderr"]==r["stderr"]=="" and b["argv"]==["xcrun","clang","-arch","arm64e","-fobjc-arc","-o",probe,root+"/harness/probe.m","-framework","Metal","-framework","Foundation"] and r["argv"]==[probe]
 outs.append(r["stdout"])
assert outs[0]==outs[1];lines=outs[0].splitlines();assert len(lines)==8 and lines[6]=="DEVICE Apple M4" and lines[7]=="RESULT ok=1"
assert all(re.fullmatch(r"CASE mode=(zero|edge|repeat) filter=(nearest|linear)(?: [0-9.,-]+){4}",x) for x in lines[:6])
for line in lines[:6]:
 for v in line.split()[3:]:assert len(v.split(","))==4 and all(re.fullmatch(r"-?(?:\d+(?:\.\d*)?|\.\d+)",z) for z in v.split(","))
assert [x.split()[1] for x in lines[:6]]==["mode=zero","mode=zero","mode=edge","mode=edge","mode=repeat","mode=repeat"]
for n in (0,2,4):
 a=lines[n].split();b=lines[n+1].split();assert a[:2]==b[:2] and a[2]=="filter=nearest" and b[2]=="filter=linear" and a[3]==b[3] and a[4]=="0,1,0,1" and b[4]=="0.5,0.5,0,1" and a[5:]==b[5:]
print("PASS bound M4 public sampler transcript; P1.3 open")
