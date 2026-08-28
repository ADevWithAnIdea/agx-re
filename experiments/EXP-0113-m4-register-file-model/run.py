#!/usr/bin/env python3
"""EXP-0113 capture runner. Never touches the GPU without --execute.

Gate sequence (matches CAPTURE_CONTRACT.json): verify.py --selftest,
verify.py --seqtest, then a NON-RECORDED smoke invocation of one case to
work/<run-id>/smoke/ (outside raw/) before the append-only raw/ tree is
created. Any smoke defect is a pre-capture stop (raw/ never created, a
repair remains authorized).

Single-threaded: one case at a time, each harness/case_exec.py invocation a
blocking subprocess under a hard timeout, one fresh process per case. Raw
records are written+flushed+fsync'd immediately (append-only; a case is
never re-run in place). A harness fault (nonzero exit / timeout / OS
exception on case_exec.py itself, as opposed to a GPU-observed STATUS) is a
hard STOP for the run.

Architecture verbatim-adapted from EXP-0099/EXP-0105-m4-.../run.py (same
gate machinery; case matrix and semantics differ, see casematrix.py).
"""
import argparse, datetime, hashlib, json, os, platform, shutil, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402

RUNS = ("m4-20260828-run01", "m4-20260828-run02")
AUTH_CODE = ("isa_helpers.py", "casematrix.py", "harness/build.sh",
             "harness/case_exec.py", "run.py", "verify.py", "analysis.py", "make_manifest.py",
             "baseline.py")
AUTH_KERNELS = ("kernels/carrier.metal", "kernels/loadfwd_carrier.metal",
                 "kernels/carrier_buf1.metal", "kernels/carrier_buf2.metal",
                 "kernels/carrier_buf3.metal")
AUTH_DOC = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "README.md")
BOUNDARY = ("public Metal API only; runtime MSL compile of our own carrier kernels; binary-archive "
            "splice of our own hand-assembled AGX programs (tools/agx-isa assemble()); owned shared "
            "buffers; every case a fresh process; no Apple binary, archive, BO, or command-stream "
            "inspection beyond our own compiled/assembled bytes")
CASE_TIMEOUT = 60
SMOKE_CASE_INDEX = 0


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, o):
    txt = json.dumps(o, indent=2, sort_keys=True) + "\n"
    with open(p, "w") as f:
        n = f.write(txt)
        f.flush()
        os.fsync(f.fileno())
        if n != len(txt):
            raise SystemExit("short write to %s" % p)
    got = Path(p).stat().st_size
    if got != len(txt.encode()):
        raise SystemExit("write verification failed for %s" % p)


def rec(argv, timeout, cwd):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(cwd), text=True,
                            capture_output=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                 "started_utc": started, "timed_out": False, "exit": p.returncode,
                 "stdout": p.stdout, "stderr": p.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                 "started_utc": started, "timed_out": True, "exit": None,
                 "stdout": e.stdout or "", "stderr": e.stderr or "", "exception": "TimeoutExpired"}
    except OSError as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                 "started_utc": started, "timed_out": False, "exit": None,
                 "stdout": "", "stderr": "", "exception": type(e).__name__}


