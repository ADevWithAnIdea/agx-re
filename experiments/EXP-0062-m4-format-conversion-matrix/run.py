#!/usr/bin/env python3
"""Append-only EXP-0062 runner; every named case is a fresh process."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ("rgba8unorm_edges", "bgra8unorm_edges", "rgba8srgb_threshold", "r16unorm_midpoint", "rgba16float_edges", "r32uint_exact")


def record(command, timeout):
    started = time.monotonic()
    try:
        p = subprocess.run([str(x) for x in command], text=True, capture_output=True, timeout=timeout)
        return {"command": [str(x) for x in command], "timeout": False, "exit": p.returncode,
                "seconds": round(time.monotonic() - started, 3), "stdout": p.stdout, "stderr": p.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"command": [str(x) for x in command], "timeout": True, "seconds": timeout,
                "stdout": exc.stdout or "", "stderr": exc.stderr or ""}


def write(path, obj): path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--run-id", required=True); args = ap.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum(): raise SystemExit("bad run ID")
    raw, work = HERE / "raw" / args.run_id, HERE / "work" / args.run_id
    raw.mkdir(parents=True, exist_ok=False); work.mkdir(parents=True, exist_ok=False)
    try:
        source_in = HERE / "kernels/format_matrix.metal"; sources = raw / "sources"; sources.mkdir()
        source = sources / source_in.name; shutil.copyfile(source_in, source)
        env = {"git_revision": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True, capture_output=True, check=True).stdout.strip(),
               "source_sha256": sha(source), "source_path": str(source.relative_to(HERE)),
               "sw_vers": record(["sw_vers"], 5), "xcode": record(["xcrun", "--version"], 5)}
        write(raw / "00_environment.json", env)
        probe = work / "probe"; build = record(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation", "-o", probe, HERE / "harness/probe.m"], 30)
        write(raw / "01_build.json", build)
        if build["timeout"] or build.get("exit") != 0: return
        for name in CASES:
            result = record([probe, "--source", source, "--case", name], 20)
            write(raw / f"case_{name}.json", result)
            if result["timeout"]:
                write(raw / "STOP.json", {"reason": "process timeout", "case": name, "automatic_recovery": False})
                break
        write(raw / "run_manifest.json", {"run_id": args.run_id, "cases": CASES, "fresh_process_per_case": True,
              "source_sha256": sha(source), "runner_sha256": sha(Path(__file__)), "probe_source_sha256": sha(HERE / "harness/probe.m")})
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__": main()
