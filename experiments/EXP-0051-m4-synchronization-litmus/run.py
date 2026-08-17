#!/usr/bin/env python3
"""Append-only builder/runner for the EXP-0051 M4 synchronization suite."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
RAW=HERE/"raw";H=HERE/"harness";K=HERE/"kernels"
PREREG_HASH="941eb45f744f6a08b19037cfd147810954fb7365466355f50e1ad652da0d2cec"

def digest(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def invoke(argv:list[object],log:Path,timeout:int)->int:
    cmd=[str(x) for x in argv];started=time.time();rec={"command":cmd,"timeout_seconds":timeout,"started_unix":started}
    try:
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        rec.update(exit=cp.returncode,elapsed_seconds=round(time.time()-started,6),stdout=cp.stdout,stderr=cp.stderr);rc=cp.returncode
    except subprocess.TimeoutExpired as exc:
        def txt(x):return x.decode(errors="replace") if isinstance(x,bytes) else (x or "")
        rec.update(exit=124,timeout=True,elapsed_seconds=round(time.time()-started,6),stdout=txt(exc.stdout),stderr=txt(exc.stderr));rc=124
    log.write_text(json.dumps(rec,indent=2,sort_keys=True)+"\n");return rc

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True);a=ap.parse_args()
    if not a.run_id.replace("-","").replace("_","").isalnum():raise SystemExit("bad run-id")
    if digest(HERE/"PRE_REGISTRATION.md")!=PREREG_HASH:raise SystemExit("frozen preregistration changed")
    out=RAW/a.run_id;out.mkdir(parents=True,exist_ok=False)
    work=HERE/"work"/a.run_id;work.mkdir(parents=True,exist_ok=False)
    inputs=[HERE/"PRE_REGISTRATION.md",HERE/"run.py",H/"litmus.m",K/"litmus.metal",*sorted((K/"compile_probes").glob("*.metal"))]
    (out/"00_preflight.json").write_text(json.dumps({
      "preregistration_sha256":PREREG_HASH,"verified_before_build_and_hardware":True,
      "target":"local Apple M4 only","started_unix":time.time(),"platform":platform.platform(),
      "python":sys.version,"clean_room":{"apple_binary_introspection":False,"apple_auxiliary_code_inspection":False,
        "generic_bo_scan":False,"command_bo_capture":False,"pointer_following":False,
        "observations":"authored MSL compile result and own shared-buffer live outputs only"},
      "exact_input_hashes":{str(p.relative_to(HERE)):digest(p) for p in inputs}},indent=2,sort_keys=True)+"\n")
    invoke(["sw_vers"],out/"01_sw_vers.json",10);invoke(["uname","-a"],out/"02_uname.json",10);invoke(["clang","--version"],out/"03_clang.json",10)
    exe=work/"litmus"
    rc=invoke(["clang","-fobjc-arc","-o",exe,H/"litmus.m","-framework","Metal","-framework","Foundation"],out/"04_build.json",30)
    if rc:
        (out/"failures.json").write_text(json.dumps([{"phase":"build","exit":rc}],indent=2)+"\n");return 1
    (out/"05_runner_hash.json").write_text(json.dumps({"path":str(exe.relative_to(HERE)),"bytes":exe.stat().st_size,"sha256":digest(exe)},indent=2,sort_keys=True)+"\n")
    rc=invoke([exe,"--source",K/"litmus.metal","--probe-dir",K/"compile_probes",
               "--api-trials","128","--message-tg-iters","256","--message-cross-iters","8192"],out/"06_suite.json",180)
    failures=[] if rc==0 else [{"phase":"suite","exit":rc}]
    (out/"failures.json").write_text(json.dumps(failures,indent=2,sort_keys=True)+"\n")
    sums=[]
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name!="SHA256SUMS":sums.append(f"{digest(p)}  {p.relative_to(out)}")
    (out/"SHA256SUMS").write_text("\n".join(sums)+"\n")
    return 1 if failures else 0

if __name__=="__main__":raise SystemExit(main())
