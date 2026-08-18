#!/usr/bin/env python3
"""Create complete EXP-0049 artifact manifest, excluding build products."""
from __future__ import annotations
from datetime import datetime
import hashlib
import json
import platform
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
RUNS={"m4-20260817-run01","m4-20260817-run02","m4-20260817-refine01","m4-20260817-refine02"}
VA={"va_100000b8000":(0x100000B8000,0x10000),"va_10000158000":(0x10000158000,0x10000),
    "va_18000":(0x18000,0x10000),"va_88000":(0x88000,0x10000)}
ROLES={"va_100000b8000":"cdm-segment-0","va_10000158000":"cdm-segment-1",
       "va_18000":"vdm-segment-0","va_88000":"vdm-segment-1"}
ALLOWED={f"{stem}.{suffix}" for stem in VA for suffix in ("bin","meta")}
META_KEYS={"gpu_va","allocation_size","read_size","role","fixed_allowlist","pointer_following","command_mutation"}
EXP0043_REPORTS=[
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/compute_732-cdm.txt","sha256":"ae174d3d772968a9187cbc34b89134eab847fb4364e421037d07c045a69bc727"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/compute_733-cdm-segment0.txt","sha256":"2bdcc4bbc1589ddcabed1fcf58505334e93d0d3887f016dca131e5ace9c19faf"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/compute_733-cdm-segment1.txt","sha256":"f053469de6efecb6462daf93d54c9366d591e89c72d5cfbc1125cd5475af6327"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/render_328-vdm.txt","sha256":"9cc5a078c639b6b5c563b21dff5b36aee2c8a2850b7ab72e6223f93ced46a7ef"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/render_329-vdm-segment0.txt","sha256":"f2df1a69be6ae521e231ac21348da865af3fcb3541717bd7505be0b629690354"},
  {"path":"experiments/EXP-0043-command-stream-framing/raw/clean-analysis/m4-20260817-boundaries-a/render_329-vdm-segment1.txt","sha256":"dbc065dcf9346cafb81396b8ca9addf2cbff2bd2da04590a4b115d922003f075"},
]

def command(argv:list[str])->str:
    return subprocess.run(argv,capture_output=True,text=True,check=True,timeout=15).stdout.strip()

