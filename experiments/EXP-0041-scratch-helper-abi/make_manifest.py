#!/usr/bin/env python3
"""Create the clean-room manifest and SHA-256 inventory for EXP-0041."""
from datetime import datetime
import hashlib, json, platform, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent; REPO=HERE.parents[1]
def command(args):
    return subprocess.run(args,capture_output=True,text=True,timeout=15,check=True).stdout.strip()
def main():
    artifacts=[]
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name=="manifest.json" or "__pycache__" in path.parts or "work" in path.parts:continue
        data=path.read_bytes();artifacts.append({"path":str(path.relative_to(HERE)),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    manifest={
      "experiment":"EXP-0041-scratch-helper-abi","generated":datetime.now().astimezone().isoformat(),
      "target":{"model":"Mac16,10","soc":"Apple M4","gpu":"Apple M4 / IOKit AGXAcceleratorG16G","gpu_cores":10,
                "qualification":"M4 observation only; no A18 Pro validation"},
      "host":{"platform":platform.platform(),"sw_vers":command(["sw_vers"]),"clang":command(["clang","--version"]).splitlines()[0]},
      "repository":{"head":command(["git","-C",str(REPO),"rev-parse","HEAD"]),
                    "authoritative_process":"CODEX.md","gap":"AGX_RE_INFORMATION_GAPS.md P0.1"},
      "provenance":{"categories":["HW-PROBE","DATA-TRACE","OWN-SHADER","PUBLIC-hypothesis-only"],
                    "apple_binary_introspection":"NONE","pointer_following":"NONE",
                    "captured_executable_bytes":"only _agc.main from the complete MSL sources in kernels/",
                    "apple_helper_program_bytes":"NOT CAPTURED OR INSPECTED",
                    "command_data_allowlist":["0x18000 VDM","0x58000 fixed-function state","0x68000 geometry state","0x100000b0000 compute launch descriptor"],
                    "allowlist_basis":["EXP-0011","EXP-0014","EXP-M4-03"]},
      "runs":{"primary":["raw/m4_20260817_run01","raw/m4_20260817_run02"],
              "scale":["raw/m4_20260817_scale01","raw/m4_20260817_scale_control01"],
              "preflight_failures":"raw/preflight_failures.txt"},
      "artifacts":artifacts}
    (HERE/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
