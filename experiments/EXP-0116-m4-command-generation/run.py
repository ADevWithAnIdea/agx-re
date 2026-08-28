#!/usr/bin/env python3
"""EXP-0116 run.py -- executes the frozen case matrix (casematrix.py) for
both harness programs on the local M4, and writes the GATED/NON-GATED raw
records (schema.py) with append+fflush per record.

CLEAN ROOM: drives our own authored C/ObjC harnesses (harness/linksplice.m,
harness/codeswap.m) under the unmodified, read-only tools/iotrace/iotrace.c
interposer. Never inspects any Apple binary.

Usage:
  python3 run.py --run-id m4_YYYYMMDD_runNN --execute
  python3 run.py --run-id <id> --smoke-only   # smoke gate only, writes
                                               # nothing under raw/

Safety: one case = one subprocess, hard per-case timeout (default 40s,
covering the harness's own 15s internal watchdog plus Metal/process
start-up and dump I/O margin). A run id is refused if raw/<run-id>/ already
exists (never reuse or silently top up a run id).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import schema
import casematrix

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
IOTRACE_SRC = os.path.join(REPO_ROOT, "tools", "iotrace", "iotrace.c")
IOTRACE_README = os.path.join(REPO_ROOT, "tools", "iotrace", "README.md")
BIN_DIR = os.path.join(HERE, "work", "bin")
LINKSPLICE_BIN = os.path.join(BIN_DIR, "linksplice")
CODESWAP_BIN = os.path.join(BIN_DIR, "codeswap")
IOTRACE_DYLIB = os.path.join(BIN_DIR, "iotrace.dylib")

CASE_TIMEOUT_SEC = 40
DUMP_WAIT_US = 1200000
WATCHDOG_SEC = 15


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def build_all():
    os.makedirs(BIN_DIR, exist_ok=True)
    steps = [
        ["xcrun", "clang", "-dynamiclib", "-O2", "-o", IOTRACE_DYLIB, IOTRACE_SRC,
         "-framework", "IOKit", "-framework", "CoreFoundation"],
        ["xcrun", "clang", "-fobjc-arc", "-O2", "-o", LINKSPLICE_BIN,
         os.path.join(HERE, "harness", "linksplice.m"),
         "-framework", "Metal", "-framework", "Foundation"],
        ["xcrun", "clang", "-fobjc-arc", "-O2", "-o", CODESWAP_BIN,
         os.path.join(HERE, "harness", "codeswap.m"),
         "-framework", "Metal", "-framework", "Foundation"],
    ]
    for cmd in steps:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print("BUILD FAILED:", " ".join(cmd), file=sys.stderr)
            print(r.stdout, r.stderr, file=sys.stderr)
            sys.exit(1)
    print("build: OK")


def run_one(binary, extra_args, dump_dir, out_json, timeout=CASE_TIMEOUT_SEC):
    os.makedirs(dump_dir, exist_ok=True)
    env = dict(os.environ)
    env["IOTRACE_LOG"] = out_json + ".iotrace.log"
    env["IOTRACE_DUMP_DIR"] = dump_dir
    env["DYLD_INSERT_LIBRARIES"] = IOTRACE_DYLIB
    cmd = [binary, "--dump-dir", dump_dir, "--out", out_json,
           "--watchdog-sec", str(WATCHDOG_SEC), "--dump-wait-us", str(DUMP_WAIT_US)] + extra_args
    try:
        r = subprocess.run(cmd, env=env, timeout=timeout, capture_output=True, text=True)
        return {"process_timeout": False, "returncode": r.returncode,
                "stdout": r.stdout, "stderr": r.stderr}
    except subprocess.TimeoutExpired as e:
        return {"process_timeout": True, "returncode": None,
                "stdout": (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                "stderr": (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")}


def smoke_gate(work_dir):
    """Runs baseline_check into work/ (never raw/) and requires
    natural_chain_ok true before any raw/<run-id>/ is created."""
    dump_dir = os.path.join(work_dir, "smoke_dumps")
    out_json = os.path.join(work_dir, "smoke_result.json")
    res = run_one(LINKSPLICE_BIN, ["--case", "baseline_check", "--mechanism", "same_cb"], dump_dir, out_json)
    if res["process_timeout"] or res["returncode"] != 0:
        print("SMOKE GATE FAILED (process):", res, file=sys.stderr)
        return False
    if not os.path.exists(out_json):
        print("SMOKE GATE FAILED: no output JSON", file=sys.stderr)
        return False
    with open(out_json) as f:
        d = json.load(f)
    ok = bool(d.get("natural_chain_ok")) and d.get("found_seg0") and d.get("found_seg1") and d.get("found_seg2")
    print("SMOKE GATE:", "PASS" if ok else "FAIL", d)
    return ok


def provenance(run_dir):
    git_rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True).stdout.strip()
    git_dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT,
                                capture_output=True, text=True).stdout.strip() != ""
    info = {
        "git_head_at_run_time": git_rev,
        "git_dirty_at_run_time": git_dirty,
        "note": "HEAD is recorded for audit only; the pinned revision in CAPTURE_CONTRACT.json is authoritative (sibling experiments' commits moving HEAD is not contamination)",
        "authored_sha256": {
            "harness/linksplice.m": sha256_file(os.path.join(HERE, "harness", "linksplice.m")),
            "harness/codeswap.m": sha256_file(os.path.join(HERE, "harness", "codeswap.m")),
            "schema.py": sha256_file(os.path.join(HERE, "schema.py")),
            "casematrix.py": sha256_file(os.path.join(HERE, "casematrix.py")),
            "run.py": sha256_file(os.path.join(HERE, "run.py")),
        },
        "tools_ro_sha256": {
            "tools/iotrace/iotrace.c": sha256_file(IOTRACE_SRC),
            "tools/iotrace/README.md": sha256_file(IOTRACE_README),
        },
        "environment": {
            "target": "local Apple M4 (G16G), macOS 26.6.2 (25G82), Metal 4",
            "case_timeout_sec": CASE_TIMEOUT_SEC,
            "watchdog_sec": WATCHDOG_SEC,
            "dump_wait_us": DUMP_WAIT_US,
        },
    }
    with open(os.path.join(run_dir, "00_inputs.json"), "w") as f:
        json.dump(info, f, indent=2)
        f.write("\n")
        f.flush()
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--smoke-only", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()

    if not args.skip_build:
        build_all()

    work_dir = os.path.join(HERE, "work", args.run_id)
    os.makedirs(work_dir, exist_ok=True)

    if not smoke_gate(work_dir):
        print("STOP: smoke gate failed; no raw/ directory created.", file=sys.stderr)
        sys.exit(1)

    if args.smoke_only:
        print("smoke-only requested; stopping after smoke gate.")
        return

    raw_dir = os.path.join(HERE, "raw", args.run_id)
    if os.path.exists(raw_dir):
        print(f"STOP: raw/{args.run_id}/ already exists -- never reuse a run id.", file=sys.stderr)
        sys.exit(1)
    os.makedirs(raw_dir)

    provenance(raw_dir)

    gated_path = os.path.join(raw_dir, "02_results.jsonl")
    addrs_path = os.path.join(raw_dir, "02_results_addrs.jsonl")
    meta_path = os.path.join(raw_dir, "02_results_meta.jsonl")

    with open(gated_path, "a") as gf, open(addrs_path, "a") as af, open(meta_path, "a") as mf:
        case_index = 0
        for case_name, mechanism, extra in casematrix.LINKSPLICE_CASES:
            case_index += 1
            dump_dir = os.path.join(work_dir, f"case{case_index:02d}_{case_name}", "dumps")
            out_json = os.path.join(work_dir, f"case{case_index:02d}_{case_name}", "result.json")
            os.makedirs(os.path.dirname(out_json), exist_ok=True)
            print(f"[{args.run_id}] case {case_index}: linksplice --case {case_name} --mechanism {mechanism}")
            proc = run_one(LINKSPLICE_BIN, ["--case", case_name, "--mechanism", mechanism] + extra, dump_dir, out_json)
            meta = {"harness": "linksplice", "case": case_name, "mechanism": mechanism,
                     "process_timeout": proc["process_timeout"], "returncode": proc["returncode"],
                     "t": time.time()}
            mf.write(json.dumps(meta) + "\n"); mf.flush(); os.fsync(mf.fileno())
            if proc["process_timeout"] or not os.path.exists(out_json):
                gated = {"case": case_name, "mechanism": mechanism, "PROCESS_LEVEL_TIMEOUT_OR_MISSING_OUTPUT": True}
                addrs = {}
            else:
                with open(out_json) as f:
                    result = json.load(f)
                gated = schema.build_gated_linksplice(result)
                addrs = schema.build_addrs_linksplice(result)
                schema.assert_no_address_leak(gated)
            gf.write(json.dumps(gated) + "\n"); gf.flush(); os.fsync(gf.fileno())
            af.write(json.dumps(addrs) + "\n"); af.flush(); os.fsync(af.fileno())

        for case_name, _, extra in casematrix.CODESWAP_CASES:
            case_index += 1
            dump_dir = os.path.join(work_dir, f"case{case_index:02d}_{case_name}", "dumps")
            out_json = os.path.join(work_dir, f"case{case_index:02d}_{case_name}", "result.json")
            os.makedirs(os.path.dirname(out_json), exist_ok=True)
            print(f"[{args.run_id}] case {case_index}: codeswap")
            proc = run_one(CODESWAP_BIN, [], dump_dir, out_json)
            meta = {"harness": "codeswap", "case": case_name,
                     "process_timeout": proc["process_timeout"], "returncode": proc["returncode"],
                     "t": time.time()}
            mf.write(json.dumps(meta) + "\n"); mf.flush(); os.fsync(mf.fileno())
            if proc["process_timeout"] or not os.path.exists(out_json):
                gated = {"case": case_name, "PROCESS_LEVEL_TIMEOUT_OR_MISSING_OUTPUT": True}
                addrs = {}
            else:
                with open(out_json) as f:
                    result = json.load(f)
                gated = schema.build_gated_codeswap(result)
                gated["case"] = case_name
                addrs = schema.build_addrs_codeswap(result)
                schema.assert_no_address_leak(gated)
            gf.write(json.dumps(gated) + "\n"); gf.flush(); os.fsync(gf.fileno())
            af.write(json.dumps(addrs) + "\n"); af.flush(); os.fsync(af.fileno())

    print(f"[{args.run_id}] complete: {case_index} cases -> {gated_path}")


if __name__ == "__main__":
    main()
