#!/usr/bin/env python3
"""Verify EXP-0049 frozen plans, raw allowlist, derivation, and manifest."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
PLANS={"PRE_REGISTRATION.md":"217063a4dad9831ece3d4fe974876d9d50b4216451c3cd281ae284382f3bc808",
       "REFINEMENT_PRE_REGISTRATION.md":"e8e41a3989f1b18c015cc5a55dbf60ca64376d89a9510f4922f03355e9b8a4f1"}
RUNS=["m4-20260817-run01","m4-20260817-run02","m4-20260817-refine01","m4-20260817-refine02"]
VA={"va_100000b8000":(0x100000B8000,0x10000),"va_10000158000":(0x10000158000,0x10000),
    "va_18000":(0x18000,0x10000),"va_88000":(0x88000,0x10000)}
ROLES={"va_100000b8000":"cdm-segment-0","va_10000158000":"cdm-segment-1",
       "va_18000":"vdm-segment-0","va_88000":"vdm-segment-1"}
ALLOWED={f"{stem}.{suffix}" for stem in VA for suffix in ("bin","meta")}
SHA_LINE=re.compile(r"^([0-9a-f]{64})  ([^/].*)$")
STATIC_ARTIFACTS={".gitignore","PRE_REGISTRATION.md","REFINEMENT_PRE_REGISTRATION.md","README.md","RESULTS.md",
  "analysis/analyze_trial.py","analysis/failures.md","analysis/report.txt","analysis/summarize.py","analysis/summary.json",
  "harness/allowtrace.c","harness/probe.m","make_manifest.py","refine.py","run.py","verify.py"}
RUN_TOP_COMMON={"00_inputs.json","02_build_allowtrace.json","03_build_probe.json","SHA256SUMS","failures.json","summary.json","trials"}
EXP0043_REPORTS=[
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/compute_732-cdm.txt","sha256":"ae174d3d772968a9187cbc34b89134eab847fb4364e421037d07c045a69bc727"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/compute_733-cdm-segment0.txt","sha256":"2bdcc4bbc1589ddcabed1fcf58505334e93d0d3887f016dca131e5ace9c19faf"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/compute_733-cdm-segment1.txt","sha256":"f053469de6efecb6462daf93d54c9366d591e89c72d5cfbc1125cd5475af6327"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/render_328-vdm.txt","sha256":"9cc5a078c639b6b5c563b21dff5b36aee2c8a2850b7ab72e6223f93ced46a7ef"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/render_329-vdm-segment0.txt","sha256":"f2df1a69be6ae521e231ac21348da865af3fcb3541717bd7505be0b629690354"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/render_329-vdm-segment1.txt","sha256":"dbc065dcf9346cafb81396b8ca9addf2cbff2bd2da04590a4b115d922003f075"},
]
META_KEYS={"gpu_va","allocation_size","read_size","role","fixed_allowlist","pointer_following","command_mutation"}
EXP0043_ARTIFACT_COMMIT="94bd70083678469867500ba87a22074dde79983e"
EXP0043_MANIFEST_BASE="45854670843e0f35573afc0546995826547cab94"

def digest(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def require(ok:bool,msg:str)->None:
    if not ok:raise AssertionError(msg)

def preflight_allowlisted_payloads()->None:
    """Validate every payload marker and path before any payload is opened."""
    raw=HERE/"raw"
    roots=list(raw.iterdir())
    require({p.name for p in roots}==set(RUNS),"preflight raw run set")
    allowed_payload_paths:set[Path]=set()
    for root in roots:
        require(root.is_dir() and not root.is_symlink(),f"preflight run directory {root}")
        trials=root/"trials"
        require(trials.is_dir() and not trials.is_symlink(),f"preflight trials directory {root}")
        for trial in trials.iterdir():
            require(trial.is_dir() and not trial.is_symlink(),f"preflight trial directory {trial}")
            state=trial/"state"
            require(state.is_dir() and not state.is_symlink(),f"preflight state directory {trial}")
            entries=list(state.iterdir())
            require(all(p.is_file() and not p.is_symlink() for p in entries),f"preflight regular state files {trial}")
            names={p.name for p in entries}
            require(names<=ALLOWED,f"preflight allowlist payload {trial}")
            for stem,(va,cap) in VA.items():
                binary=state/f"{stem}.bin";meta=state/f"{stem}.meta"
                require(binary.exists()==meta.exists(),f"preflight payload pair {trial}/{stem}")
                if not binary.exists():continue
                lines=meta.read_text().splitlines()
                require(len(lines)==len(META_KEYS) and all("=" in line for line in lines),f"preflight meta grammar {meta}")
                fields=dict(line.split("=",1) for line in lines)
                require(set(fields)==META_KEYS,f"preflight meta keys {meta}")
                require(int(fields["gpu_va"],0)==va and fields["role"]==ROLES[stem],f"preflight VA/role {meta}")
                require(fields["fixed_allowlist"]=="1" and fields["pointer_following"]=="0" and fields["command_mutation"]=="0",f"preflight boundary {meta}")
                size=binary.stat().st_size;read_size=int(fields["read_size"],0)
                require(size==read_size<=cap and read_size<=int(fields["allocation_size"],0),f"preflight payload bounds {binary}")
                allowed_payload_paths|={binary,meta}
    observed={p for p in HERE.rglob("*") if p.is_file() and p.suffix in {".bin",".meta"}}
    require(observed==allowed_payload_paths,f"preflight global payload matrix missing={sorted(map(str,allowed_payload_paths-observed))} extra={sorted(map(str,observed-allowed_payload_paths))}")

def check_invocation(path:Path,expected:list[str],timeout:int,expected_exit:int=0)->dict[str,object]:
    rec=json.loads(path.read_text())
    require(rec.get("command")==expected,f"command {path}")
    require(rec.get("timeout_seconds")==timeout and rec.get("exit")==expected_exit and not rec.get("timeout",False),f"invocation status {path}")
    return rec

def main()->int:
    repo=HERE.parents[1]
    for path in HERE.rglob("*"):
        require(not path.is_symlink(),f"symlink forbidden {path}")
        require(path.is_file() or path.is_dir(),f"special filesystem entry {path}")
    for name,want in PLANS.items():require(digest(HERE/name)==want,f"frozen plan {name}")
    # This must precede SHA inventory and manifest hashing: payload bytes are
    # opened only after their exact path and metadata boundary have passed.
    preflight_allowlisted_payloads()
    raw_entries=list((HERE/"raw").iterdir())
    require({p.name for p in raw_entries}==set(RUNS) and all(p.is_dir() and not p.is_symlink() for p in raw_entries),"formal raw run set")
    gpu_processes=0;derived=0;expected_stops=0;expected_artifacts=set(STATIC_ARTIFACTS)
    for run in RUNS:
        root=HERE/"raw"/run;require(root.is_dir() and not root.is_symlink(),f"missing/unsafe {run}")
        environment_name="01_scope.json" if "refine" in run else "01_environment.json"
        expected_root=RUN_TOP_COMMON|{environment_name}
        require({p.name for p in root.iterdir()}==expected_root,f"raw root entries {run}")
        inventory={}
        for line in (root/"SHA256SUMS").read_text().splitlines():
            m=SHA_LINE.fullmatch(line);require(bool(m),f"malformed inventory {run}: {line!r}")
            want,rel=m.groups();rp=PurePosixPath(rel)
            require(rel not in inventory and not rp.is_absolute() and ".." not in rp.parts,f"unsafe inventory {run}/{rel}")
            p=root/Path(*rp.parts);require(p.is_file() and not p.is_symlink(),f"missing/unsafe inventory path {run}/{rel}");require(digest(p)==want,f"raw hash {run}/{rel}")
            inventory[rel]=want
        actual={str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and p.name!="SHA256SUMS"}
        require(set(inventory)==actual,f"inventory coverage {run}")
        expected_artifacts|={str(p.relative_to(HERE)) for p in root.rglob("*") if p.is_file()}
        preflight=json.loads((root/"00_inputs.json").read_text());inputs=preflight["authored_inputs"]
        required_inputs={"PRE_REGISTRATION.md","run.py","harness/probe.m","harness/allowtrace.c","analysis/analyze_trial.py"}
        if "refine" in run:
            required_inputs|={"REFINEMENT_PRE_REGISTRATION.md","refine.py"}
            require(set(preflight)=={"verified_before_build_and_hardware","main_pre_registration_sha256","refinement_pre_registration_sha256","authored_inputs"},f"refinement preflight keys {run}")
            require(preflight["verified_before_build_and_hardware"] is True and preflight["main_pre_registration_sha256"]==PLANS["PRE_REGISTRATION.md"] and preflight["refinement_pre_registration_sha256"]==PLANS["REFINEMENT_PRE_REGISTRATION.md"],f"refinement preregistration binding {run}")
        else:
            require(set(preflight)=={"pre_registration_verified_before_build_and_hardware","pre_registration_sha256","authored_inputs"},f"main preflight keys {run}")
            require(preflight["pre_registration_verified_before_build_and_hardware"] is True and preflight["pre_registration_sha256"]==PLANS["PRE_REGISTRATION.md"],f"main preregistration binding {run}")
        require(set(inputs)==required_inputs,f"input path set {run}")
        for rel,want in inputs.items():require(digest(HERE/rel)==want,f"authored input changed {run}/{rel}")
        scope=json.loads((root/environment_name).read_text())
        if "refine" in run:
            require(scope.get("run_id")==run and scope.get("scope")=="local M4 structural refinement only" and
                    scope.get("pointer_following")==scope.get("command_mutation")==scope.get("unknown_bo_contents")=="NONE",f"refinement scope {run}")
        else:
            require(scope.get("run_id")==run and scope.get("target")=="local Apple M4/G16G only" and
                    scope.get("apple_binary_introspection")==scope.get("unknown_bo_contents")==scope.get("pointer_following")==scope.get("command_mutation")=="NONE" and
                    scope.get("allowlist")==["0x100000b8000","0x10000158000","0x18000","0x88000"],f"main scope {run}")
        tracer=HERE/"work"/run/"allowtrace.dylib";probe=HERE/"work"/run/"probe"
        build_trace=check_invocation(root/"02_build_allowtrace.json",["xcrun","clang","-arch","arm64e","-dynamiclib","-o",str(tracer),str(HERE/"harness/allowtrace.c"),"-framework","IOKit","-framework","CoreFoundation"],60)
        build_probe=check_invocation(root/"03_build_probe.json",["xcrun","clang","-arch","arm64e","-fobjc-arc","-o",str(probe),str(HERE/"harness/probe.m"),"-framework","Metal","-framework","Foundation"],60)
        require(scope["started_unix"]<=build_trace["started_unix"]<=build_probe["started_unix"],f"build chronology {run}")
        expected_failures=([
          {"count":2048,"error":"analysis","exit":1,"phase":"discover","variant":"cdm-indirect"},
          {"count":4096,"error":"analysis","exit":1,"phase":"discover","variant":"vdm-stable"},
          {"count":4096,"error":"analysis","exit":1,"phase":"discover","variant":"vdm-pass1"}]
          if "refine" not in run else [
          {"count":512,"error":"TARGET_WITHOUT_EXACT_PAIR","phase":"approach","variant":"cdm-indirect"},
          {"count":4096,"error":"TARGET_WITHOUT_EXACT_PAIR","phase":"approach","variant":"vdm-stable"},
          {"count":64,"error":"TARGET_WITHOUT_EXACT_PAIR","phase":"approach","variant":"vdm-pass1"}])
        require(json.loads((root/"failures.json").read_text())==expected_failures,f"preserved stop records {run}")
        trials=sorted((root/"trials").iterdir())
        require(all(p.is_dir() and not p.is_symlink() for p in trials),f"trial entries {run}")
        for sequence,trial in enumerate(trials,1):
            gpu_processes+=1
            identity=re.fullmatch(r"(\d{3})_(.+)_(discover|repeat|approach|bisect)_n(\d{4})",trial.name)
            require(bool(identity) and int(identity[1])==sequence,f"trial sequence/name {trial}")
            engine="cdm" if identity[2].startswith("cdm-") else "vdm" if identity[2].startswith("vdm-") else ""
            require(bool(engine),f"trial engine {trial}")
            state=trial/"state";require(state.is_dir() and not state.is_symlink(),f"state directory {trial}")
            state_entries=list(state.iterdir());require(all(p.is_file() and not p.is_symlink() for p in state_entries),f"regular state files {trial}")
            names={p.name for p in state_entries}
            require(names<=ALLOWED,f"allowlist payload {trial}")
            source="va_100000b8000" if engine=="cdm" else "va_18000"
            require(f"{source}.bin" in names and f"{source}.meta" in names,f"source pair {trial}")
            for stem,(va,cap) in VA.items():
                binary=state/f"{stem}.bin";meta=state/f"{stem}.meta"
                require(binary.exists()==meta.exists(),f"payload pair {trial}/{stem}")
                if not binary.exists():continue
                metadata_lines=meta.read_text().splitlines();require(len(metadata_lines)==len(META_KEYS),f"meta line count {meta}")
                fields=dict(line.split("=",1) for line in metadata_lines);require(set(fields)==META_KEYS,f"meta keys {meta}")
                require(int(fields["gpu_va"],0)==va,f"meta VA {meta}")
                require(fields["role"]==ROLES[stem],f"meta role {meta}")
                require(fields.get("fixed_allowlist")=="1" and fields.get("pointer_following")=="0" and fields.get("command_mutation")=="0",f"meta boundary {meta}")
                require(binary.stat().st_size==int(fields["read_size"],0)<=cap,f"payload cap {binary}")
                require(int(fields["read_size"],0)<=int(fields["allocation_size"],0),f"allocation cap {binary}")
            trace=(trial/"trace.log").read_text()
            header="# EXP-0049 fixed_allowlist=4 unknown_bo_dump=0 pointer_following=0 shader_dump=0 command_mutation=0"
            require(trace.splitlines().count(header)==1,f"trace header {trial}")
            dumps=[line for line in trace.splitlines() if line.startswith("ALLOWLIST_DUMP ")]
            require(len(dumps)==len([n for n in names if n.endswith(".bin")]),f"trace dump count {trial}")
            seen=set()
            for line in dumps:
                m=re.fullmatch(r"ALLOWLIST_DUMP va=(0x[0-9a-f]+) alloc=(0x[0-9a-f]+) cap=(0x[0-9a-f]+) got=(0x[0-9a-f]+) role=(\S+) kr=0x([0-9a-f]+)",line)
                require(bool(m),f"trace parse {trial}");dump_va=int(m[1],0)
                stems=[stem for stem,spec in VA.items() if spec[0]==dump_va]
                require(len(stems)==1 and stems[0] not in seen,f"trace VA/duplicate {trial}");stem=stems[0];seen.add(stem)
                fields=dict(x.split("=",1) for x in (state/f"{stem}.meta").read_text().splitlines())
                require(int(m[2],0)==int(fields["allocation_size"],0) and int(m[3],0)==int(fields["read_size"],0) and int(m[4],0)==int(m[3],0) and m[5]==fields["role"] and int(m[6],16)==0,f"trace/meta/binary linkage {trial}/{stem}")
            require(seen=={n[:-4] for n in names if n.endswith(".bin")},f"trace/state set {trial}")
            rec=json.loads((trial/"run.json").read_text());stdout=rec.get("stdout","")
            variants=re.findall(r"^VARIANT name=(\S+) engine=(\S+) count=(\d+) mutation=0$",stdout,re.M)
            require(re.findall(r"^DEVICE (.+)$",stdout,re.M)==["Apple M4"] and variants==[(identity[2],engine,str(int(identity[4])))] and re.findall(r"^COMMAND status=(\d+) error=(.*)$",stdout,re.M)==[("4","none")] and re.findall(r"^RESULT ok=(\d+)$",stdout,re.M)==["1"],f"GPU output/readback {trial}")
            require(rec.get("exit")==0 and not rec.get("timeout",False) and rec.get("timeout_seconds")==45 and rec.get("command")==[str(probe),"--variant",identity[2],"--count",str(int(identity[4])),"--dump"],f"GPU process command {trial}")
            require(rec["started_unix"]>=build_probe["started_unix"],f"process chronology {trial}")
            analysis=trial/"analysis.json"
            expected_trial_entries={"analysis-run.json","run.json","state","trace.log"}|({"analysis.json"} if analysis.exists() else set())
            require({p.name for p in trial.iterdir()}==expected_trial_entries,f"trial artifact set {trial}")
            arec=json.loads((trial/"analysis-run.json").read_text());argv=arec.get("command")
            require(isinstance(argv,list) and len(argv)==8 and Path(argv[0]).name.startswith("python3") and argv[1:]==[str(HERE/"analysis/analyze_trial.py"),"--trial",str(trial),"--engine",engine,"--output",str(analysis)] and arec.get("timeout_seconds")==15 and not arec.get("timeout",False),f"analysis command {trial}")
            if analysis.exists():
                require(arec.get("exit")==0,f"analysis status {trial}")
                with tempfile.TemporaryDirectory(prefix="exp0049-trial-") as tmp:
                    generated=Path(tmp)/"analysis.json"
                    cp=subprocess.run([sys.executable,HERE/"analysis/analyze_trial.py","--trial",trial,"--engine",engine,"--output",generated],capture_output=True,text=True,timeout=15)
                    require(cp.returncode==0,f"analysis regeneration {trial}: {cp.stderr}")
                    require(generated.read_bytes()==analysis.read_bytes(),f"stale trial analysis {trial}")
                derived+=1
            else:
                expected_stops+=1
                require(arec.get("exit")==1 and "presence mismatch" in arec.get("stderr",""),f"unexpected analysis stop {trial}")
    require(gpu_processes==226,f"GPU process count {gpu_processes}")
    require(derived==214,f"trial analysis count {derived}")
    require(expected_stops==12,f"strict stop count {expected_stops}")
    with tempfile.TemporaryDirectory(prefix="exp0049-summary-") as tmp:
        summary=Path(tmp)/"summary.json";report=Path(tmp)/"report.txt"
        cp=subprocess.run([sys.executable,HERE/"analysis/summarize.py","--json",summary,"--report",report],capture_output=True,text=True,timeout=30)
        require(cp.returncode==0,f"summary regeneration: {cp.stderr}")
        require(summary.read_bytes()==(HERE/"analysis/summary.json").read_bytes(),"stale analysis/summary.json")
        require(report.read_bytes()==(HERE/"analysis/report.txt").read_bytes(),"stale analysis/report.txt")
    combined=json.loads((HERE/"analysis/summary.json").read_text())
    require(combined["gpu_processes"]=={"count":226,"nonzero_exit":0,"timeouts":0,"readback_failures":0},"combined process facts")
    require({k:(v["lower_no_link"],v["first_known_link"]) for k,v in combined["positive"].items()}=={
        "cdm-direct":(732,733),"cdm-encoder1":(732,733),"cdm-pad7":(732,733),"vdm-state1":(328,329),"vdm-pad7":(328,329)},"combined thresholds")
    require(combined["bounded_stops"]=={
      "cdm-indirect":{"reason":"TARGET_WITHOUT_EXACT_PAIR","source_sha256":"5f5f44fed8032cc9c560ce808ddef19489f9fda8f55ae6961c075785fd985607","stop_count":512,"target_sha256":"612c09422e7623ab7e7be468499961627254528e53930577342b20352651a52e"},
      "vdm-pass1":{"reason":"TARGET_WITHOUT_EXACT_PAIR","source_draw_packets":64,"source_sha256":"98895e9c31d10c533f2c4e62c40e2d31b72e7e55170e256e22dad45b5458d7b5","stop_count":64,"target_draw_packets":0,"target_sha256":"1e286aab6a4133ced25a35a67046b233a78f40aa0544ac3620b04c7e86ab1eb3"},
      "vdm-stable":{"reason":"TARGET_WITHOUT_EXACT_PAIR","source_draw_packets":1958,"source_sha256":"82aa19b4b2438db3b7ed897177d3068df5eb89e0550a6602e69983a02c30b700","stop_count":4096,"target_draw_packets":174,"target_sha256":"f583db492ca079c6c3d75594d51f9ba7bbe54972f6cfeac76ee48eda1921bd83"}},"combined bounded stops")
    for item in EXP0043_REPORTS:
        path=repo/item["path"];require(path.is_file() and not path.is_symlink() and digest(path)==item["sha256"],f"EXP-0043 prior evidence {item['path']}")
        blob=subprocess.run(["git","-C",repo,"show",f"{EXP0043_ARTIFACT_COMMIT}:{item['path']}"],capture_output=True,timeout=15)
        require(blob.returncode==0 and hashlib.sha256(blob.stdout).hexdigest()==item["sha256"],f"EXP-0043 committed prior evidence {item['path']}")
    prior_manifest=repo/"experiments/EXP-0043-command-stream-framing/manifest.json"
    require(digest(prior_manifest)=="f801b0f516c227fca5e3baa1c588df42dcf1b40f30b091d7aa982a01c0007e88","EXP-0043 manifest hash")
    committed_manifest=subprocess.run(["git","-C",repo,"show",f"{EXP0043_ARTIFACT_COMMIT}:experiments/EXP-0043-command-stream-framing/manifest.json"],capture_output=True,timeout=15)
    require(committed_manifest.returncode==0 and hashlib.sha256(committed_manifest.stdout).hexdigest()=="f801b0f516c227fca5e3baa1c588df42dcf1b40f30b091d7aa982a01c0007e88","EXP-0043 committed manifest")
    prior_parent=subprocess.run(["git","-C",repo,"rev-parse",f"{EXP0043_ARTIFACT_COMMIT}^"],capture_output=True,text=True,check=True,timeout=15).stdout.strip()
    require(prior_parent==EXP0043_MANIFEST_BASE,"EXP-0043 artifact/base ancestry")
    manifest=json.loads((HERE/"manifest.json").read_text());listed={a["path"]:a for a in manifest["artifacts"]}
    actual={str(p.relative_to(HERE)):p for p in HERE.rglob("*") if p.is_file() and p.name!="manifest.json" and "work" not in p.parts and "__pycache__" not in p.parts}
    require(set(actual)==expected_artifacts,f"positive artifact policy missing={sorted(expected_artifacts-set(actual))} extra={sorted(set(actual)-expected_artifacts)}")
    require(len(listed)==len(manifest["artifacts"]) and set(listed)==set(actual),"manifest unique coverage")
    for rel,p in actual.items():
        a=listed[rel];require(a["bytes"]==p.stat().st_size and a["sha256"]==digest(p),f"manifest hash {rel}")
    repository=manifest.get("repository",{});declared_base=repository.get("base_revision_at_manifest")
    require(isinstance(declared_base,str) and re.fullmatch(r"[0-9a-f]{40}",declared_base) is not None,"manifest base syntax")
    ancestry=subprocess.run(["git","-C",repo,"merge-base","--is-ancestor",declared_base,"HEAD"],capture_output=True,text=True,timeout=15)
    require(ancestry.returncode==0,"manifest base is not an ancestor of HEAD")
    require(manifest["schema"]==1 and manifest["experiment"]=="EXP-0049-command-link-structure","manifest identity")
    require(manifest["target"]=={"model":"Mac16,10","soc":"Apple M4","gpu":"Apple M4 / G16G","qualification":"local M4 structural observation only; no A18 Pro validation"},"manifest target")
    require(repository=={"base_revision_at_manifest":declared_base,"authoritative_process":"CODEX.md","gap":"P0.5","base_must_be_ancestor_of_head":True},"manifest repository/base")
    require(manifest["pre_registration"]=={
      "main":{"path":"PRE_REGISTRATION.md","sha256":PLANS["PRE_REGISTRATION.md"]},
      "refinement":{"path":"REFINEMENT_PRE_REGISTRATION.md","sha256":PLANS["REFINEMENT_PRE_REGISTRATION.md"]}},"manifest plans")
    require(manifest["prior_evidence"]=={"experiment":"EXP-0043-command-stream-framing","artifact_commit":EXP0043_ARTIFACT_COMMIT,"manifest_base_revision":EXP0043_MANIFEST_BASE,"manifest":{"path":"experiments/EXP-0043-command-stream-framing/manifest.json","sha256":"f801b0f516c227fca5e3baa1c588df42dcf1b40f30b091d7aa982a01c0007e88"},"clean_boundary_reports":EXP0043_REPORTS},"manifest prior evidence")
    require(manifest["provenance"]=={"categories":["HW-PROBE","DATA-TRACE","OWN-SHADER"],"apple_binary_introspection":"NONE","apple_auxiliary_or_helper_code_inspection":"NONE","compiled_shader_bytes_inspected":"NONE","unknown_bo_contents_inspected":"NONE","pointer_following":"NONE","command_memory_mutation_or_replay":"NONE","command_bo_allowlist":[
      {"gpu_va":"0x100000b8000","role":"CDM segment 0","cap":"0x10000"},{"gpu_va":"0x10000158000","role":"CDM segment 1","cap":"0x10000"},{"gpu_va":"0x18000","role":"VDM segment 0","cap":"0x10000"},{"gpu_va":"0x88000","role":"VDM segment 1","cap":"0x10000"}]},"manifest clean-room provenance")
    require(manifest["authored_build_products"]=={"retention":"ignored rebuildable work products","formal_run_binary_size_sha256":"NOT_RECORDED","limitation":"Formal raw runs retain exact authored source hashes and build/process commands, but did not record executable/interposer size or SHA-256. No binary identity is inferred after the fact."},"manifest build-product limitation")
    require(manifest["runs"]=={"main":["raw/m4-20260817-run01","raw/m4-20260817-run02"],"refinement":["raw/m4-20260817-refine01","raw/m4-20260817-refine02"],"gpu_processes":226,"gpu_errors":0,"gpu_timeouts":0,"readback_failures":0},"manifest runs")
    print(f"PASS plans=2 raw_runs=4 gpu_processes={gpu_processes} trial_analyses={derived} strict_stops={expected_stops} manifest_artifacts={len(listed)}")
    return 0

if __name__=="__main__":raise SystemExit(main())