def provenance():
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True,
                          capture_output=True, check=True).stdout.strip()
    return {"git_revision_informational_only": rev,  # NEVER gated on -- pinned revision is recorded
                                                        # in PRE_REGISTRATION.md instead (SUBAGENT_BRIEF.md)
            "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
            "authored_kernel_sha256": {p: sha(HERE / p) for p in AUTH_KERNELS},
            "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC}}


def env_record():
    def envcmd(argv):
        return rec(argv, 5, HERE)
    return {"schema": 1, **provenance(), "sw_vers": envcmd(["sw_vers"]),
            "xcrun_version": envcmd(["xcrun", "--version"]),
            "device_model": envcmd(["sysctl", "-n", "hw.model"]),
            "machine": platform.machine(), "boundary": BOUNDARY}


def env_problems(env):
    bad = []
    for name in ("sw_vers", "xcrun_version", "device_model"):
        z = env[name]
        if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
            bad.append("environment command failed: " + name)
    return bad


def case_argv(run_dir, bin_dir, idx):
    return [sys.executable, "-B", str(HERE / "harness" / "case_exec.py"),
            "--case-index", str(idx), "--run-dir", str(run_dir),
            "--bin-dir", str(bin_dir), "--repo", str(REPO)]


def run_case(run_dir, bin_dir, idx, timeout=CASE_TIMEOUT):
    z = rec(case_argv(run_dir, bin_dir, idx), timeout, HERE)
    if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
        return None, z
    try:
        parsed = json.loads(z["stdout"])
    except ValueError:
        return None, z
    return parsed, z


SMOKE_KEYS = {"i", "name", "group", "carrier", "oracle", "expect_match", "notes", "dispatch", "argv",
              "timed_out", "exception", "exit", "status", "pipeline_source", "out_hex",
              "observed", "match", "stdout", "stderr", "duration_ms"}


def smoke_problems(parsed, receipt):
    bad = []
    if receipt["timed_out"] is not False:
        bad.append("smoke invocation timed out")
    if receipt["exception"] is not None:
        bad.append("smoke OS exception: %s" % receipt["exception"])
    if receipt["exit"] != 0:
        bad.append("smoke exit code %r" % (receipt["exit"],))
    if parsed is None:
        return bad + ["smoke stdout did not parse as one JSON object"]
    missing = SMOKE_KEYS - set(parsed)
    extra = set(parsed) - SMOKE_KEYS
    if missing or extra:
        bad.append("smoke payload key set differs: missing=%s extra=%s" % (sorted(missing), sorted(extra)))
        return bad
    if parsed.get("status") != "OK":
        bad.append("smoke status %r (must be OK before capture begins)" % (parsed.get("status"),))
    if parsed.get("match") is not True:
        bad.append("smoke case did not match its own oracle")
    return bad


def run_gate(args):
    r = subprocess.run(["python3", "-B"] + args, cwd=HERE, timeout=300)
    if r.returncode:
        raise SystemExit("run gate failed: " + " ".join(args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ",".join(RUNS))

    run_gate(["verify.py", "--selftest"])
    run_gate(["verify.py", "--seqtest"])
    if a.run_id == RUNS[1]:
        run_gate(["verify.py", "--between-runs"])
    else:
        run_gate(["verify.py", "--preflight"])

    raw = HERE / "raw" / a.run_id
    work_root = HERE / "work" / a.run_id
    if raw.exists():
        raise SystemExit("append-only raw path already exists")
    if work_root.exists():
        raise SystemExit("scratch path already exists; remove a retained pre-capture stop first")
    work_root.mkdir(parents=True)
    bin_dir = work_root / "bin"

    try:
        env = env_record()
        if env_problems(env):
            put(work_root / "STOP.json", {"schema": 1, "phase": "environment",
                "problems": env_problems(env), "raw_created": False})
            raise SystemExit("pre-capture stop: environment")

        build = rec([str(HERE / "harness" / "build.sh"), str(bin_dir)], 120, HERE)
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None:
            put(work_root / "STOP.json", {"schema": 1, "phase": "host_build",
                "receipt": build, "raw_created": False})
            raise SystemExit("pre-capture stop: host build")

        cs = CM.build_cases()
        smoke_dir = work_root / "smoke"
        smoke_dir.mkdir()
        parsed, receipt = run_case(smoke_dir, bin_dir, SMOKE_CASE_INDEX, timeout=60)
        put(smoke_dir / "smoke_receipt.json", receipt)
        problems = smoke_problems(parsed, receipt)
        if problems:
            put(work_root / "STOP.json", {"schema": 1, "phase": "pre_capture_smoke",
                "problems": problems, "raw_created": False})
            raise SystemExit("pre-capture stop: smoke gate (raw/ not created)")

        raw.mkdir(parents=True)
        put(raw / "00_env.json", env)
        results = []
        timing = []
        with open(raw / "01_results.jsonl", "w") as fres, open(raw / "01_timing.jsonl", "w") as ftim:
            for c in cs:
                parsed, receipt = run_case(work_root, bin_dir, c["i"])
                if parsed is None:
                    put(raw / "STOP.json", {"schema": 1, "phase": "case", "case_index": c["i"],
                        "receipt": receipt})
                    fres.flush(); os.fsync(fres.fileno())
                    ftim.flush(); os.fsync(ftim.fileno())
                    raise SystemExit("hard stop: case %d harness fault" % c["i"])
                gated = {k: parsed[k] for k in ("i", "name", "group", "carrier", "oracle", "expect_match",
                                                  "notes", "dispatch", "status", "pipeline_source",
                                                  "out_hex", "observed", "match")}
                nongated = {"i": parsed["i"], "duration_ms": parsed["duration_ms"],
                            "argv": parsed["argv"], "stdout": parsed["stdout"],
                            "stderr": parsed["stderr"]}
                fres.write(json.dumps(gated, sort_keys=True) + "\n")
                fres.flush(); os.fsync(fres.fileno())
                ftim.write(json.dumps(nongated, sort_keys=True) + "\n")
                ftim.flush(); os.fsync(ftim.fileno())
                results.append(gated)
                timing.append(nongated)
        results_sha256 = hashlib.sha256((raw / "01_results.jsonl").read_bytes()).hexdigest()
        put(raw / "02_dispatch.json", {"schema": 1, "run_id": a.run_id, "n_cases": len(cs),
            "status_counts": {s: sum(1 for r in results if r["status"] == s)
                               for s in set(r["status"] for r in results)},
            "match_counts": {"match": sum(1 for r in results if r["match"]),
                              "mismatch": sum(1 for r in results if not r["match"])},
            "results_sha256": results_sha256,
            "runner_sha256": sha(HERE / "run.py"),
            "casematrix_sha256": sha(HERE / "casematrix.py")})
    finally:
        if not (work_root / "STOP.json").exists():
            shutil.rmtree(work_root, ignore_errors=True)

    print("run %s complete: %d cases, %d matched, %d mismatched" %
          (a.run_id, len(results), sum(1 for r in results if r["match"]),
           sum(1 for r in results if not r["match"])))


if __name__ == "__main__":
    main()
