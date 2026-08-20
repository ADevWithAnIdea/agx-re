#!/usr/bin/env python3
import argparse,datetime,hashlib,json,os,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def call(argv,timeout):
 t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:c=subprocess.run([str(x) for x in argv],capture_output=True,text=True,timeout=timeout);return {"argv":[str(x) for x in argv],"cwd":str(HERE),"environment_overrides":{},"timeout_seconds":timeout,"started_utc":t,"exit":c.returncode,"stdout":c.stdout,"stderr":c.stderr}
 except subprocess.TimeoutExpired as e:return {"argv":[str(x) for x in argv],"cwd":str(HERE),"environment_overrides":{},"timeout_seconds":timeout,"started_utc":t,"exit":None,"timed_out":True,"stdout":str(e.stdout or ""),"stderr":str(e.stderr or "")}
ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True);a=ap.parse_args();out=HERE/"raw"/a.run_id
if a.run_id not in ("m4-20260820-run01","m4-20260820-run02") or out.exists():raise SystemExit("fixed append-only run id")
out.mkdir();inputs=[HERE/"PRE_REGISTRATION.md",HERE/"run.py",HERE/"verify.py",HERE/"harness/probe.m"]
(out/"00_inputs.json").write_text(json.dumps({"schema":1,"revision":subprocess.run(["git","rev-parse","HEAD"],cwd=REPO,capture_output=True,text=True,check=True).stdout.strip(),"inputs":{str(p.relative_to(REPO)):sha(p) for p in inputs},"boundary":{"binary_archive_bo_inspection":"NONE","target":"M4 public Metal only"}},indent=2,sort_keys=True)+"\n")
probe=out/"probe-unretained";b=call(["xcrun","clang","-arch","arm64e","-fobjc-arc","-o",probe,HERE/"harness/probe.m","-framework","Metal","-framework","Foundation"],60);(out/"01_build.json").write_text(json.dumps(b,indent=2,sort_keys=True)+"\n")
if b["exit"]:raise SystemExit(1)
r=call([probe],45);(out/"02_run.json").write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
probe.unlink();raise SystemExit(0 if r["exit"]==0 else 1)
