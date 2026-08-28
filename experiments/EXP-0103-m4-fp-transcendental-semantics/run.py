#!/usr/bin/env python3
"""EXP-0103 capture runner.

Builds harness/probe.m, runs the NON-RECORDED smoke gate, then -- only with
--execute --run-id <id> -- dispatches every case in analysis/corpus_manifest.json
as its OWN subprocess (one case = one variable = one process), appending a
receipt to raw/<run-id>/receipts.jsonl (fflush'd immediately) and writing
raw/<run-id>/results/<case>.jsonl verbatim from the harness output. A run
directory is only "closed" (see verify.run_dir_complete) once every case has
both a receipt and a results file and 00_manifest.json is written last.

Refuses to run unless verify.py --selftest has just passed. Never reuses a
run id (refuses if the target raw/<run-id>/ already exists and is non-empty).
Faults/timeouts are recorded as results (exit code, timed_out flag, empty or
partial results file) and do NOT abort the rest of the run.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import platform

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_DIR = os.path.join(HERE, "analysis")
KERNEL_SRC = os.path.join(HERE, "kernels", "probe.metal")
HARNESS_SRC = os.path.join(HERE, "harness", "probe.m")
WORK_DIR = os.path.join(HERE, "work")
RAW_DIR = os.path.join(HERE, "raw")
BIN_PATH = os.path.join(WORK_DIR, "probe")

DISPATCH_TIMEOUT_S = 300  # outer belt-and-suspenders on top of the harness's own watchdogs


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def run_capture(cmd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr, False, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -1, e.stdout.decode() if e.stdout else "", (e.stderr.decode() if e.stderr else ""), True, time.time() - t0


def git_info():
    rev = sh(["git", "rev-parse", "HEAD"], cwd=HERE).stdout.strip()
    status = sh(["git", "status", "--porcelain"], cwd=HERE).stdout
    dirty = len(status.strip()) > 0
    exp_dirty = 0
    for line in status.splitlines():
        if "EXP-0103-m4-fp-transcendental-semantics" in line:
            exp_dirty += 1
    return rev, dirty, exp_dirty


def build_harness():
    os.makedirs(WORK_DIR, exist_ok=True)
    cmd = ["xcrun", "clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
           "-O2", "-o", BIN_PATH, HARNESS_SRC]
    p = sh(cmd)
    if p.returncode != 0:
        print("BUILD FAILED:\n", p.stdout, p.stderr)
        return False
    return True


def smoke_gate():
    """NON-RECORDED smoke gate: run the freshly built harness on a tiny
    scratch input (not one of the frozen corpora) into work/, verify shape,
    and NEVER write anything into raw/."""
    scratch_in = os.path.join(WORK_DIR, "smoke_gate_in.bin")
    scratch_out = os.path.join(WORK_DIR, "smoke_gate_out.jsonl")
    with open(scratch_in, "wb") as f:
        import struct
        for v in (0x3F800000, 0x40000000, 0x00000000):
            f.write(struct.pack("<4I", v, 0, 0, 0))
    cmd = [BIN_PATH, "--source", KERNEL_SRC, "--fn", "k_rcp_fast_f32",
           "--cases", scratch_in, "--out", scratch_out, "--n", "3"]
    rc, out, err, timed_out, dur = run_capture(cmd, 60)
    if timed_out or rc != 0:
        print("SMOKE GATE FAILED: rc=%s timed_out=%s stderr=%s" % (rc, timed_out, err))
        return False
    try:
        summary = json.loads(out.strip().splitlines()[-1])
    except Exception as e:
        print("SMOKE GATE FAILED: could not parse harness summary: %s\nstdout=%r" % (e, out))
        return False
    required = {"schema", "fn", "n", "device", "registry_id", "machine", "os", "fast_math",
                "math_mode_raw", "language_version_raw", "library_compile_seconds",
                "dispatch_seconds", "command_buffer_status", "error", "in_prefix_guard",
                "in_suffix_guard", "out_prefix_guard", "out_suffix_guard", "results_written"}
    if set(summary.keys()) != required:
        print("SMOKE GATE FAILED: summary key mismatch, got", set(summary.keys()))
        return False
    if not os.path.isfile(scratch_out):
        print("SMOKE GATE FAILED: no results file")
        return False
    lines = [l for l in open(scratch_out) if l.strip()]
    if len(lines) != 3:
        print("SMOKE GATE FAILED: expected 3 result lines, got", len(lines))
        return False
    for l in lines:
        rec = json.loads(l)
        if set(rec.keys()) != {"i", "r0", "r1", "r2", "r3"}:
            print("SMOKE GATE FAILED: result record key mismatch:", rec)
            return False
    print("SMOKE GATE OK (record shape only, not promoted to raw/)")
    return True


def do_run(run_id):
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    cm_path = os.path.join(ANALYSIS_DIR, "corpus_manifest.json")
    if not os.path.isfile(cm_path):
        print("run.py: corpus_manifest.json missing -- run analysis/gen_all.py first")
        return False
    cm = json.load(open(cm_path))
    cases = cm["cases"]

    run_dir = os.path.join(RAW_DIR, run_id)
    if os.path.isdir(run_dir) and os.listdir(run_dir):
        print("run.py: refusing to reuse non-empty run id %s" % run_id)
        return False
    os.makedirs(os.path.join(run_dir, "results"), exist_ok=True)

    rev, dirty, exp_dirty = git_info()
    sw_vers = sh(["sw_vers"]).stdout.strip()
    xcrun_ver = sh(["xcrun", "--version"]).stdout.strip()
    py_ver = sys.version
    machine = platform.machine()

    receipts_path = os.path.join(run_dir, "receipts.jsonl")
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    device_name = None
    registry_id = None

    with open(receipts_path, "a") as rf:
        for name in sorted(cases.keys()):
            meta = cases[name]
            in_bin = os.path.join(WORK_DIR, "cases", name + ".bin")
            out_jsonl = os.path.join(run_dir, "results", name + ".jsonl")
            fastmath = "yes" if meta.get("fastmath") else "no"
            cmd = [BIN_PATH, "--source", KERNEL_SRC, "--fn", meta["kernel"],
                   "--cases", in_bin, "--out", out_jsonl, "--n", str(meta["n"]),
                   "--fastmath", fastmath]
            t_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            rc, out, err, timed_out, dur = run_capture(cmd, DISPATCH_TIMEOUT_S)
            stdout_summary = None
            if out.strip():
                try:
                    stdout_summary = json.loads(out.strip().splitlines()[-1])
                    if device_name is None:
                        device_name = stdout_summary.get("device")
                        registry_id = stdout_summary.get("registry_id")
                except Exception:
                    stdout_summary = None
            results_sha = None
            results_lines = 0
            if os.path.isfile(out_jsonl):
                data = open(out_jsonl, "rb").read()
                results_sha = hashlib.sha256(data).hexdigest()
                results_lines = data.count(b"\n")
            else:
                # ensure an (empty) results file always exists so run_dir_complete's
                # per-case check is well-defined even on a hard failure
                open(out_jsonl, "wb").close()
                results_sha = hashlib.sha256(b"").hexdigest()
                results_lines = 0
            receipt = {
                "case": name, "kernel": meta["kernel"], "fastmath": bool(meta.get("fastmath", False)),
                "argv": cmd, "cwd": HERE, "started_utc": t_start, "duration_seconds": dur,
                "exit_code": rc, "timed_out": timed_out,
                "stdout_summary": stdout_summary, "stderr_tail": err[-2000:],
                "results_sha256": results_sha, "results_lines": results_lines,
            }
            rf.write(json.dumps(receipt) + "\n")
            rf.flush()
            os.fsync(rf.fileno())
            status = "OK" if (rc == 0 and not timed_out) else "FAULT"
            print("[%s] %-40s exit=%s timed_out=%s dur=%.3fs lines=%d" % (
                status, name, rc, timed_out, dur, results_lines))

    finished_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest = {
        "run_id": run_id, "git_revision": rev, "git_dirty": dirty,
        "experiment_tree_dirty_entries": exp_dirty, "sw_vers": sw_vers,
        "xcrun_version": xcrun_ver, "python_version": py_ver, "machine": machine,
        "started_utc": started_utc, "finished_utc": finished_utc,
        "cases": sorted(cases.keys()), "device_name": device_name,
        "registry_id": registry_id, "schema": 1,
    }
    with open(os.path.join(run_dir, "00_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    print("run %s complete: %d cases" % (run_id, len(cases)))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    sys.path.insert(0, HERE)
    import verify

    if not args.execute:
        print("run.py: refusing to run without --execute")
        sys.exit(2)
    if not args.run_id:
        print("run.py: --run-id is required")
        sys.exit(2)

    print("== verify.py --selftest ==")
    if not verify.selftest():
        print("run.py: selftest failed, refusing to capture")
        sys.exit(3)
    print("== verify.py --seqtest ==")
    if not verify.seqtest():
        print("run.py: seqtest failed, refusing to capture")
        sys.exit(3)
    print("== verify.py --preflight ==")
    if not verify.preflight():
        print("run.py: preflight failed, refusing to capture")
        sys.exit(3)

    print("== build harness ==")
    if not build_harness():
        sys.exit(4)

    print("== smoke gate ==")
    if not smoke_gate():
        sys.exit(5)

    print("== capture %s ==" % args.run_id)
    ok = do_run(args.run_id)
    sys.exit(0 if ok else 6)


if __name__ == "__main__":
    main()
