#!/usr/bin/env python3
"""EXP-0141 capture runner. Never touches the GPU without --execute.

Gate sequence (CAPTURE_CONTRACT.json): verify.py --selftest, then --preflight
(run01) or --between-runs (run02), then an environment record, then a host
build of our own read-only tool sources, then the append-only capture.

raw/<run_id>/ is created only after every pre-capture gate passes; a defect
before that point leaves raw/ untouched and a repair authorized.
"""
import argparse, datetime, hashlib, json, os, platform, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = ("m4-20260828-run11", "m4-20260828-run12")
ADDENDUM_RUNS = ("m4-20260828-run21", "m4-20260828-run22")
BOUNDARY = ("public Metal API only; runtime MSL compile of our own carrier kernels; "
            "binary-archive splice of our own hand-assembled AGX programs "
            "(tools/agx-isa assemble()) and of our own compiled carriers; owned "
            "shared buffers; no Apple binary, archive, BO or command-stream "
            "inspection beyond our own compiled/assembled bytes")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rec(argv, timeout, cwd):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(cwd), text=True,
                           capture_output=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "started_utc": started,
                "timed_out": False, "exit": p.returncode,
                "stdout": p.stdout[-4000:], "stderr": p.stderr[-4000:], "exception": None}
    except subprocess.TimeoutExpired as e:
        return {"argv": [str(x) for x in argv], "started_utc": started, "timed_out": True,
                "exit": None, "stdout": (e.stdout or "")[-2000:] if isinstance(e.stdout, str) else "",
                "stderr": "", "exception": "TimeoutExpired"}


def env_record():
    cc = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    return {"schema": 1,
            "git_revision_informational_only":
                subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True,
                               capture_output=True).stdout.strip(),
            "repo_revision_pinned_at_preregistration":
                cc["repo_revision_recorded_not_gated"],
            "authored_sha256": {p: sha(HERE / p) for p in cc["authored_sha256"]},
            "tool_sha256": {p: sha(REPO / p) for p in cc["tool_sha256"]},
            "sw_vers": rec(["sw_vers"], 10, HERE),
            "hw_model": rec(["sysctl", "-n", "hw.model"], 10, HERE),
            "xcrun_version": rec(["xcrun", "--version"], 10, HERE),
            "machine": platform.machine(), "boundary": BOUNDARY,
            "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}


def gate(args):
    r = subprocess.run([sys.executable, "-B", "verify.py"] + args, cwd=HERE, timeout=600)
    if r.returncode:
        raise SystemExit("GATE FAILED: verify.py " + " ".join(args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation without --execute")
    if a.run_id not in RUNS + ADDENDUM_RUNS:
        raise SystemExit("run-id must be one of: " + ",".join(RUNS + ADDENDUM_RUNS))
    addendum = a.run_id in ADDENDUM_RUNS

    gate(["--selftest"])
    gate(["--preflight"])
    if a.run_id == RUNS[1]:
        gate(["--between-runs"])

    raw = HERE / "raw" / a.run_id
    if raw.exists():
        raise SystemExit("append-only raw path already exists: " + str(raw))
    work = HERE / "work" / a.run_id
    if work.exists():
        raise SystemExit("scratch path already exists; retain the stop first")
    work.mkdir(parents=True)
    bin_dir = work / "bin"

    build = rec([str(HERE / "harness" / "build.sh"), str(bin_dir)], 300, HERE)
    if build["exit"] != 0:
        (work / "STOP.json").write_text(json.dumps({"phase": "host_build", "receipt": build}, indent=1))
        raise SystemExit("pre-capture stop: host build")

    raw.mkdir(parents=True)
    env = env_record()
    (raw / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True) + "\n")
    (raw / "00_build.json").write_text(json.dumps(build, indent=1, sort_keys=True) + "\n")

    r = subprocess.run([sys.executable, "-B", str(HERE / "harness" / "sweeprun.py"),
                        "--run-id", a.run_id, "--bin-dir", str(bin_dir),
                        "--work", str(work), "--raw", str(raw)]
                       + (["--addendum"] if addendum else []),
                       cwd=HERE, timeout=7200)
    if r.returncode:
        raise SystemExit("sweep executor exited %d (raw/ retained)" % r.returncode)
    n = sum(1 for _ in (raw / "sweep.jsonl").open())
    (raw / "02_dispatch.json").write_text(json.dumps(
        {"run_id": a.run_id, "records": n,
         "sweep_sha256": sha(raw / "sweep.jsonl"),
         "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()},
        indent=1, sort_keys=True) + "\n")
    print("run %s complete: %d records" % (a.run_id, n))


if __name__ == "__main__":
    main()
