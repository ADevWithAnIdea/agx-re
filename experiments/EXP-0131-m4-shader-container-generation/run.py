#!/usr/bin/env python3
"""EXP-0131 run driver.

Builds the OWN-SHADER/DATA-TRACE harness (harness/codesplice.m) and the
unmodified, read-only tools/iotrace/iotrace.c interposer, runs a NON-RECORDED
smoke gate (baseline_check only, into work/, never raw/), then drives the
full case matrix (casematrix.CASES) once per case, one process per case (per
SUBAGENT_BRIEF.md), each under a hard timeout, appending gated + non-gated
JSONL records to raw/<run-id>/ with fflush after every record.

Usage:
    python3 run.py --run-id m4_20260828_run01
    python3 run.py --run-id m4_20260828_run01 --smoke-only
"""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import schema
from casematrix import CASES

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT.parent.parent / "tools"
WORK = ROOT / "work"
BIN = WORK / "bin"
RAW = ROOT / "raw"

CASE_TIMEOUT_SEC = 45
WATCHDOG_SEC = 15
DUMP_WAIT_US = 1000000


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def build():
    BIN.mkdir(parents=True, exist_ok=True)
    codesplice_src = ROOT / "harness" / "codesplice.m"
    iotrace_src = TOOLS / "iotrace" / "iotrace.c"
    codesplice_bin = BIN / "codesplice"
    iotrace_dylib = BIN / "iotrace.dylib"

    subprocess.run(
        ["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
         "-o", str(codesplice_bin), str(codesplice_src)],
        check=True, cwd=str(WORK),
    )
    subprocess.run(
        ["clang", "-dynamiclib", "-o", str(iotrace_dylib), str(iotrace_src),
         "-framework", "IOKit", "-framework", "CoreFoundation"],
        check=True, cwd=str(WORK),
    )
    return codesplice_bin, iotrace_dylib, codesplice_src, iotrace_src


def run_one_case(codesplice_bin: Path, iotrace_dylib: Path, case: str, out_dir: Path,
                  tag: str) -> dict:
    """Runs one case in its own process. Returns a dict with:
    exit_code, timed_out(bool), signal(str|None), stdout_path, stderr_path,
    json_path, json (parsed dict or None)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_dir = out_dir / f"dumps_{case}"
    dump_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"case_{case}.json"
    stdout_path = out_dir / f"case_{case}.stdout.log"
    stderr_path = out_dir / f"case_{case}.stderr.log"
    iotrace_log = out_dir / f"case_{case}.iotrace.log"

    env = dict(os.environ)
    env["DYLD_INSERT_LIBRARIES"] = str(iotrace_dylib)
    env["IOTRACE_LOG"] = str(iotrace_log)
    env["IOTRACE_DUMP_DIR"] = str(dump_dir)

    cmd = [str(codesplice_bin), "--case", case, "--dump-dir", str(dump_dir),
           "--watchdog-sec", str(WATCHDOG_SEC), "--dump-wait-us", str(DUMP_WAIT_US),
           "--out", str(out_json)]

    timed_out = False
    sig = None
    t0 = time.time()
    with open(stdout_path, "w") as so, open(stderr_path, "w") as se:
        proc = subprocess.Popen(cmd, stdout=so, stderr=se, env=env, cwd=str(ROOT))
        try:
            rc = proc.wait(timeout=CASE_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            try:
                rc = proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                rc = None
    elapsed = time.time() - t0

    if rc is not None and rc < 0:
        sig = signal.Signals(-rc).name if -rc in signal.Signals._value2member_map_ else str(-rc)

    parsed = None
    if out_json.exists():
        try:
            parsed = json.loads(out_json.read_text())
        except Exception as e:
            parsed = {"__parse_error__": str(e)}

    return {
        "tag": tag,
        "case": case,
        "cmd": cmd,
        "exit_code": rc,
        "timed_out": timed_out,
        "signal": sig,
        "elapsed_sec": round(elapsed, 3),
        "stdout_path": str(stdout_path.relative_to(ROOT)),
        "stderr_path": str(stderr_path.relative_to(ROOT)),
        "json_path": str(out_json.relative_to(ROOT)) if out_json.exists() else None,
        "json": parsed,
    }


def append_jsonl(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--smoke-only", action="store_true")
    args = ap.parse_args()

    codesplice_bin, iotrace_dylib, codesplice_src, iotrace_src = build()

    # ---- NON-RECORDED smoke gate (never under raw/) ----
    smoke_dir = WORK / f"smoke_{args.run_id}"
    if smoke_dir.exists():
        import shutil
        shutil.rmtree(smoke_dir)
    smoke_result = run_one_case(codesplice_bin, iotrace_dylib, "baseline_check", smoke_dir, "SMOKE")
    ok = (smoke_result["exit_code"] == 0 and smoke_result["json"] is not None
          and smoke_result["json"].get("baseline_completed") is True
          and smoke_result["json"].get("baseline_bgra") == "4080ffff")
    print(f"SMOKE GATE: {'PASS' if ok else 'FAIL'} -> {smoke_result['json_path']}")
    if not ok:
        print(json.dumps(smoke_result, indent=2, default=str))
        sys.exit(1)
    if args.smoke_only:
        return

    # ---- Official run: never reuse a run id ----
    run_dir = RAW / args.run_id
    if run_dir.exists():
        print(f"REFUSING: raw/{args.run_id} already exists (never reuse a run id)")
        sys.exit(1)
    run_dir.mkdir(parents=True)

    inputs = {
        "run_id": args.run_id,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "codesplice_sha256": sha256_file(codesplice_src),
        "iotrace_sha256": sha256_file(iotrace_src),
        "schema_sha256": sha256_file(ROOT / "schema.py"),
        "casematrix_sha256": sha256_file(ROOT / "casematrix.py"),
        "cases": CASES,
        "case_timeout_sec": CASE_TIMEOUT_SEC,
        "watchdog_sec": WATCHDOG_SEC,
    }
    (run_dir / "00_inputs.json").write_text(json.dumps(inputs, indent=2, sort_keys=True))

    work_run_dir = WORK / args.run_id
    for case in CASES:
        result = run_one_case(codesplice_bin, iotrace_dylib, case, work_run_dir, args.run_id)
        append_jsonl(run_dir / "01_process.jsonl", {
            k: result[k] for k in
            ("tag", "case", "exit_code", "timed_out", "signal", "elapsed_sec",
             "stdout_path", "stderr_path", "json_path")
        })
        if result["json"] is None or "__parse_error__" in result["json"]:
            append_jsonl(run_dir / "02_results.jsonl", {
                "case": case, "__missing_or_unparseable__": True,
                "exit_code": result["exit_code"], "signal": result["signal"],
            })
            print(f"CASE {case}: NO/UNPARSEABLE JSON (exit={result['exit_code']} "
                  f"signal={result['signal']} timed_out={result['timed_out']})")
            continue
        gated, nongated = schema.split_record(result["json"])
        schema.assert_no_address_leak(gated)
        append_jsonl(run_dir / "02_results.jsonl", gated)
        append_jsonl(run_dir / "02_results_addrs.jsonl", nongated)
        print(f"CASE {case}: exit={result['exit_code']} signal={result['signal']} "
              f"post_bgra={gated.get('post_mutation_bgra')} hang={gated.get('post_mutation_hang')}")

    print(f"DONE run_id={args.run_id} -> raw/{args.run_id}/")


if __name__ == "__main__":
    main()
