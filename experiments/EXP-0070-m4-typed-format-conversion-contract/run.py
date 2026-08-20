#!/usr/bin/env python3
"""Opt-in future capture runner; it never runs unless --execute is explicit."""
import argparse, datetime, hashlib, json, platform, shutil, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent; REPO=HERE.parents[1]
CASES=("rgba8unorm_edges","bgra8unorm_edges","rgba8srgb_threshold","r16unorm_midpoint","rgba16float_finite","r32uint_exact")
AUTH=("PRE_REGISTRATION.md","README.md","RESULTS.md","CAPTURE_CONTRACT.json","kernels/format_matrix.metal","harness/probe.m","run.py","analysis.py","make_manifest.py","verify.py")
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,o): p.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n")
def rec(argv,timeout):
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p=subprocess.run([str(x) for x in argv],cwd=HERE,text=True,capture_output=True,timeout=timeout)
        return {"argv":[str(x) for x in argv],"cwd":str(HERE),"timeout_seconds":timeout,"started_utc":started,"timed_out":False,"exit":p.returncode,"stdout":p.stdout,"stderr":p.stderr,"exception":None}
    except subprocess.TimeoutExpired as e:
        return {"argv":[str(x) for x in argv],"cwd":str(HERE),"timeout_seconds":timeout,"started_utc":started,"timed_out":True,"exit":None,"stdout":e.stdout or "","stderr":e.stderr or "","exception":"TimeoutExpired"}
    except OSError as e:
        return {"argv":[str(x) for x in argv],"cwd":str(HERE),"timeout_seconds":timeout,"started_utc":started,"timed_out":False,"exit":None,"stdout":"","stderr":"","exception":type(e).__name__}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--run-id");ap.add_argument("--execute",action="store_true");a=ap.parse_args()
    if not a.execute: raise SystemExit("refusing device operation: pass --execute only after approved pre-GPU review")
    if not a.run_id or a.run_id not in ("m4-TODO-run01","m4-TODO-run02"): raise SystemExit("run-id must be a contracted append-only ID")
    if subprocess.run(["python3","-B","verify.py","--preflight"],cwd=HERE).returncode: raise SystemExit("preflight failed")
    raw=HERE/"raw"/a.run_id; work=HERE/"work"/a.run_id
    if raw.exists() or work.exists(): raise SystemExit("append-only path already exists")
    raw.mkdir(parents=True);work.mkdir(parents=True)
    try:
        env={"schema":1,"git_revision":subprocess.run(["git","rev-parse","HEAD"],cwd=REPO,text=True,capture_output=True,check=True).stdout.strip(),"authored_sha256":{x:sha(HERE/x) for x in AUTH},"sw_vers":rec(["sw_vers"],5),"xcrun_version":rec(["xcrun","--version"],5),"machine":platform.machine(),"boundary":"public Metal; owned in-bounds buffers; no binary/archive/BO inspection"};put(raw/"00_inputs.json",env)
        if any(z["timed_out"] or z["exit"] != 0 or z["exception"] is not None for z in (env["sw_vers"],env["xcrun_version"])): put(raw/"STOP.json",{"schema":1,"phase":"environment","automatic_retry":False});return
        build=rec(["xcrun","clang","-fobjc-arc","-o",work/"probe",HERE/"harness/probe.m","-framework","Metal","-framework","Foundation"],60);put(raw/"01_host_build.json",build)
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None: put(raw/"STOP.json",{"schema":1,"phase":"host_build","automatic_retry":False});return
        for case in CASES:
            z=rec([work/"probe","--source",HERE/"kernels/format_matrix.metal","--case",case],20);put(raw/f"case_{case}.json",z)
            if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None: put(raw/"STOP.json",{"schema":1,"phase":"case","case":case,"automatic_retry":False});return
        put(raw/"run_manifest.json",{"schema":1,"run_id":a.run_id,"cases":list(CASES),"fresh_process_per_case":True,"runner_sha256":sha(HERE/"run.py"),"harness_sha256":sha(HERE/"harness/probe.m"),"kernel_sha256":sha(HERE/"kernels/format_matrix.metal")})
    finally: shutil.rmtree(work,ignore_errors=True)
if __name__=="__main__": main()
