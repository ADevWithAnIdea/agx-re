#!/usr/bin/env python3
"""Append-only EXP-0049 refinement: approach first rollover from below."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from run import HERE, RAW, WORK, ALLOWED, digest, invoke

MAIN_HASH = "217063a4dad9831ece3d4fe974876d9d50b4216451c3cd281ae284382f3bc808"
REFINE_HASH = "e8e41a3989f1b18c015cc5a55dbf60ca64376d89a9510f4922f03355e9b8a4f1"
VARIANTS = {
    "cdm-indirect": ("cdm", 2048),
    "vdm-stable": ("vdm", 4096),
    "vdm-pass1": ("vdm", 4096),
}

def main() -> int:
    ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True);a=ap.parse_args()
    if not a.run_id.replace("-","").replace("_","").isalnum():raise SystemExit("bad run-id")
    if digest(HERE/"PRE_REGISTRATION.md") != MAIN_HASH:raise SystemExit("main prereg changed")
    if digest(HERE/"REFINEMENT_PRE_REGISTRATION.md") != REFINE_HASH:raise SystemExit("refinement prereg changed")
    out=RAW/a.run_id;work=WORK/a.run_id;out.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    inputs=[HERE/"PRE_REGISTRATION.md",HERE/"REFINEMENT_PRE_REGISTRATION.md",HERE/"refine.py",
            HERE/"run.py",HERE/"harness/probe.m",HERE/"harness/allowtrace.c",HERE/"analysis/analyze_trial.py"]
    (out/"00_inputs.json").write_text(json.dumps({"verified_before_build_and_hardware":True,
        "main_pre_registration_sha256":MAIN_HASH,"refinement_pre_registration_sha256":REFINE_HASH,
        "authored_inputs":{str(p.relative_to(HERE)):digest(p) for p in inputs}},indent=2,sort_keys=True)+"\n")
    (out/"01_scope.json").write_text(json.dumps({"run_id":a.run_id,"started_unix":time.time(),
        "scope":"local M4 structural refinement only","pointer_following":"NONE",
        "command_mutation":"NONE","unknown_bo_contents":"NONE"},indent=2,sort_keys=True)+"\n")
    tracer=work/"allowtrace.dylib";probe=work/"probe";failures=[]
    rc1=invoke(["xcrun","clang","-arch","arm64e","-dynamiclib","-o",tracer,HERE/"harness/allowtrace.c",
                "-framework","IOKit","-framework","CoreFoundation"],out/"02_build_allowtrace.json",60)
    rc2=invoke(["xcrun","clang","-arch","arm64e","-fobjc-arc","-o",probe,HERE/"harness/probe.m",
                "-framework","Metal","-framework","Foundation"],out/"03_build_probe.json",60)
    if rc1 or rc2:failures.append({"phase":"build","allowtrace_exit":rc1,"probe_exit":rc2})
    sequence=0

    def trial(variant:str,count:int,phase:str)->dict[str,object]:
        nonlocal sequence;sequence+=1;engine=VARIANTS[variant][0]
        name=f"{sequence:03d}_{variant}_{phase}_n{count:04d}";d=out/"trials"/name;state=d/"state";state.mkdir(parents=True)
        env=os.environ.copy();env.update({"DYLD_INSERT_LIBRARIES":str(tracer),"ALLOWTRACE_LOG":str(d/"trace.log"),"ALLOWTRACE_DUMP_DIR":str(state)})
        rc=invoke([probe,"--variant",variant,"--count",count,"--dump"],d/"run.json",45,env)
        names={p.name for p in state.iterdir() if p.is_file()}
        source="va_100000b8000.bin" if engine=="cdm" else "va_18000.bin"
        target="va_10000158000.bin" if engine=="cdm" else "va_88000.bin"
        base={"trial":name,"variant":variant,"engine":engine,"count":count,"probe_exit":rc,
              "source_present":source in names,"target_present":target in names,"captured":sorted(names)}
        if not names<=ALLOWED or rc or source not in names:
            base["classification"]="PROCESS_FAILURE";return base
        arc=invoke([sys.executable,HERE/"analysis/analyze_trial.py","--trial",d,"--engine",engine,"--output",d/"analysis.json"],d/"analysis-run.json",15)
        if arc:
            base["classification"]="TARGET_WITHOUT_EXACT_PAIR" if target in names else "ANALYSIS_FAILURE"
            return base
        analysis=json.loads((d/"analysis.json").read_text());base.update(classification="KNOWN_LINK" if analysis["known_link"] else "NO_LINK",analysis=analysis)
        return base

    summaries={}
    if not failures:
        for variant,(engine,upper) in VARIANTS.items():
            observations=[];count=1;previous=0;bracket=None;stopped=None
            while count<=upper:
                result=trial(variant,count,"approach");observations.append(result)
                if result["classification"]=="NO_LINK":previous=count
                elif result["classification"]=="KNOWN_LINK":bracket=(previous,count);break
                else:stopped=result["classification"];break
                if count==upper:break
                count=min(count*2,upper)
            if stopped or bracket is None:
                reason=stopped or "NO_KNOWN_LINK_BY_UPPER_BOUND"
                failures.append({"variant":variant,"phase":"approach","error":reason,"count":count})
                summaries[variant]={"status":"STOPPED","reason":reason,"observations":observations};continue
            low,high=bracket
            while high-low>1:
                middle=(low+high)//2;result=trial(variant,middle,"bisect");observations.append(result)
                if result["classification"]=="NO_LINK":low=middle
                elif result["classification"]=="KNOWN_LINK":high=middle
                else:stopped=result["classification"];break
            if stopped:
                failures.append({"variant":variant,"phase":"bisect","error":stopped,"count":middle})
                summaries[variant]={"status":"STOPPED","reason":stopped,"observations":observations};continue
            rlow=trial(variant,low,"repeat");rhigh=trial(variant,high,"repeat");observations.extend((rlow,rhigh))
            if rlow["classification"]!="NO_LINK" or rhigh["classification"]!="KNOWN_LINK":
                failures.append({"variant":variant,"phase":"repeat","error":"BOUNDARY_MISMATCH","lower":low,"threshold":high})
                summaries[variant]={"status":"STOPPED","reason":"BOUNDARY_MISMATCH","observations":observations};continue
            summaries[variant]={"status":"PASS","engine":engine,"lower_no_link":low,"first_known_link":high,
                                "link_offsets":[rhigh["analysis"]["link_offsets"]],"observations":observations}
    (out/"summary.json").write_text(json.dumps({"schema":1,"run_id":a.run_id,
        "scope":"local M4 structural refinement; no mutation; no A18 claim","variants":summaries},indent=2,sort_keys=True)+"\n")
    (out/"failures.json").write_text(json.dumps(failures,indent=2,sort_keys=True)+"\n")
    sums=[]
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name!="SHA256SUMS":sums.append(f"{digest(p)}  {p.relative_to(out)}")
    (out/"SHA256SUMS").write_text("\n".join(sums)+"\n")
    print(json.dumps({"run_id":a.run_id,"variants":summaries,"failures":failures},indent=2,sort_keys=True))
    return 1 if failures else 0

if __name__=="__main__":raise SystemExit(main())
