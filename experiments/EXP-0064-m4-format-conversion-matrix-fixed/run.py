#!/usr/bin/env python3
import argparse, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
CASES=("rgba8unorm_edges","bgra8unorm_edges","rgba8srgb_threshold","r16unorm_midpoint","rgba16float_edges","r32uint_exact")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rec(cmd,to):
 t=time.monotonic()
 try:
  p=subprocess.run([str(x) for x in cmd],text=True,capture_output=True,timeout=to);return {"command":[str(x) for x in cmd],"timeout":False,"exit":p.returncode,"seconds":round(time.monotonic()-t,3),"stdout":p.stdout,"stderr":p.stderr}
 except subprocess.TimeoutExpired as e:return {"command":[str(x) for x in cmd],"timeout":True,"seconds":to,"stdout":e.stdout or "","stderr":e.stderr or ""}
def put(p,o):p.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n")
def main():
 a=argparse.ArgumentParser();a.add_argument("--run-id",required=True);x=a.parse_args();rid=x.run_id
 if not rid.replace("-","").replace("_","").isalnum():raise SystemExit("bad run id")
 raw=HERE/"raw"/rid;work=HERE/"work"/rid;raw.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
 try:
  src=raw/"format_matrix.metal";shutil.copyfile(HERE/"kernels/format_matrix.metal",src)
  put(raw/"00_environment.json",{"git_revision":subprocess.run(["git","rev-parse","HEAD"],cwd=HERE,text=True,capture_output=True,check=True).stdout.strip(),"source_sha256":sha(src),"sw_vers":rec(["sw_vers"],5),"xcode":rec(["xcrun","--version"],5)})
  exe=work/"probe";b=rec(["clang","-fobjc-arc","-framework","Metal","-framework","Foundation","-o",exe,HERE/"harness/probe.m"],30);put(raw/"01_build.json",b)
  if b["timeout"] or b.get("exit")!=0:return
  for n in CASES:
   z=rec([exe,"--source",src,"--case",n],20);put(raw/f"case_{n}.json",z)
   if z["timeout"]:put(raw/"STOP.json",{"case":n,"reason":"timeout","automatic_recovery":False});break
  put(raw/"run_manifest.json",{"run_id":rid,"cases":CASES,"fresh_process_per_case":True,"source_sha256":sha(src),"runner_sha256":sha(Path(__file__))})
 finally:shutil.rmtree(work,ignore_errors=True)
if __name__=="__main__":main()
