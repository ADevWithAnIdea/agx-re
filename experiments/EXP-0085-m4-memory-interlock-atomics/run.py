#!/usr/bin/env python3
"""EXP-0085 capture runner.

Builds the three harness binaries once, runs a NON-RECORDED smoke case into
work/ (never promoted to raw/), then executes the frozen 56-case matrix
(casematrix.py), one fresh subprocess per case, hard-timeout each. Writes an
append-only raw/<run-id>/ tree.

Usage:
  python3 -B run.py --execute --run-id <id>
"""
import argparse, datetime, hashlib, json, os, platform, shutil, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import casematrix as CM

TIMEOUTS = {"env_cmd": 10, "build": 60, "case_proc": 45}
CASE_PROC_TIMEOUT = TIMEOUTS["case_proc"]


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_cmd(argv, cwd, timeout):
    t0 = time.time()
    started = utcnow()
    try:
        p = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                            timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "started_utc": started,
                "duration_ms": int((time.time() - t0) * 1000), "exit": p.returncode,
                "timed_out": False, "exception": None, "stdout": p.stdout, "stderr": p.stderr}
    except subprocess.TimeoutExpired as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "started_utc": started,
                "duration_ms": int((time.time() - t0) * 1000), "exit": None, "timed_out": True,
                "exception": str(e), "stdout": e.stdout.decode() if e.stdout else "",
                "stderr": e.stderr.decode() if e.stderr else ""}
    except Exception as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "started_utc": started,
                "duration_ms": int((time.time() - t0) * 1000), "exit": None, "timed_out": False,
                "exception": str(e), "stdout": "", "stderr": ""}


def env_record():
    sw = run_cmd(["sw_vers"], HERE, TIMEOUTS["env_cmd"])
    xc = run_cmd(["xcrun", "--version"], HERE, TIMEOUTS["env_cmd"])
    git_rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                              text=True).stdout.strip()
    git_status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True,
                                 text=True).stdout
    dirty_entries = [l for l in git_status.splitlines() if not l.strip().startswith("??")]
    tree_dirty = subprocess.run(["git", "status", "--porcelain", "--", str(HERE)], cwd=REPO,
                                 capture_output=True, text=True).stdout.splitlines()
    return {
        "schema": "exp0085.inputs.v1",
        "git_revision": git_rev,
        "git_dirty_nonuntracked": dirty_entries,
        "experiment_tree_status": tree_dirty,
        "authored_sha256": CM.authored_sha256(),
        "sw_vers": sw["stdout"],
        "xcrun_version": xc["stdout"],
        "python": sys.version,
        "machine": platform.machine(),
        "timeouts_seconds": TIMEOUTS,
        "matrix_total": CM.TOTAL,
    }


def build_harness(name, src, work):
    out = work / name
    argv = ["xcrun", "clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
            "-O1", "-o", str(out), str(HERE / "harness" / src)]
    rec = run_cmd(argv, HERE, TIMEOUTS["build"])
    ok = (rec["exit"] == 0) and out.exists()
    return ok, rec, out


def run_one_case(binpaths, case, timeout=CASE_PROC_TIMEOUT):
    fam = case["family"]
    if fam == "atomic":
        argv = [binpaths["atomics_probe"], "--source", str(HERE / "kernels" / "atomics.metal"),
                "--kernel", case["kernel"], "--shape", case["shape"], "--dtype", case["dtype"],
                "--n", str(case["n"]), "--addr", case["addr"], "--timeout", str(timeout - 5)]
        if case.get("init"):
            argv += ["--init", case["init"]]
        if case.get("tcount"):
            argv += ["--tcount", str(case["tcount"])]
    elif fam == "ordering_probe":
        argv = [binpaths["atomics_probe"], "--source", str(HERE / "kernels" / "atomics_ordering.metal"),
                "--kernel", case["kernel"], "--shape", "dev_rmw", "--dtype", "u32",
                "--n", str(case["n"]), "--addr", "uniform", "--init", "00000000",
                "--timeout", str(timeout - 5)]
    elif fam == "interlock":
        argv = [binpaths["interlock_probe"], "--source", str(HERE / "kernels" / "interlock.metal"),
                "--kernel", case["kernel"], "--n", str(case["n"]), "--afactor", str(case["afactor"]),
                "--timeout", str(timeout - 5)]
    elif fam == "interlock_tex":
        argv = [binpaths["interlock_tex_probe"], "--source", str(HERE / "kernels" / "interlock_tex.metal"),
                "--kernel", case["kernel"], "--w", str(case["w"]), "--h", str(case["h"]),
                "--timeout", str(timeout - 5)]
    else:
        raise ValueError(fam)

    rec = run_cmd(argv, HERE, timeout)
    parsed = None
    if not rec["timed_out"] and rec["exit"] == 0:
        for line in rec["stdout"].splitlines():
            if line.startswith("JSON "):
                try:
                    parsed = json.loads(line[5:])
                except json.JSONDecodeError:
                    parsed = None
                break
    return rec, parsed


