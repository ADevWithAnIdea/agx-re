#!/usr/bin/env python3
"""EXP-0121 capture orchestrator. Runs the gated two-run capture:
  1. --selftest, --seqtest (pure Python, no GPU)
  2. build tools fresh into work/<run>/bin
  3. NON-RECORDED smoke gate (--preflight for run01, --between-runs for run02)
  4. all 94 cases, ONE fresh subprocess per case, appended+fflushed to
     raw/<run-id>/01_results.jsonl (GATED), 01_detail.jsonl (NON-GATED --
     concurrency per-lane counts, full observed arrays, raw hex live here),
     01_timing.jsonl (non-gated) as each completes.
  5. 00_env.json, 02_dispatch.json summary.

Usage: python3 -B run.py --run-id m4-<UTC-timestamp>-run01 [--between-runs]
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "harness"))
import casematrix as CM  # noqa: E402
import verify as V  # noqa: E402


def sh(cmd, **kw):
    return subprocess.run(cmd, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--repo", default=str(HERE.parent.parent))
    ap.add_argument("--case-timeout", type=float, default=45.0)
    ap.add_argument("--between-runs", action="store_true")
    ap.add_argument("--start-index", type=int, default=0)
    a = ap.parse_args()

    run_dir = HERE / "raw" / a.run_id
    if run_dir.exists() and any(run_dir.iterdir()) and a.start_index == 0:
        print(f"REFUSING: {run_dir} already exists and is non-empty; run ids are never reused.")
        sys.exit(1)
    run_dir.mkdir(parents=True, exist_ok=True)
    bin_dir = HERE / "work" / a.run_id / "bin"
    case_work_dir = HERE / "work" / a.run_id / "cases"
    case_work_dir.mkdir(parents=True, exist_ok=True)

    def progress(msg):
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        line = f"- {ts} [{a.run_id}] {msg}\n"
        with open(HERE / "PROGRESS.md", "a") as f:
            f.write(line)
            f.flush()
        print(line, end="")

    if not V.run_selftest(verbose=False):
        (run_dir / "STOP.json").write_text(json.dumps({"reason": "selftest failed"}))
        progress("STOP: --selftest failed pre-capture")
        sys.exit(1)
    progress("selftest PASS")
    ok, phase = V.run_seqtest(str(HERE), verbose=False)
    progress(f"seqtest phase={phase}")

    r = sh(["sh", str(HERE / "harness" / "build.sh"), str(bin_dir)],
           capture_output=True, text=True)
    if r.returncode != 0:
        (run_dir / "STOP.json").write_text(json.dumps({"reason": "build failed", "stderr": r.stderr}))
        progress("STOP: harness/build.sh failed: " + r.stderr[-500:])
        sys.exit(1)
    progress(f"built tools into {bin_dir}")

    smoke_ok = V.run_smoke(str(bin_dir), a.repo, verbose=False,
                            work_dir=str(HERE / "work" / a.run_id / "smoke_scratch"))
    progress(f"{'between-runs' if a.between_runs else 'preflight'} smoke gate: {'PASS' if smoke_ok else 'FAIL'}")
    if not smoke_ok:
        (run_dir / "STOP.json").write_text(json.dumps({"reason": "smoke gate failed"}))
        sys.exit(1)

    git_head = subprocess.run(["git", "-C", a.repo, "rev-parse", "HEAD"],
                               capture_output=True, text=True).stdout.strip()
    git_dirty = bool(subprocess.run(["git", "-C", a.repo, "status", "--porcelain"],
                                     capture_output=True, text=True).stdout.strip())
    macos = subprocess.run(["sw_vers"], capture_output=True, text=True).stdout.strip()
    env = {
        "run_id": a.run_id, "host": platform.node(), "macos_sw_vers": macos,
        "python": sys.version, "git_head_at_capture_start": git_head,
        "git_dirty_at_capture_start": git_dirty,
        "note": "git_head_at_capture_start is INFORMATIONAL ONLY -- pinned_revision in "
                "CAPTURE_CONTRACT.json is what gates validity (SUBAGENT_BRIEF.md); this repo "
                "tree is dirty from SIBLING experiments' untracked directories, not this one's "
                "own tracked inputs.",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (run_dir / "00_env.json").write_text(json.dumps(env, indent=2, sort_keys=True))

    cases = CM.build_cases()
    for i, c in enumerate(cases):
        c["_i"] = i

    results_path = run_dir / "01_results.jsonl"
    detail_path = run_dir / "01_detail.jsonl"
    timing_path = run_dir / "01_timing.jsonl"
    rf = open(results_path, "a")
    df = open(detail_path, "a")
    tf = open(timing_path, "a")
    status_counts = {}
    for i in range(a.start_index, len(cases)):
        c = cases[i]
        argv = [sys.executable, "-B", str(HERE / "harness" / "case_exec.py"),
                "--case-index", str(i), "--run-dir", str(run_dir),
                "--bin-dir", str(bin_dir), "--repo", a.repo,
                "--work-dir", str(case_work_dir), "--case-timeout", str(a.case_timeout)]
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=a.case_timeout + 30)
            out_line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else None
            payload = json.loads(out_line) if out_line else None
            harness_err = None if payload else (r.stderr[-2000:] or "no stdout")
        except subprocess.TimeoutExpired:
            payload, harness_err = None, "HARNESS_TIMEOUT"
        except Exception as e:  # noqa: BLE001
            payload, harness_err = None, f"HARNESS_EXC {e}"

        if payload is None:
            record = {"id": c["id"], "item": c["item"], "kind": c["kind"], "status": "HARNESS_ERROR"}
            detail = {"id": c["id"], "error": harness_err}
            timing = {"id": c["id"], "duration_ms": None, "error": harness_err}
        else:
            record, detail, timing = payload["record"], payload["detail"], payload["timing"]

        rf.write(json.dumps(record, sort_keys=True) + "\n")
        rf.flush()
        df.write(json.dumps(detail, sort_keys=True) + "\n")
        df.flush()
        tf.write(json.dumps(timing, sort_keys=True) + "\n")
        tf.flush()
        status_counts[record.get("status")] = status_counts.get(record.get("status"), 0) + 1
        if (i + 1) % 10 == 0 or i == len(cases) - 1:
            progress(f"case {i+1}/{len(cases)} id={record.get('id')} status={record.get('status')}")
    rf.close()
    df.close()
    tf.close()

    results_sha256 = hashlib.sha256(results_path.read_bytes()).hexdigest()
    dispatch = {
        "run_id": a.run_id, "n_cases": len(cases), "status_counts": status_counts,
        "results_sha256": results_sha256,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (run_dir / "02_dispatch.json").write_text(json.dumps(dispatch, indent=2, sort_keys=True))
    progress(f"CAPTURE COMPLETE: {len(cases)} cases, status_counts={status_counts}, "
             f"results_sha256={results_sha256[:16]}...")

    ok, fails = V.check_captured(str(run_dir))
    progress(f"post-capture --captured check: {'PASS' if ok else 'FAIL: ' + str(fails[:10])}")


if __name__ == "__main__":
    main()
