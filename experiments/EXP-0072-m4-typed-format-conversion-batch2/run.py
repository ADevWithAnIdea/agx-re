#!/usr/bin/env python3
"""Opt-in capture runner; never runs unless --execute is explicit.

Each case is one fresh harness process (fresh device, library, pipelines,
buffers, texture, command buffer). The runner records argv, cwd, timeouts,
timestamps, and complete stdout/stderr receipts into an append-only raw tree.
API-level rejections (exit 0 with a non-"ok" status) are recorded outcomes.
Any nonzero exit, timeout, or OS error is a harness fault: STOP.json is
written, the run ends, and nothing is retried automatically.

The record builders (env_record, run_manifest_record, case_argv) are separate
functions so verify.py --selftest can prove the capture schema is satisfiable
before any GPU work (lesson from quarantined EXP-0073).
"""
import argparse, datetime, hashlib, json, platform, shutil, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
RUNS = ("m4-20260827-run01", "m4-20260827-run02")
AUTH = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "kernels/format_batch2.metal",
        "harness/probe.m", "run.py", "analysis.py", "make_manifest.py", "verify.py")
BOUNDARY = "public Metal only; owned in-bounds buffers; no binary/archive/BO inspection"

def contract():
    return json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())

def cases():
    return contract()["cases"]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def provenance():
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True, capture_output=True, check=True).stdout.strip()
    por = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=HERE, text=True, capture_output=True, check=True).stdout.splitlines()
    return {"git_revision": rev, "git_dirty": bool(por), "authored_sha256": {x: sha(HERE / x) for x in AUTH}}

def put(p, o):
    p.write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")

def rec(argv, timeout):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run([str(x) for x in argv], cwd=HERE, text=True, capture_output=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": True, "exit": None,
                "stdout": e.stdout or "", "stderr": e.stderr or "", "exception": "TimeoutExpired"}
    except OSError as e:
        return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": None,
                "stdout": "", "stderr": "", "exception": type(e).__name__}

def env_record():
    return {"schema": 1, **provenance(),
            "sw_vers": rec(["sw_vers"], 5),
            "xcrun_version": rec(["xcrun", "--version"], 5),
            "device_model": rec(["sysctl", "-n", "hw.model"], 5),
            "machine": platform.machine(), "boundary": BOUNDARY}

def build_argv(work_dir):
    return ["xcrun", "clang", "-fobjc-arc", "-o", work_dir / "probe", HERE / "harness/probe.m",
            "-framework", "Metal", "-framework", "Foundation"]

def case_argv(work_dir, c):
    return [work_dir / "probe", "--source", HERE / "kernels/format_batch2.metal",
            "--case", c["case"], "--format", c["format"],
            "--texel-bytes", str(c["texel_bytes"]), "--reader", c["reader"]]

def run_manifest_record(run_id, case_ids):
    return {"schema": 1, "run_id": run_id, "cases": list(case_ids), "fresh_process_per_case": True,
            "runner_sha256": sha(HERE / "run.py"),
            "harness_sha256": sha(HERE / "harness/probe.m"),
            "kernel_sha256": sha(HERE / "kernels/format_batch2.metal"),
            "contract_sha256": sha(HERE / "CAPTURE_CONTRACT.json")}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ",".join(RUNS))
    gates = ("--preflight", "--selftest") if a.run_id == RUNS[0] else ("--between-runs", "--selftest")
    for g in gates:
        if subprocess.run(["python3", "-B", "verify.py", g], cwd=HERE).returncode:
            raise SystemExit("run gate failed: " + g)
    current = provenance()
    if a.run_id == RUNS[1]:
        first = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        for key in ("git_revision", "authored_sha256"):
            if first.get(key) != current[key]:
                raise SystemExit("run02 provenance differs from closed run01")
    raw = HERE / "raw" / a.run_id
    work_root = HERE / "work" / a.run_id
    if raw.exists() or work_root.exists():
        raise SystemExit("append-only path already exists")
    raw.mkdir(parents=True)
    work_root.mkdir(parents=True)
    try:
        cs = cases()
        env = env_record()
        put(raw / "00_inputs.json", env)
        if any(z["timed_out"] or z["exit"] != 0 or z["exception"] is not None
               for z in (env["sw_vers"], env["xcrun_version"], env["device_model"])):
            put(raw / "STOP.json", {"schema": 1, "phase": "environment", "automatic_retry": False})
            return
        build = rec(build_argv(work_root), 120)
        put(raw / "01_host_build.json", build)
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None:
            put(raw / "STOP.json", {"schema": 1, "phase": "host_build", "automatic_retry": False})
            return
        for c in cs:
            z = rec(case_argv(work_root, c), 300)
            put(raw / f"case_{c['case']}.json", z)
            if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
                put(raw / "STOP.json", {"schema": 1, "phase": "case", "case": c["case"], "automatic_retry": False})
                return
        put(raw / "run_manifest.json", run_manifest_record(a.run_id, [c["case"] for c in cs]))
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

if __name__ == "__main__":
    main()
