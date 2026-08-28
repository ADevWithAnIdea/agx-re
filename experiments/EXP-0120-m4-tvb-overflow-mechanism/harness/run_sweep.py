#!/usr/bin/env python3
"""Official (or smoke) capture driver for EXP-0120.

Usage:
  python3 run_sweep.py --smoke                      # NON-RECORDED dry run -> work/smoke/
  python3 run_sweep.py --run-id m4_20260828_run01    # official capture -> raw/<run-id>/

Every case is its own OS process (run_case.run_case). Records are appended to
raw/<run-id>/records.jsonl with an fflush+fsync after every line, so a kill
mid-sweep loses at most the in-flight case. A run is only "complete" once a
raw/<run-id>/COMPLETE marker is written after every case in the frozen matrix
has a record (used by analysis/verify.py --seqtest).
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from casematrix import load_contract, verify_pins, all_cases, EXP_ROOT, REPO_ROOT
from run_case import run_case

SANITY_MAX_FAILS = 0  # any sanity-check failure after a Sweep D case halts the run


def git_rev(repo_root):
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root,
                              capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except Exception as e:
        return f"UNKNOWN ({e})"


def append_progress(msg):
    path = os.path.join(EXP_ROOT, "PROGRESS.md")
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "a") as f:
        f.write(f"- {ts} {msg}\n")
        f.flush()
        os.fsync(f.fileno())


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true")
    g.add_argument("--run-id")
    args = ap.parse_args()

    contract = load_contract()
    problems = verify_pins(contract)
    if problems:
        print("PIN VERIFICATION FAILED, aborting:", file=sys.stderr)
        for p in problems:
            print(" -", p, file=sys.stderr)
        sys.exit(1)

    cases, sanity_case = all_cases(contract)

    if args.smoke:
        out_root = os.path.join(EXP_ROOT, "work", "smoke")
        os.makedirs(out_root, exist_ok=True)
        # smoke only needs to prove the harness works end-to-end; run a small
        # representative subset (not the full 57+ cases) to keep it fast.
        subset = [c for c in cases if c["sweep"] in ("A", "B", "C")][:3] + \
                 [c for c in cases if c["sweep"] == "D"][:1]
        run_id = "smoke"
        print(f"SMOKE (non-recorded): {len(subset)} representative cases -> {out_root}")
    else:
        subset = cases
        run_id = args.run_id
        out_root = os.path.join(EXP_ROOT, "raw", run_id)
        if os.path.exists(out_root):
            print(f"REFUSING: {out_root} already exists (run ids are never reused).", file=sys.stderr)
            sys.exit(1)
        os.makedirs(out_root)

    manifest = {
        "run_id": run_id,
        "smoke": args.smoke,
        "started_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pinned_repo_head": contract["pinned_repo_head"],
        "live_repo_head_at_run_time": git_rev(REPO_ROOT),
        "n_cases": len(subset),
        "contract_frozen_at_utc": contract["frozen_at_utc"],
    }
    with open(os.path.join(out_root, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    records_path = os.path.join(out_root, "records.jsonl")
    rf = open(records_path, "a")

    def emit(record):
        rf.write(json.dumps(record) + "\n")
        rf.flush()
        os.fsync(rf.fileno())

    n_ok, n_timeout, n_fault = 0, 0, 0
    last_sweep = None
    for i, case in enumerate(subset):
        case_dir = os.path.join(out_root, "cases", case["case_id"])
        t0 = time.time()
        rec = run_case(case, case_dir)
        emit(rec)
        dt = time.time() - t0
        status = "TIMEOUT" if rec["timed_out"] else ("OK" if rec["returncode"] == 0 else f"rc={rec['returncode']}")
        if rec["timed_out"]:
            n_timeout += 1
        elif rec["returncode"] == 0:
            n_ok += 1
        else:
            n_fault += 1
        print(f"[{i+1}/{len(subset)}] {case['case_id']:24s} {status:10s} {dt:7.3f}s")

        if case["sweep"] != last_sweep:
            if not args.smoke:
                append_progress(f"run={run_id} sweep={case['sweep']} started (case {case['case_id']})")
            last_sweep = case["sweep"]

        if case["sweep"] == "D" and case["role"] == "limits":
            sdir = os.path.join(out_root, "cases", f"{case['case_id']}-sanity")
            srec = run_case(sanity_case, sdir)
            srec["case_id"] = f"{case['case_id']}-sanity"
            emit(srec)
            ok = (not srec["timed_out"]) and srec["returncode"] == 0 and "exact=1" in " ".join(srec["stdout_tail"])
            print(f"    sanity-check after {case['case_id']}: {'OK' if ok else 'FAIL'}")
            if not ok:
                print("SANITY CHECK FAILED after a Sweep D stress case -- halting run, marking BLOCKED.",
                      file=sys.stderr)
                if not args.smoke:
                    append_progress(f"run={run_id} BLOCKED: sanity check failed after {case['case_id']}")
                rf.close()
                with open(os.path.join(out_root, "BLOCKED.md"), "w") as f:
                    f.write(f"Sanity check failed after {case['case_id']}. See records.jsonl.\n")
                sys.exit(2)

    rf.close()
    summary = {"n_ok": n_ok, "n_timeout": n_timeout, "n_fault": n_fault, "n_total": len(subset)}
    with open(os.path.join(out_root, "SUMMARY.json"), "w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    if not args.smoke:
        # COMPLETE marker: only written once every frozen-matrix case has a record.
        with open(os.path.join(out_root, "COMPLETE"), "w") as f:
            f.write(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")
        append_progress(f"run={run_id} COMPLETE n_ok={n_ok} n_timeout={n_timeout} n_fault={n_fault}")

    print("DONE", summary)


if __name__ == "__main__":
    main()
