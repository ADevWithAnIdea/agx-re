#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 import argparse;ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True);a=ap.parse_args();out=HERE/"raw"/a.run_id
 if out.exists():raise SystemExit("append-only")
 out.mkdir(parents=True);inputs=[HERE/"PRE_REGISTRATION.md",HERE/"run.py",HERE/"harness/probe.m"]
 (out/"00_inputs.json").write_text(json.dumps({"revision":subprocess.run(["git","rev-parse","HEAD"],cwd=REPO,capture_output=True,text=True,check=True).stdout.strip(),"inputs":{str(p.relative_to(REPO)):sha(p) for p in inputs}},indent=2,sort_keys=True)+"\n")
 probe=HERE/"work"/(a.run_id+"-probe");build=subprocess.run(["xcrun","clang","-arch","arm64e","-fobjc-arc","-o",probe,HERE/"harness/probe.m","-framework","Metal","-framework","Foundation"],capture_output=True,text=True,timeout=60);(out/"01_build.json").write_text(json.dumps({"exit":build.returncode,"stdout":build.stdout,"stderr":build.stderr},indent=2)+"\n");
 if build.returncode:return 1
 run=subprocess.run([probe],capture_output=True,text=True,timeout=45);(out/"02_run.json").write_text(json.dumps({"exit":run.returncode,"stdout":run.stdout,"stderr":run.stderr},indent=2)+"\n");return run.returncode
if __name__=="__main__":raise SystemExit(main())
