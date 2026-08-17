#!/usr/bin/env python3
"""Build the complete clean-room artifact inventory for EXP-0051."""
from __future__ import annotations
from datetime import datetime
import hashlib,json,platform,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
def command(a):return subprocess.run(a,capture_output=True,text=True,check=True,timeout=15).stdout.strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    artifacts=[]
    for p in sorted(HERE.rglob("*")):
        if not p.is_file() or p.name=="manifest.json" or "work" in p.parts or "__pycache__" in p.parts:continue
        artifacts.append({"path":str(p.relative_to(HERE)),"bytes":p.stat().st_size,"sha256":digest(p)})
    pre=json.loads((HERE/"raw/m4_20260817_run01/00_preflight.json").read_text())
    runner=json.loads((HERE/"raw/m4_20260817_run01/05_runner_hash.json").read_text())
    obj={"experiment":"EXP-0051-m4-synchronization-litmus","generated":datetime.now().astimezone().isoformat(),
      "target":{"model":command(["sysctl","-n","hw.model"]),"soc":"Apple M4","gpu":"Apple M4 / G16G",
                "qualification":"M4 Metal-path observation only; no A18 Pro validation"},
      "host":{"platform":platform.platform(),"sw_vers":command(["sw_vers"]),"clang":command(["clang","--version"]).splitlines()[0]},
      "repository":{"head_at_manifest":command(["git","-C",str(REPO),"rev-parse","HEAD"]),"authoritative_process":"CODEX.md","gap":"AGX_RE_INFORMATION_GAPS.md P1.4"},
      "pre_registration":{"path":"PRE_REGISTRATION.md","sha256":"941eb45f744f6a08b19037cfd147810954fb7365466355f50e1ad652da0d2cec"},
      "exact_authored_input_hashes":pre["exact_input_hashes"],"runner_binary":{"bytes":runner["bytes"],"sha256":runner["sha256"],"same_in_both_runs":True},
      "provenance":{"categories":["HW-PROBE","OWN-SHADER"],"observed":["authored MSL compile acceptance/diagnostics","live Metal completion","process-owned shared-buffer bytes"],
        "apple_binary_introspection":"NONE","apple_auxiliary_or_helper_code_inspection":"NONE","command_or_bo_scan":"NONE","pointer_following":"NONE","compiled_shader_bytes_inspected":"NONE"},
      "runs":["raw/m4_20260817_run01","raw/m4_20260817_run02"],"hard_host_timeout_seconds":180,
      "formal_command_errors":0,"formal_timeouts":0,"expected_compile_rejections_preserved":True,"artifacts":artifacts}
    (HERE/"manifest.json").write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
