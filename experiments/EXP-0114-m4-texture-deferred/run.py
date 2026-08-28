#!/usr/bin/env python3
"""EXP-0114 capture runner. Builds the tool binaries, then executes every
case in CAPTURE_CONTRACT.json as its OWN fresh subprocess (one case = one
process, per the standing gate), writing one JSON receipt per case to
raw/<run_id>/case_<id>.json (written+flushed immediately after that case
completes -- never buffered in memory for a batch write at the end, so a
kill mid-run costs at most the in-flight case).

Usage:
  python3 run.py --run-id m4-20260828d-run01 --execute
  python3 run.py --run-id m4-20260828d-run01 --smoke-only   # non-recorded pre-capture gate
"""
import argparse, datetime, json, subprocess, sys, hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit", "stdout", "stderr", "exception"}


def rec(argv, timeout, cwd=None):
    argv = [str(x) for x in argv]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=str(cwd or HERE))
        return {"argv": argv, "cwd": str(cwd or HERE), "timeout_seconds": timeout, "started_utc": started,
                "timed_out": False, "exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        return {"argv": argv, "cwd": str(cwd or HERE), "timeout_seconds": timeout, "started_utc": started,
                "timed_out": True, "exit": None, "stdout": e.stdout or "", "stderr": e.stderr or "", "exception": "TimeoutExpired"}
    except Exception as e:
        return {"argv": argv, "cwd": str(cwd or HERE), "timeout_seconds": timeout, "started_utc": started,
                "timed_out": False, "exit": None, "stdout": "", "stderr": "", "exception": repr(e)}


def sha(p):
    return hashlib.sha256((HERE / p).read_bytes()).hexdigest()


def env_record():
    contract = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    gitrev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    gitdirty = subprocess.run(["git", "status", "--porcelain"], cwd=HERE, capture_output=True, text=True).stdout.strip() != ""
    authored = {p: sha(p) for p in contract["blob_sha256"]}
    authored["CAPTURE_CONTRACT.json"] = sha("CAPTURE_CONTRACT.json")
    return {
        "schema": 1, "git_revision": gitrev, "git_dirty": gitdirty,
        "authored_sha256": authored,
        "sw_vers": rec(["sw_vers"], 5), "xcrun_version": rec(["xcrun", "--version"], 5),
        "device_model": rec(["sysctl", "-n", "hw.model"], 5), "machine": "arm64",
        "boundary": contract["boundary"],
    }


def build(work):
    (work / "bin").mkdir(parents=True, exist_ok=True)
    builds = {}
    builds["shdump"] = rec(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
                             "-o", work / "bin" / "shdump", REPO / "tools/shdump/shdump.m"], 120)
    builds["texsplice"] = rec(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
                                "-o", work / "bin" / "texsplice", HERE / "harness/texsplice.m"], 120)
    builds["gradsplice"] = rec(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
                                 "-o", work / "bin" / "gradsplice", HERE / "harness/gradsplice.m"], 120)
    return builds


def case_argv(work, c):
    return [sys.executable, HERE / "harness/case_runner.py", "--family", c["family"], "--case", c["case"],
            "--work", work, "--args", json.dumps(c["args"], sort_keys=True)]


SMOKE_TIMEOUT = 40


def smoke_gate(work, contract):
    """NON-RECORDED pre-capture smoke gate: run the designated smoke case
    (tex_native) once, verify it produced a well-formed OK result BEFORE
    raw/ is ever created for this run. This invocation is never itself
    written into a byte-compared record."""
    sm = contract["capture"]["pre_capture_smoke"]
    case = next(c for c in contract["cases"] if c["case"] == sm["case"] and c["family"] == sm["family"])
    z = rec(case_argv(work, case), SMOKE_TIMEOUT)
    problems = smoke_problems(z, case)
    return problems, z


def smoke_problems(z, case):
    probs = []
    if z["timed_out"] or z["exception"] is not None or z["exit"] != 0:
        probs.append("smoke case did not exit cleanly: %r" % z)
        return probs
    try:
        p = json.loads(z["stdout"])
    except json.JSONDecodeError:
        return ["smoke stdout not valid JSON"]
    if p.get("status") != "ok":
        probs.append("smoke case status != ok: %r" % p)
    if p.get("out_word_hex") != case["expect"]["out_word_hex"]:
        probs.append("smoke case out_word_hex mismatch: %r" % p)
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--smoke-only", action="store_true")
    args = ap.parse_args()

    contract = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    work = HERE / "work" / args.run_id
    work.mkdir(parents=True, exist_ok=True)

    build_receipts = build(work)
    for name, b in build_receipts.items():
        if b["exit"] != 0:
            print("BUILD FAILED:", name, b["stderr"][-2000:])
            sys.exit(1)

    problems, smoke_rec = smoke_gate(work, contract)
    if problems:
        print("SMOKE GATE FAILED:", problems)
        sys.exit(1)
    print("SMOKE GATE PASS (non-recorded):", smoke_rec["argv"])

    if args.smoke_only:
        return

    if not args.execute:
        print("dry run only; pass --execute to capture")
        return

    raw = HERE / "raw" / args.run_id
    if raw.exists():
        print("REFUSING to reuse an existing run id:", raw)
        sys.exit(1)
    raw.mkdir(parents=True)

    env = env_record()
    (raw / "00_inputs.json").write_text(json.dumps(env, indent=2, sort_keys=True))

    (raw / "01_host_build.json").write_text(json.dumps(build_receipts, indent=2, sort_keys=True))

    order = [c["case"] for c in contract["cases"]]
    run_manifest = {
        "schema": 1, "run_id": args.run_id, "cases": order, "fresh_process_per_case": True,
        "runner_sha256": sha("run.py"), "harness_sha256": sha("harness/case_runner.py"),
        "authored_sha256": env["authored_sha256"], "contract_sha256": sha("CAPTURE_CONTRACT.json"),
    }
    (raw / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, sort_keys=True))

    for c in contract["cases"]:
        argv = case_argv(work, c)
        z = rec(argv, c["timeout_seconds"])
        outpath = raw / f"case_{c['case']}.json"
        outpath.write_text(json.dumps(z, indent=2, sort_keys=True))
        with open(outpath, "r+"):
            pass  # ensure the write above is flushed to disk before moving on
        status = "?"
        try:
            status = json.loads(z["stdout"]).get("status")
        except Exception:
            pass
        print(f"[{args.run_id}] {c['case']:24s} exit={z['exit']} status={status}")

    print("DONE", args.run_id, len(order), "cases")


if __name__ == "__main__":
    main()
