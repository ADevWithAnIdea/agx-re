#!/usr/bin/env python3
"""EXP-0130 capture driver.

Runs the full casematrix.py matrix once (behavioral records, one process per
case via harness/render_eot) plus a fixed set of structural byte-extraction
records (harness/shdump + harness/agxparse.py on our own compiled kernels),
appending each record to raw/<run_id>/records.jsonl with an immediate
fflush+fsync after every record (a kill costs at most one record).

Usage:
    python3 run.py --run-id <id> --out-root work/smoke   (NON-RECORDED smoke)
    python3 run.py --run-id <id> --out-root ../raw         (official capture)

Refuses to reuse/overwrite an existing run directory (CODEX: never reuse a
run id). Hard per-process timeout via subprocess.run(timeout=...).
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import casematrix  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_EOT = os.path.join(HERE, "render_eot")
SHDUMP = os.path.join(HERE, "shdump")
AGXPARSE = os.path.join(HERE, "agxparse.py")
KERNEL = os.path.join(HERE, "..", "kernels", "eot_construct.metal")

CASE_TIMEOUT_S = 20
BUILD_TIMEOUT_S = 30

STRUCTURAL_FUNCS = ["f_eot_evict", "f_eot_ctrl", "f_eot_combine"]


def append_record(fp, rec):
    fp.write(json.dumps(rec, sort_keys=True) + "\n")
    fp.flush()
    os.fsync(fp.fileno())


def run_behavioral_case(mode, case_id, dst, k_or_src):
    args = [
        RENDER_EOT, "--source", KERNEL, "--mode", mode, "--case", case_id,
        "--dr", repr(dst[0]), "--dg", repr(dst[1]), "--db", repr(dst[2]), "--da", repr(dst[3]),
        "--kr", repr(k_or_src[0]), "--kg", repr(k_or_src[1]), "--kb", repr(k_or_src[2]), "--ka", repr(k_or_src[3]),
    ]
    t0 = time.monotonic()
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=CASE_TIMEOUT_S)
        dt = time.monotonic() - t0
        rec = {
            "kind": "behavioral", "mode": mode, "case_id": case_id,
            "returncode": r.returncode, "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip()[:4000], "wall_s": round(dt, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        dt = time.monotonic() - t0
        rec = {
            "kind": "behavioral", "mode": mode, "case_id": case_id,
            "returncode": None, "stdout": "", "stderr": "TIMEOUT",
            "wall_s": round(dt, 3), "timed_out": True,
        }
    return rec


def run_structural_case(func_name, work_dir):
    archive = os.path.join(work_dir, f"{func_name}.bin")
    build_args = [SHDUMP, "-o", archive, "--render", "--vertex", "v_full",
                  "--fragment", func_name, KERNEL]
    try:
        rb = subprocess.run(build_args, capture_output=True, text=True, timeout=BUILD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"kind": "structural", "function": func_name, "build_ok": False,
                "build_error": "TIMEOUT", "hex": None}
    if rb.returncode != 0:
        return {"kind": "structural", "function": func_name, "build_ok": False,
                "build_error": rb.stderr.strip()[:2000], "hex": None}
    extract_args = ["python3", AGXPARSE, archive, "--stage", "fragment", "--extract-hex"]
    try:
        re_ = subprocess.run(extract_args, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return {"kind": "structural", "function": func_name, "build_ok": True,
                "build_error": None, "hex": None, "extract_error": "TIMEOUT"}
    hexstr = re_.stdout.strip()
    return {
        "kind": "structural", "function": func_name, "build_ok": True,
        "build_error": None, "extract_returncode": re_.returncode,
        "hex": hexstr, "hex_len_bytes": len(hexstr) // 2,
        "contains_tile_read": "670e54" in hexstr,
        "contains_frag_color_store": "e70654" in hexstr,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-root", required=True, help="directory that will contain <run_id>/")
    args = ap.parse_args()

    run_dir = os.path.join(args.out_root, args.run_id)
    if os.path.exists(run_dir):
        print(f"REFUSING: run dir already exists: {run_dir}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(run_dir)
    # Transient compiled-archive scratch space MUST live outside raw/: those
    # .bin files are Metal binary archive containers (MetalLib), and raw/ is
    # append-only text-log/JSON evidence only (SUBAGENT_BRIEF.md: "never
    # binary archives, .metallib, or Apple blobs" -- authorship does not
    # matter, only file type). Only the extracted hex (already text, written
    # into records.jsonl by run_structural_case) is evidence; the archives
    # themselves are disposable build intermediates.
    work_dir = os.path.join(HERE, "..", "work", "build_scratch", args.run_id)
    os.makedirs(work_dir, exist_ok=True)

    records_path = os.path.join(run_dir, "records.jsonl")
    n_ok = n_fail = n_timeout = 0
    with open(records_path, "a") as fp:
        # Structural records first (static properties of the compiled kernel).
        for func_name in STRUCTURAL_FUNCS:
            rec = run_structural_case(func_name, work_dir)
            append_record(fp, rec)
            if rec.get("build_ok"):
                n_ok += 1
            else:
                n_fail += 1

        # Behavioral records.
        for mode, case_id, dst, k_or_src, expected in casematrix.all_cases():
            rec = run_behavioral_case(mode, case_id, dst, k_or_src)
            rec["expected"] = list(expected)
            append_record(fp, rec)
            if rec["timed_out"]:
                n_timeout += 1
            elif rec["returncode"] == 0:
                n_ok += 1
            else:
                n_fail += 1

    print(f"run {args.run_id}: ok={n_ok} fail={n_fail} timeout={n_timeout} -> {records_path}")


if __name__ == "__main__":
    main()