def split_result_and_receipt(case, rec, parsed):
    fam = case["family"]
    keys = CM.RESULT_KEYS_BY_FAMILY[fam]
    result = {k: None for k in keys}
    result["i"] = case["i"]
    result["name"] = case["name"]
    for k in ("kernel", "shape", "dtype", "n", "tcount", "addr", "init", "afactor", "w", "h"):
        if k in case:
            result[k] = case[k]

    gputime_ns = None
    if parsed is None:
        if rec["timed_out"]:
            result["status"] = "proc_timeout"
        else:
            result["status"] = "proc_fail"
        result["err"] = (rec.get("exception") or rec.get("stderr") or "")[:2000]
    else:
        gputime_ns = parsed.pop("gputime_ns", None)
        for k, v in parsed.items():
            if k in result:
                result[k] = v
        if result.get("status") is None:
            result["status"] = "proc_fail"
    # normalize tcount for atomic family (harness computes a default when omitted)
    if fam == "atomic" and result.get("tcount") is None and parsed and "tcount" in parsed:
        result["tcount"] = parsed["tcount"]

    assert set(result.keys()) == keys, (fam, set(result.keys()) ^ keys)

    receipt = {
        "i": case["i"], "name": case["name"], "argv": rec["argv"], "cwd": rec["cwd"],
        "started_utc": rec["started_utc"], "duration_ms": rec["duration_ms"], "exit": rec["exit"],
        "timed_out": rec["timed_out"], "gputime_ns": gputime_ns,
    }
    return result, receipt


def do_smoke(binpaths, work):
    """NON-RECORDED smoke gate (fenced class c): one scratch case, work/ only,
    never promoted into raw/. Must parse cleanly with status ok before any
    raw/ tree is created."""
    smoke_case = {"i": -1, "family": "atomic", "name": "SMOKE_da_add_uniform", "kernel": "da_add",
                  "shape": "dev_rmw", "dtype": "u32", "n": 8, "addr": "uniform", "init": "00000000"}
    rec, parsed = run_one_case(binpaths, smoke_case, timeout=30)
    smoke_path = work / "smoke_receipt.json"
    smoke_path.write_text(json.dumps({"rec": rec, "parsed": parsed}, indent=2))
    ok = (parsed is not None and parsed.get("status") == "ok"
          and parsed.get("target_final_hex") is not None)
    return ok, smoke_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.execute:
        print("refuses to run without --execute"); sys.exit(2)

    # required pre-flight gates
    r = subprocess.run([sys.executable, "-B", str(HERE / "verify.py"), "--selftest"], cwd=HERE)
    if r.returncode != 0:
        print("FAIL: verify.py --selftest"); sys.exit(3)
    r = subprocess.run([sys.executable, "-B", str(HERE / "verify.py"), "--seqtest"], cwd=HERE)
    if r.returncode != 0:
        print("FAIL: verify.py --seqtest"); sys.exit(3)

    raw_dir = HERE / "raw" / args.run_id
    work_dir = HERE / "work" / args.run_id
    if raw_dir.exists():
        print(f"FAIL: raw/{args.run_id} already exists (append-only)"); sys.exit(3)
    work_dir.mkdir(parents=True, exist_ok=True)

    inputs = env_record()
    (work_dir / "00_inputs.json").write_text(json.dumps(inputs, indent=2))

    binpaths, build_recs = {}, {}
    for name, src in (("atomics_probe", "atomics_probe.m"), ("interlock_probe", "interlock_probe.m"),
                       ("interlock_tex_probe", "interlock_tex_probe.m")):
        ok, rec, out = build_harness(name, src, work_dir)
        build_recs[name] = rec
        if not ok:
            (work_dir / "STOP.json").write_text(json.dumps({"stage": "build", "name": name, "rec": rec}, indent=2))
            print(f"FAIL: build {name}"); sys.exit(3)
        binpaths[name] = str(out)
    (work_dir / "02_build.json").write_text(json.dumps(build_recs, indent=2))

    smoke_ok, smoke_path = do_smoke(binpaths, work_dir)
    if not smoke_ok:
        (work_dir / "STOP.json").write_text(json.dumps({"stage": "smoke"}, indent=2))
        print(f"FAIL: smoke gate ({smoke_path})"); sys.exit(3)
    print(f"smoke OK ({smoke_path})")

    # Now safe to create the append-only raw tree.
    raw_dir.mkdir(parents=True)
    (raw_dir / "00_inputs.json").write_text(json.dumps(inputs, indent=2))
    (raw_dir / "01_matrix.json").write_text(json.dumps(CM.MATRIX, indent=2))
    (raw_dir / "02_build.json").write_text(json.dumps(build_recs, indent=2))

    results_f = open(raw_dir / "04_results.jsonl", "w")
    receipts_f = open(raw_dir / "05_receipts.jsonl", "w")
    status_counts = {}
    consecutive_infra_fail = 0
    for case in CM.MATRIX:
        rec, parsed = run_one_case(binpaths, case)
        result, receipt = split_result_and_receipt(case, rec, parsed)
        results_f.write(json.dumps(result, sort_keys=True) + "\n")
        results_f.flush()
        receipts_f.write(json.dumps(receipt, sort_keys=True) + "\n")
        receipts_f.flush()
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
        if result["status"] in ("proc_fail",) and rec.get("exception") and "No such file" in str(rec.get("exception", "")):
            consecutive_infra_fail += 1
        else:
            consecutive_infra_fail = 0
        if consecutive_infra_fail >= 3:
            (raw_dir / "STOP.json").write_text(json.dumps({"stage": "capture", "case_i": case["i"],
                                                             "reason": "3 consecutive spawn failures"}, indent=2))
            print("FAIL: 3 consecutive spawn failures, stopping"); break
        print(f"[{case['i']+1}/{CM.TOTAL}] {case['name']} -> {result['status']}")
    results_f.close()
    receipts_f.close()

    def fsha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    manifest = {
        "schema": "exp0085.run_manifest.v1", "run_id": args.run_id,
        "cases_planned": CM.TOTAL,
        "status_counts": status_counts,
        "results_sha256": fsha(raw_dir / "04_results.jsonl"),
        "receipts_sha256": fsha(raw_dir / "05_receipts.jsonl"),
    }
    (raw_dir / "06_run_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
