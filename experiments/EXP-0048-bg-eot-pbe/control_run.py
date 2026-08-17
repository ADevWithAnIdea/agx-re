#!/usr/bin/env python3
"""Run the frozen EXP-0048 blend negative control once."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from run import invoke, sha256, EXPECTED_PREREG

HERE=Path(__file__).resolve().parent
RAW=HERE/"raw"
H=HERE/"harness"
CONTROL_HASH="588ccdf3a234c790e12311d99bf142d7b476a9663506409bf0bda66117bd35d1"

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True);a=ap.parse_args()
    if not a.run_id.replace("-","").replace("_","").isalnum():raise SystemExit("bad run-id")
    if sha256(HERE/"PRE_REGISTRATION.md")!=EXPECTED_PREREG:raise SystemExit("main prereg changed")
    if sha256(HERE/"CONTROL_PRE_REGISTRATION.md")!=CONTROL_HASH:raise SystemExit("control prereg changed")
    out=RAW/a.run_id;out.mkdir(parents=True,exist_ok=False)
    work=HERE/"work"/a.run_id;work.mkdir(parents=True,exist_ok=False)
    (out/"00_preregistration.json").write_text(json.dumps({
        "main_sha256":EXPECTED_PREREG,"control_sha256":CONTROL_HASH,
        "verified_before_build_and_hardware":True,"started_unix":time.time()},indent=2,sort_keys=True)+"\n")
    tracer=work/"allowtrace.dylib";probe=work/"blend_control"
    failures=[]
    rc=invoke(["clang","-dynamiclib","-o",tracer,H/"allowtrace.c","-framework","IOKit","-framework","CoreFoundation"],out/"01_build_allowtrace.json",30)
    if rc:failures.append({"phase":"build_allowtrace","exit":rc})
    rc2=invoke(["clang","-fobjc-arc","-o",probe,H/"blend_control.m","-framework","Metal","-framework","Foundation"],out/"02_build_probe.json",30)
    if rc2:failures.append({"phase":"build_probe","exit":rc2})
    if not failures:
        state=out/"state_rgba8-load-store-draw-control";state.mkdir()
        env=os.environ.copy();env.update({"DYLD_INSERT_LIBRARIES":str(tracer),
            "ALLOWTRACE_LOG":str(out/"trace.log"),"ALLOWTRACE_DUMP_DIR":str(state)})
        rc3=invoke([probe,"--source-out",out/"source.metal","--dump"],out/"run.json",45,env)
        expected={"va_18000.bin","va_58000.bin","va_68000.bin","va_10000018200.bin"}
        present={p.name for p in state.glob("*.bin")}
        if rc3 or present!=expected:failures.append({"phase":"run","exit":rc3,"missing":sorted(expected-present),"extra":sorted(present-expected)})
    (out/"failures.json").write_text(json.dumps(failures,indent=2,sort_keys=True)+"\n")
    sums=[]
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name!="SHA256SUMS":sums.append(f"{sha256(p)}  {p.relative_to(out)}")
    (out/"SHA256SUMS").write_text("\n".join(sums)+"\n")
    return 1 if failures else 0

if __name__=="__main__":raise SystemExit(main())
