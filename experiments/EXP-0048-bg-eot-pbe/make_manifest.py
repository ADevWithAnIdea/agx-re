#!/usr/bin/env python3
"""Create the complete EXP-0048 clean-room SHA-256 inventory."""
from __future__ import annotations
from datetime import datetime
import hashlib
import json
import platform
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]

def command(argv:list[str])->str:
    return subprocess.run(argv,capture_output=True,text=True,check=True,timeout=15).stdout.strip()

def digest(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def main()->None:
    artifacts=[]
    for p in sorted(HERE.rglob("*")):
        if not p.is_file() or p.name=="manifest.json" or "work" in p.parts or "__pycache__" in p.parts:continue
        artifacts.append({"path":str(p.relative_to(HERE)),"bytes":p.stat().st_size,"sha256":digest(p)})
    manifest={
      "experiment":"EXP-0048-bg-eot-pbe",
      "generated":datetime.now().astimezone().isoformat(),
      "target":{"model":command(["sysctl","-n","hw.model"]),"soc":"Apple M4",
                "gpu":"Apple M4 / IOKit AGXAcceleratorG16G",
                "qualification":"local M4 observation only; no A18 Pro validation"},
      "host":{"platform":platform.platform(),"sw_vers":command(["sw_vers"]),
              "clang":command(["clang","--version"]).splitlines()[0]},
      "repository":{"head_at_manifest":command(["git","-C",str(REPO),"rev-parse","HEAD"]),
                    "authoritative_process":"CODEX.md",
                    "gaps":["AGX_RE_INFORMATION_GAPS.md P0.4","AGX_RE_INFORMATION_GAPS.md P1.1"]},
      "pre_registration":{"main":{"path":"PRE_REGISTRATION.md","sha256":"872ea37e256cc196d4e62e41a48d77f14eb9303c4fa7cc9509e63298941ffa78"},
                          "blend_control":{"path":"CONTROL_PRE_REGISTRATION.md","sha256":"588ccdf3a234c790e12311d99bf142d7b476a9663506409bf0bda66117bd35d1"}},
      "provenance":{"categories":["HW-PROBE","DATA-TRACE","OWN-SHADER","PUBLIC-hypothesis-only"],
                    "apple_binary_introspection":"NONE",
                    "apple_auxiliary_or_helper_code_inspection":"NONE",
                    "compiled_shader_bytes_inspected":"NONE",
                    "unknown_bo_contents_inspected":"NONE",
                    "pointer_following":"NONE",
                    "command_state_allowlist":[
                      {"gpu_va":"0x18000","role":"VDM command/state","cap":"0x10000"},
                      {"gpu_va":"0x58000","role":"fixed-function render state","cap":"0x10000"},
                      {"gpu_va":"0x68000","role":"tiling state","cap":"0x10000"},
                      {"gpu_va":"0x10000018200","role":"MRT attachment descriptors","cap":"0x1000"}],
                    "allowlist_basis":["EXP-M4-03-cmdstream-pipeline","EXP-M4-09-cmdstream-coverage/cmd3-mrt"]},
      "runs":{"primary":["raw/m4_20260817_run01","raw/m4_20260817_run02"],
              "blend_controls":["raw/m4_20260817_blend_control01","raw/m4_20260817_blend_control02"],
              "preflight_failures":"raw/preflight_failures.md",
              "hard_timeouts":True,"formal_gpu_errors":0,"formal_timeouts":0},
      "artifacts":artifacts,
    }
    (HERE/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")

if __name__=="__main__":main()
