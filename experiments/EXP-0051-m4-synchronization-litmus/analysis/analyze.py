#!/usr/bin/env python3
"""Parse only authored EXP-0051 stdout and provenance records."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parents[1]
DEFAULT=[HERE/"raw"/"m4_20260817_run01",HERE/"raw"/"m4_20260817_run02"]
PREREG="941eb45f744f6a08b19037cfd147810954fb7365466355f50e1ad652da0d2cec"
BARRIER_NAMES={"tg_mem_threadgroup","tg_mem_none","simd_mem_threadgroup",
  "tg_device_mem_device","tg_device_mem_wrong_class","tg_device_mem_both"}
MESSAGE_NAMES={"msg_tg_relaxed","msg_tg_fence_device","msg_tg_fence_tgscope",
  "msg_cross_relaxed","msg_cross_fence_device"}
API_NAMES={"same_encoder_no_explicit_barrier","same_encoder_buffer_barrier",
  "adjacent_compute_encoders","same_queue_two_cb_no_cpu_wait",
  "same_queue_two_cb_cpu_wait","two_queue_unsync_consumer_first",
  "two_queue_cpu_wait","two_queue_shared_event","cpu_write_to_gpu_after_commit_wait",
  "gpu_write_to_cpu_after_completion_wait"}
COMPILE_NAMES={"atomic_load_acquire_store_release.metal","atomic_rmw_acq_rel.metal",
  "atomic_rmw_relaxed.metal","fence_release_device.metal","fence_seq_cst_device.metal"}

def fields(line:str)->dict[str,str]:
    out={}
    for token in line.split()[1:]:
        if "=" not in token:raise AssertionError(f"malformed record token {token!r}")
        k,v=token.split("=",1)
        if k in out:raise AssertionError(f"duplicate record key {k}")
        out[k]=v
    return out

def num(x:str)->int:return int(x,0)
def insert_unique(records:dict[str,dict[str,str]],name:str,value:dict[str,str],kind:str)->None:
    if name in records:raise AssertionError(f"duplicate {kind} record {name}")
    records[name]=value

def parse(run:Path)->dict[str,object]:
    if json.loads((run/"failures.json").read_text()):raise AssertionError(f"formal failure {run}")
    pre=json.loads((run/"00_preflight.json").read_text())
    if pre["preregistration_sha256"]!=PREREG or not pre["verified_before_build_and_hardware"]:raise AssertionError("prereg verification")
    suite=json.loads((run/"06_suite.json").read_text())
    if suite.get("exit")!=0 or suite.get("timeout"):raise AssertionError(f"suite exit {run}")
    parsed={"barrier":{},"message":{},"api":{},"compile":{},"pipeline":[],"done":0,
            "input_hashes":pre["exact_input_hashes"],"runner":json.loads((run/"05_runner_hash.json").read_text())}
    lines=suite["stdout"].splitlines()
    if lines.count("DEVICE Apple M4")!=1:raise AssertionError("device identity")
    if lines.count("CONFIG api_trials=128 msg_tg_iters=256 msg_cross_iters=8192")!=1:raise AssertionError("suite config")
    error_name=None;error_blocks=set()
    for line in lines:
        if error_name is not None:
            if line==f"COMPILE_ERROR_END name={error_name}":
                error_blocks.add(error_name);error_name=None
            continue
        if line in {"DEVICE Apple M4","CONFIG api_trials=128 msg_tg_iters=256 msg_cross_iters=8192"}:
            continue
        if line.startswith("COMPILE_ERROR_BEGIN "):
            f=fields(line)
            if set(f)!={"name"} or f["name"] in error_blocks:raise AssertionError("compile error begin")
            error_name=f["name"];continue
        if line.startswith("BARRIER "):
            f=fields(line);name=f.pop("case");insert_unique(parsed["barrier"],name,f,"barrier")
        elif line.startswith("MESSAGE "):
            f=fields(line);name=f.pop("case");insert_unique(parsed["message"],name,f,"message")
        elif line.startswith("API "):
            f=fields(line);name=f.pop("case");insert_unique(parsed["api"],name,f,"API")
        elif line.startswith("COMPILE_PROBE "):
            f=fields(line);name=f.pop("name");insert_unique(parsed["compile"],name,f,"compile")
        elif line.startswith("PIPELINE "):
            parsed["pipeline"].append(fields(line))
        elif line=="SUITE_DONE command_or_pipeline_errors=0":parsed["done"]+=1
        else:raise AssertionError(f"unrecognized authored stdout line {line!r}")
    if error_name is not None:raise AssertionError("unterminated compile error")
    if parsed["done"]!=1:raise AssertionError("suite completion count")
    if set(parsed["barrier"])!=BARRIER_NAMES or set(parsed["message"])!=MESSAGE_NAMES or set(parsed["api"])!=API_NAMES or set(parsed["compile"])!=COMPILE_NAMES:raise AssertionError("matrix name set")
    pipeline_names=[f["name"] for f in parsed["pipeline"]]
    expected_pipeline=BARRIER_NAMES|MESSAGE_NAMES|{"ordered_producer","ordered_consumer"}
    if len(pipeline_names)!=15 or set(pipeline_names)!=(expected_pipeline|{"probe"}) or pipeline_names.count("probe")!=2:raise AssertionError("pipeline set")
    if any(set(f)!={"name","thread_width","max_threads"} or f["thread_width"]!="32" or
           f["max_threads"]!="1024" for f in parsed["pipeline"]):raise AssertionError("pipeline grammar")
    rejected=COMPILE_NAMES-{"atomic_rmw_relaxed.metal","fence_seq_cst_device.metal"}
    if error_blocks!=rejected:raise AssertionError("compile diagnostic block set")
    return parsed

def semantic(p:dict[str,object],include_unsync:bool)->dict[str,object]:
    apis=dict(p["api"])
    if not include_unsync:apis.pop("two_queue_unsync_consumer_first")
    return {"barrier":p["barrier"],"message":p["message"],"api":apis,"compile":p["compile"]}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--run-a",type=Path,default=DEFAULT[0]);ap.add_argument("--run-b",type=Path,default=DEFAULT[1]);ap.add_argument("--json",type=Path);ap.add_argument("--report",type=Path);a=ap.parse_args()
    runs=[a.run_a.resolve(),a.run_b.resolve()];p=[parse(x) for x in runs]
    if p[0]["input_hashes"]!=p[1]["input_hashes"]:raise AssertionError("input hashes differ")
    if (p[0]["runner"]["sha256"],p[0]["runner"]["bytes"])!=(p[1]["runner"]["sha256"],p[1]["runner"]["bytes"]):raise AssertionError("runner differs")
    if semantic(p[0],False)!=semantic(p[1],False):raise AssertionError("deterministic semantic results differ")

    for q in p:
        for name,f in q["barrier"].items():
            if (set(f)!={"mismatch","checked","first_key","observed","command_errors"} or
                num(f["mismatch"])!=0 or num(f["checked"])!=65536 or
                num(f["first_key"])!=0xffffffff or num(f["observed"])!=0 or
                num(f["command_errors"])):raise AssertionError(f"barrier {name}")
        for name,f in q["message"].items():
            if set(f)!={"topology","iterations","expected","mismatch_words","producer_timeouts","consumer_timeouts","completed","command_errors"}:raise AssertionError(f"message fields {name}")
            same=name.startswith("msg_tg_");expected=16384 if same else 8192;iterations=256 if same else 8192
            if f["topology"]!=("same_threadgroup" if same else "cross_threadgroup") or num(f["iterations"])!=iterations or num(f["expected"])!=expected or num(f["completed"])!=expected or any(num(f[k]) for k in ("mismatch_words","producer_timeouts","consumer_timeouts","command_errors")):raise AssertionError(f"message {name}")
        for name,f in q["api"].items():
            if set(f)!={"trials","words","good","bad","mismatch_words","initial_source_words","first_epoch","first_index","first_got","first_want","command_errors"} or num(f["trials"])!=128 or num(f["words"])!=524288:raise AssertionError(f"API shape {name}")
            if name=="two_queue_unsync_consumer_first":
                if (num(f["good"])+num(f["bad"])!=128 or num(f["mismatch_words"])==0 or
                    num(f["mismatch_words"])!=num(f["initial_source_words"]) or
                    num(f["mismatch_words"])!=num(f["bad"])*4096 or num(f["command_errors"])):raise AssertionError("unsync did not expose missing order")
            elif (num(f["good"])!=128 or num(f["bad"]) or num(f["mismatch_words"]) or
                  num(f["initial_source_words"]) or num(f["command_errors"])):raise AssertionError(f"API {name}")
    exposure={name:(num(f["accepted"]),num(f["pipeline"]),num(f["executed"])) for name,f in p[0]["compile"].items()}
    expected={
      "atomic_load_acquire_store_release.metal":(0,0,0),"atomic_rmw_acq_rel.metal":(0,0,0),
      "atomic_rmw_relaxed.metal":(1,1,1),"fence_release_device.metal":(0,0,0),
      "fence_seq_cst_device.metal":(1,1,1)}
    if exposure!=expected:raise AssertionError(f"compile exposure {exposure}")
    for q in p:
        relaxed=q["compile"]["atomic_rmw_relaxed.metal"]
        fence=q["compile"]["fence_seq_cst_device.metal"]
        if (relaxed!={"accepted":"1","pipeline":"1","executed":"1","flag":"0x00000002","out0":"0x00000000","out1":"0x00000001"} or
            fence!={"accepted":"1","pipeline":"1","executed":"1","flag":"0x00000002","out0":"0xa5000000","out1":"0xa5000001"}):raise AssertionError("accepted compile-probe outputs")
        for name in COMPILE_NAMES-{"atomic_rmw_relaxed.metal","fence_seq_cst_device.metal"}:
            if q["compile"][name]!={"accepted":"0","pipeline":"0","executed":"0"}:raise AssertionError(f"rejected compile-probe shape {name}")

    uns=[]
    for run,q in zip(runs,p):
        f=q["api"]["two_queue_unsync_consumer_first"]
        uns.append({"run":run.name,**{k:num(v) for k,v in f.items() if k not in ("case",)}})
    summary={"scope":"local Apple M4/G16G Metal path only; no native-instruction, Vulkan/GL, Linux UAPI, or A18 claim",
      "runs":[x.name for x in runs],"preregistration_sha256":PREREG,"exact_input_hashes":p[0]["input_hashes"],
      "runner":p[0]["runner"],"barriers":p[0]["barrier"],"messages":p[0]["message"],
      "ordered_api_cases":{k:v for k,v in p[0]["api"].items() if k!="two_queue_unsync_consumer_first"},
      "unsynchronized_two_queue":uns,"compile_exposure":p[0]["compile"]}
    if a.json:a.json.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    u0,u1=uns
    lines=[
      "EXP-0051 strict authored-output analysis","OBSERVATIONS",
      f"- Both runs used identical input hashes and an identical {p[0]['runner']['bytes']:,}-byte runner binary (SHA-256 {p[0]['runner']['sha256']}).",
      "- All six barrier/scope cases checked 65,536 asymmetric peer values per run with zero mismatches, including both deliberately under-scoped controls.",
      "- Same-threadgroup publication completed 16,384 messages per case/run; cross-threadgroup publication completed 8,192 per case/run. Relaxed and fenced cases all had zero payload mismatch or timeout.",
      "- Nine producer-before-consumer API/CPU cases each validated 128 epochs and 524,288 words per run with no mismatch or command error.",
      f"- Unsynchronized consumer-first two-queue run01: good={u0['good']} bad={u0['bad']} stale_words={u0['initial_source_words']}; run02: good={u1['good']} bad={u1['bad']} stale_words={u1['initial_source_words']}.",
      "- Atomic relaxed RMW and device-scope seq-cst fence compiled, created pipelines, and executed. Acquire-load/release-store, acquire-release RMW, and release fence identifiers were rejected in both runs.",
      "",
      "INTERPRETATION",
      "- Correct barrier/API cases satisfy their bounded live M4 litmus. Passing wrong-scope, mem_none, relaxed, or no-explicit-barrier controls does not establish a portable guarantee; coherence and scheduling can hide a race.",
      "- The unsynchronized two-queue variability (0 then 1 good epoch) demonstrates absent deterministic inter-queue order. CPU wait and shared-event cases establish the tested runtime ordering boundaries.",
      "- Compile rejection establishes only this Metal language/runtime exposure. It does not imply that Apple9 lacks native acquire/release encodings.",
      "- Results combine compiler, Metal runtime, command processing, scheduling, and cache policy. No isolated native instruction or Linux UAPI barrier semantics were tested.",
    ]
    report="\n".join(lines)+"\n";print(report,end="")
    if a.report:a.report.write_text(report)
    return 0

if __name__=="__main__":raise SystemExit(main())
