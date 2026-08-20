#!/usr/bin/env python3
"""Append-only EXP-0056 M4 transition capture; payloads open only post-preflight."""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, platform, re, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
RAW=HERE/"raw"; WORK=HERE/"work"
PRE_HASH="fd0df7965ded35fe89bbe2390b785d0950c8aa77f2a8075dfc8e013fca728080"
ALLOWED={"va_100000b8000":{"va":0x100000b8000,"role":"cdm-segment-0"},
         "va_10000158000":{"va":0x10000158000,"role":"cdm-segment-1"},
         "va_18000":{"va":0x18000,"role":"vdm-segment-0"},
         "va_88000":{"va":0x88000,"role":"vdm-segment-1"}}
VARIANTS=("compute-only","cpu-render","compute-render"); SCHEDULES=("plain","pad64k")
HEADER="# EXP-0056 fixed_allowlist=4 unknown_bo_dump=0 pointer_following=0 shader_dump=0 command_mutation=0"
RESOURCE=re.compile(r"RESOURCE_MAP class=(\S+) va=(0x[0-9a-f]+) size=(0x[0-9a-f]+) handle=(\d+) cpu_present=(\d+) outcpu_present=(\d+) allowlisted=(\d+)")
DUMP=re.compile(r"ALLOWLIST_DUMP va=(0x[0-9a-f]+) alloc=(0x[0-9a-f]+) cap=(0x[0-9a-f]+) got=(0x[0-9a-f]+) role=(\S+) kr=0x([0-9a-f]+)")
SERVICE=re.compile(r"SERVICE_OPEN class=(\S+) type=(\d+)")
CALL=re.compile(r"CALL class=(\S+) sel=(\d+) ret=(0x[0-9a-f]+) in_struct=(0x[0-9a-f]+) out_struct=(0x[0-9a-f]+)")
META={"gpu_va","allocation_size","read_size","role","fixed_allowlist","pointer_following","command_mutation"}

def sha(p:Path)->str:
 h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()
