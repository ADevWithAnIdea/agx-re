#!/usr/bin/env python3
"""Build and execute EXP-0041 with hard timeouts; raw outputs are never overwritten."""
import json
import os
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
RAW_ROOT = HERE / "raw"
KERNELS = HERE / "kernels"
H = HERE / "harness"

CASES = [
    ("cs_nospill_k72", "cs", 72), ("cs_spill_k80", "cs", 80),
    ("cs_spill_k96", "cs", 96), ("cs_spill_k112", "cs", 112), ("cs_spill_k160", "cs", 160),
    ("vs_nospill_k72", "vs", 72), ("vs_spill_k112", "vs", 112),
    ("fs_nospill_k72", "fs", 72), ("fs_spill_k112", "fs", 112),
]

def run(cmd, out, timeout, env=None):
    started = time.time()
    try:
        cp = subprocess.run([str(x) for x in cmd], capture_output=True, text=True, timeout=timeout, env=env)
        text = f"COMMAND {json.dumps([str(x) for x in cmd])}\nEXIT {cp.returncode}\nSECONDS {time.time()-started:.3f}\nSTDOUT\n{cp.stdout}\nSTDERR\n{cp.stderr}"
    except subprocess.TimeoutExpired as e:
        text = f"COMMAND {json.dumps([str(x) for x in cmd])}\nTIMEOUT {timeout}\nSTDOUT\n{e.stdout or ''}\nSTDERR\n{e.stderr or ''}"
        out.write_text(text); raise
    out.write_text(text)
    if cp.returncode: raise RuntimeError(f"failed: {cmd}; see {out}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, help="new append-only raw subdirectory name")
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("run-id must contain only alphanumerics, dash, underscore")
    RAW = RAW_ROOT / args.run_id
    RAW.mkdir(parents=True, exist_ok=False)
    work = HERE / "work" / args.run_id
    work.mkdir(parents=True, exist_ok=False)
    run([sys.executable, KERNELS / "generate.py"], RAW / "00_generate.log", 20)
    build = RAW / "01_build.log"
    maptrace = work / "maptrace.dylib"; probe = work / "probe"
    run(["clang", "-dynamiclib", "-o", maptrace, H / "maptrace.c", "-framework", "IOKit", "-framework", "CoreFoundation"], build, 30)
    run(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation", "-o", probe, H / "probe.m"], RAW / "02_build_probe.log", 30)
    for name, stage, k in CASES:
        source = KERNELS / f"{name}.metal"
        run([sys.executable, H / "metadata.py", "--stage", stage, "--source", source], RAW / f"metadata_{name}.log", 100)
        case_dir = RAW / f"cmd_{name}"; case_dir.mkdir(exist_ok=True)
        env = os.environ.copy(); env.update({
            "DYLD_INSERT_LIBRARIES": str(maptrace),
            "MAPTRACE_LOG": str(RAW / f"map_{name}.log"),
            "MAPTRACE_DUMP_DIR": str(case_dir),
            # Prior clean experiments establish these as command/state BOs.
            # No pointed-to VA is ever added or followed.
            "MAPTRACE_DUMP_GPU_VAS": "0x18000,0x58000,0x68000,0x100000b0000",
        })
        run([probe, "--stage", stage, "--source", source, "--k", k], RAW / f"run_{name}.log", 45, env)
    shutil.rmtree(work)
    print("runs complete; invoke analysis/analyze.py")

if __name__ == "__main__": main()