def digest(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def preflight_allowlisted_payloads()->None:
    """Fail closed on all state payload paths/markers before hashing bytes."""
    roots=list((HERE/"raw").iterdir())
    if {p.name for p in roots}!=RUNS:raise RuntimeError("unexpected raw run set")
    allowed_paths:set[Path]=set()
    for root in roots:
        if not root.is_dir() or root.is_symlink():raise RuntimeError(f"unsafe run directory: {root}")
        trials=root/"trials"
        if not trials.is_dir() or trials.is_symlink():raise RuntimeError(f"unsafe trials directory: {root}")
        for trial in trials.iterdir():
            state=trial/"state"
            if not trial.is_dir() or trial.is_symlink() or not state.is_dir() or state.is_symlink():raise RuntimeError(f"unsafe trial/state: {trial}")
            entries=list(state.iterdir())
            if not all(p.is_file() and not p.is_symlink() for p in entries):raise RuntimeError(f"unsafe state entry: {state}")
            names={p.name for p in entries}
            if not names<=ALLOWED:raise RuntimeError(f"nonallowlisted state payload: {state}")
            for stem,(va,cap) in VA.items():
                binary=state/f"{stem}.bin";meta=state/f"{stem}.meta"
                if binary.exists()!=meta.exists():raise RuntimeError(f"unpaired state payload: {state}/{stem}")
                if not binary.exists():continue
                lines=meta.read_text().splitlines()
                if len(lines)!=len(META_KEYS) or not all("=" in line for line in lines):raise RuntimeError(f"bad metadata grammar: {meta}")
                fields=dict(line.split("=",1) for line in lines)
                if set(fields)!=META_KEYS:raise RuntimeError(f"bad metadata keys: {meta}")
                if int(fields["gpu_va"],0)!=va or fields["role"]!=ROLES[stem]:raise RuntimeError(f"bad metadata role: {meta}")
                if (fields["fixed_allowlist"],fields["pointer_following"],fields["command_mutation"])!=("1","0","0"):raise RuntimeError(f"bad metadata boundary: {meta}")
                size=binary.stat().st_size;read_size=int(fields["read_size"],0)
                if not (size==read_size<=cap and read_size<=int(fields["allocation_size"],0)):raise RuntimeError(f"bad payload bounds: {binary}")
                allowed_paths|={binary,meta}
    observed={p for p in HERE.rglob("*") if p.is_file() and p.suffix in {".bin",".meta"}}
    if observed!=allowed_paths:raise RuntimeError("global payload matrix contains an unvalidated path")

def main()->None:
    # No payload byte is opened until every path and metadata marker passes.
    preflight_allowlisted_payloads()
    artifacts=[]
    for p in sorted(HERE.rglob("*")):
        if p.is_symlink():raise RuntimeError(f"symlink forbidden in experiment: {p}")
        if not p.is_file() or p.name=="manifest.json" or "work" in p.parts or "__pycache__" in p.parts:continue
        artifacts.append({"path":str(p.relative_to(HERE)),"bytes":p.stat().st_size,"sha256":digest(p)})
    data={
      "schema":1,"experiment":"EXP-0049-command-link-structure","generated":datetime.now().astimezone().isoformat(),
      "target":{"model":command(["sysctl","-n","hw.model"]),"soc":"Apple M4","gpu":"Apple M4 / G16G",
                "qualification":"local M4 structural observation only; no A18 Pro validation"},
      "host":{"platform":platform.platform(),"sw_vers":command(["sw_vers"]),"clang":command(["clang","--version"]).splitlines()[0]},
      "repository":{"base_revision_at_manifest":command(["git","-C",str(REPO),"rev-parse","HEAD"]),
                    "authoritative_process":"CODEX.md","gap":"P0.5","base_must_be_ancestor_of_head":True},
      "pre_registration":{
        "main":{"path":"PRE_REGISTRATION.md","sha256":"217063a4dad9831ece3d4fe974876d9d50b4216451c3cd281ae284382f3bc808"},
        "refinement":{"path":"REFINEMENT_PRE_REGISTRATION.md","sha256":"e8e41a3989f1b18c015cc5a55dbf60ca64376d89a9510f4922f03355e9b8a4f1"}},
      "prior_evidence":{"experiment":"EXP-0043-command-stream-framing",
        "artifact_commit":"94bd70083678469867500ba87a22074dde79983e",
        "manifest_base_revision":"45854670843e0f35573afc0546995826547cab94",
        "manifest":{"path":"experiments/EXP-0043-command-stream-framing/manifest.json",
                    "sha256":"f801b0f516c227fca5e3baa1c588df42dcf1b40f30b091d7aa982a01c0007e88"},
        "clean_boundary_reports":EXP0043_REPORTS},
      "provenance":{"categories":["HW-PROBE","DATA-TRACE","OWN-SHADER"],
        "apple_binary_introspection":"NONE","apple_auxiliary_or_helper_code_inspection":"NONE",
        "compiled_shader_bytes_inspected":"NONE","unknown_bo_contents_inspected":"NONE",
        "pointer_following":"NONE","command_memory_mutation_or_replay":"NONE",
        "command_bo_allowlist":[
          {"gpu_va":"0x100000b8000","role":"CDM segment 0","cap":"0x10000"},
          {"gpu_va":"0x10000158000","role":"CDM segment 1","cap":"0x10000"},
          {"gpu_va":"0x18000","role":"VDM segment 0","cap":"0x10000"},
          {"gpu_va":"0x88000","role":"VDM segment 1","cap":"0x10000"}]},
      "authored_build_products":{"retention":"ignored rebuildable work products",
        "formal_run_binary_size_sha256":"NOT_RECORDED",
        "limitation":"Formal raw runs retain exact authored source hashes and build/process commands, but did not record executable/interposer size or SHA-256. No binary identity is inferred after the fact."},
      "runs":{"main":["raw/m4-20260817-run01","raw/m4-20260817-run02"],
              "refinement":["raw/m4-20260817-refine01","raw/m4-20260817-refine02"],
              "gpu_processes":226,"gpu_errors":0,"gpu_timeouts":0,"readback_failures":0},
      "artifacts":artifacts,
    }
    (HERE/"manifest.json").write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")

if __name__=="__main__":main()