def jwrite(p:Path,v:object)->None:p.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n")
def invoke(argv:list[object],out:Path,timeout:int,env:dict[str,str]|None=None)->int:
 rec={"argv":[str(x) for x in argv],"timeout_seconds":timeout,"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  cp=subprocess.run(rec["argv"],capture_output=True,text=True,timeout=timeout,env=env);rec.update(exit=cp.returncode,stdout=cp.stdout,stderr=cp.stderr)
 except subprocess.TimeoutExpired as x:
  cv=lambda y:y.decode(errors="replace") if isinstance(y,bytes) else str(y or "")
  rec.update(exit=None,timed_out=True,stdout=cv(x.stdout),stderr=cv(x.stderr))
 jwrite(out,rec);return rec.get("exit",124) if isinstance(rec.get("exit",124),int) else 124
def meta(p:Path)->dict[str,str]:
 lines=p.read_text().splitlines()
 if len(lines)!=len(META) or any(x.count("=")!=1 for x in lines):raise AssertionError(f"metadata grammar {p}")
 d=dict(x.split("=",1) for x in lines)
 if set(d)!=META or len(d)!=len(lines):raise AssertionError(f"metadata keys {p}")
 return d
def preflight(trial:Path, required:set[str])->dict[str,dict[str,object]]:
 """All paths, metadata and trace validated before *any* bin opens or hashes."""
 if {p.name for p in trial.iterdir()}!={"run.json","trace.log","state"}:raise AssertionError("trial entries")
 state=trial/"state"
 if state.is_symlink() or not state.is_dir():raise AssertionError("state type")
 files=list(state.iterdir())
 if any(not p.is_file() or p.is_symlink() for p in files):raise AssertionError("state regular files")
 names={p.name for p in files}
 if any(not re.fullmatch(r"va_(100000b8000|10000158000|18000|88000)\.(bin|meta)",n) for n in names):raise AssertionError("state filename scope")
 present={n[:-4] for n in names if n.endswith(".bin")}
 if present!={n[:-5] for n in names if n.endswith(".meta")}:raise AssertionError("exact bin/meta pairs")
 if not required<=present:raise AssertionError(f"required mappings absent: {sorted(required-present)}")
 lines=(trial/"trace.log").read_text().splitlines()
 if lines.count(HEADER)!=1:raise AssertionError("header")
 maps=[]; dumps=[]; services=calls=0
 for line in lines:
  if line==HEADER:continue
  if line.startswith("SERVICE_OPEN "):
   if not SERVICE.fullmatch(line):raise AssertionError("service grammar")
   services+=1;continue
  if line.startswith("CALL "):
   if not CALL.fullmatch(line):raise AssertionError("call grammar")
   calls+=1;continue
  if line.startswith("RESOURCE_MAP "):
   m=RESOURCE.fullmatch(line)
   if not m:raise AssertionError("resource grammar")
   if m[7]=="1":maps.append(m)
   continue
  if line.startswith("ALLOWLIST_DUMP "):
   m=DUMP.fullmatch(line)
   if not m:raise AssertionError("dump grammar")
   dumps.append(m);continue
  raise AssertionError(f"unknown trace record {line!r}")
 if services!=2 or calls<1:raise AssertionError("service/call count")
 if len(maps)!=len(present) or len(dumps)!=len(present):raise AssertionError("trace pair count")
 ret={}
 for stem in sorted(present):
  spec=ALLOWED[stem]; d=meta(state/(stem+".meta")); b=state/(stem+".bin")
  if int(d["gpu_va"],0)!=spec["va"] or d["role"]!=spec["role"]:raise AssertionError("VA role")
  if (d["fixed_allowlist"],d["pointer_following"],d["command_mutation"])!=("1","0","0"):raise AssertionError("boundary flags")
  if b.stat().st_size!=int(d["read_size"],0) or int(d["read_size"],0)>0x10000 or int(d["allocation_size"],0)<int(d["read_size"],0):raise AssertionError("size bounds")
  ms=[m for m in maps if int(m[2],0)==spec["va"]];ds=[m for m in dumps if int(m[1],0)==spec["va"]]
  if len(ms)!=1 or len(ds)!=1 or int(ms[0][3],0)!=int(d["allocation_size"],0) or int(ds[0][2],0)!=int(d["allocation_size"],0) or int(ds[0][4],0)!=int(d["read_size"],0) or ds[0][5]!=spec["role"] or ds[0][6]!="0":raise AssertionError("trace-meta linkage")
  ret[stem]={"path":b,"size":b.stat().st_size,"metadata":d}
 return ret
def analyze(out:Path)->None:
 trials=out/"trials"; matrix={}
 for schedule in SCHEDULES:
  for variant in VARIANTS:
   name=f"{schedule}_{variant}"; required={"va_100000b8000"} if variant=="compute-only" else ({"va_18000"} if variant=="cpu-render" else {"va_100000b8000","va_18000"})
   checked=preflight(trials/name,required) # no payload opened before this returns
   matrix[name]={s:{"size":v["size"],"sha256":sha(v["path"])} for s,v in checked.items()}
 diffs={}
 for schedule in SCHEDULES:
  a=preflight(trials/f"{schedule}_compute-only",{"va_100000b8000"})
  b=preflight(trials/f"{schedule}_compute-render",{"va_100000b8000","va_18000"})
  c=preflight(trials/f"{schedule}_cpu-render",{"va_18000"})
  for label,left,right in (("cdm",a["va_100000b8000"],b["va_100000b8000"]),("vdm",c["va_18000"],b["va_18000"])):
   x=left["path"].read_bytes();y=right["path"].read_bytes()
   if len(x)!=len(y):raise AssertionError("matched VA size changed")
   changes=[i for i,(u,v) in enumerate(zip(x,y)) if u!=v]
   diffs[f"{schedule}_{label}"]={"left":left["path"].name,"right":right["path"].name,"size":len(x),"changed_byte_count":len(changes),"changed_offsets":changes,"pairs":[[x[i],y[i]] for i in changes]}
 jwrite(out/"analysis.json",{"scope":"M4 only; structural comparison; no pointer following or mutation","matrix":matrix,"dependency_vs_control_diffs":diffs})
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True);a=ap.parse_args()
 if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*",a.run_id):raise SystemExit("bad run id")
 if sha(HERE/"PRE_REGISTRATION.md")!=PRE_HASH:raise SystemExit("pre-registration hash mismatch")
 out=RAW/a.run_id;work=WORK/a.run_id
 if out.exists() or work.exists():raise SystemExit("append-only id exists")
 out.mkdir(parents=True);work.mkdir(parents=True)
 inputs=[HERE/"PRE_REGISTRATION.md",HERE/"run.py",HERE/"harness/probe.m",HERE/"harness/allowtrace.c"]
 jwrite(out/"00_inputs.json",{"pre_registration_sha256":PRE_HASH,"authored_inputs":{str(p.relative_to(HERE)):sha(p) for p in inputs},"revision":subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()})
 jwrite(out/"01_environment.json",{"platform":platform.platform(),"machine":platform.machine(),"target":"local Apple M4/G16G only","apple_binary_introspection":"NONE","unknown_bo_contents":"NONE","pointer_following":"NONE","command_mutation":"NONE"})
 tracer=work/"allowtrace.dylib";probe=work/"probe"
 if invoke(["xcrun","clang","-arch","arm64e","-dynamiclib","-o",tracer,HERE/"harness/allowtrace.c","-framework","IOKit","-framework","CoreFoundation"],out/"02_build_allowtrace.json",60) or invoke(["xcrun","clang","-arch","arm64e","-fobjc-arc","-o",probe,HERE/"harness/probe.m","-framework","Metal","-framework","Foundation"],out/"03_build_probe.json",60):return 1
 for schedule in SCHEDULES:
  for variant in VARIANTS:
   trial=out/"trials"/f"{schedule}_{variant}";state=trial/"state";state.mkdir(parents=True)
   env=os.environ.copy();env.update({"DYLD_INSERT_LIBRARIES":str(tracer),"ALLOWTRACE_LOG":str(trial/"trace.log"),"ALLOWTRACE_DUMP_DIR":str(state)})
   argv=[probe,"--variant",variant,"--dump"]+(["--pad64k"] if schedule=="pad64k" else [])
   if invoke(argv,trial/"run.json",45,env):return 1
 try:analyze(out)
 except Exception as e:jwrite(out/"analysis_failure.json",{"error":repr(e)});return 1
 sums=[]
 for p in sorted(out.rglob("*")):
  if p.is_file() and p.name!="SHA256SUMS":sums.append(f"{sha(p)}  {p.relative_to(out)}")
 (out/"SHA256SUMS").write_text("\n".join(sums)+"\n");return 0
if __name__=="__main__":raise SystemExit(main())
