#!/usr/bin/env python3
"""EXP-0092 capture runner. Never runs a device operation without --execute.

Four backends, one case matrix (casematrix.py), one gated record shape:
  srsweep / dstsweep    -- splice OUR OWN compiled kernel bytes (re-assembled
                            with tools/agx-isa) via tools/agxtest/agxtest.py,
                            executed by tools/agxtest/agxrun in a FRESH process
                            on the local M4 under a hard timeout.
  drawparam              -- our own harness/agxvdraw (built from source each
                            run; no splice) issues one indexed/instanced draw
                            with controlled parameters and reads back the
                            vertex-shader-recorded (vid,iid,bv,bi) tuples.
  numworkgroups           -- our own harness/agxcdispatch (built from source
                            each run; no splice) issues one direct-3D or
                            indirect compute dispatch and reads back
                            threadgroups_per_grid.

A fault, hang, timeout, or mismatch is a RESULT: recorded, and the sweep
continues in a fresh process; nothing is retried in place.

Two records per case, split per the standing NO-NONDETERMINISM gate:
  04_results.jsonl      -- GATED (byte/JSON-comparable across runs): case
                            identity, params, splice, status, observed,
                            expected, VERDICT. Contains NO timing field.
  04_results_raw.jsonl  -- NOT gated: full subprocess receipt, timing included.

Execution is single-threaded and synchronous: one case at a time, each
sub-process is a blocking call in its OWN fresh process, and every raw record
line is flushed to disk before the next case starts.
"""
import argparse, datetime, hashlib, json, platform, shutil, struct, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0092-m4-sysval-abi"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import casematrix as CM   # noqa: E402

# NOTE: "m4-20260828-run01" (without the "b") is QUARANTINED -- a first attempt
# hit an own-code bug (parse_lines() dict-init KeyError, fixed below) mid-sweep
# and was retained untouched as process history; see QUARANTINE-run01-attempt1.md.
# This is the fresh, fully-closed run-id pair for the real capture.
RUNS = ("m4-20260828b-run01", "m4-20260828b-run02")

BOUNDARY = ("public Metal API only; runtime MSL compile of our own kernels; binary-archive "
           "splice of our own compiled shader bytes re-assembled with tools/agx-isa "
           "(srsweep/dstsweep only); two own-built harness binaries (agxvdraw, agxcdispatch) "
           "compiling our own MSL with no splice for drawparam/numworkgroups; owned shared "
           "buffers; every case a fresh process; no Apple binary, archive, BO or command-stream "
           "inspection beyond our own compiled shader bytes")

TIMEOUTS = {"env_command": 10, "host_build": 60, "baseline": 60,
           "case_process": 60, "smoke_process": 60}

AUTH_CODE = tuple(f"kernels/{k}.metal" for k in CM.KERNELS) + (
    "harness/build.sh", "harness/agxvdraw.m", "harness/agxcdispatch.m",
    "baseline.py", "casematrix.py", "run.py", "analysis.py", "make_manifest.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")

# authoritative record key sets (imported by verify.py; never restated there)
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
           "stdout", "stderr", "exception"}
DISPATCH_KEYS = {"argv", "cwd", "started_utc", "finished_utc", "duration_seconds",
                 "n_cases", "status_counts", "verdict_counts", "results_sha256",
                 "results_lines"}
# GATED (04_results.jsonl) -- must never contain a timing/duration/pid/address field.
CASE_KEYS = {"i", "backend", "kernel", "case_name", "item", "rep", "params",
            "splice_args", "changed_bytes", "status", "pipeline_source",
            "observed", "expected", "verdict"}
# NOT gated (04_results_raw.jsonl) -- full receipt including timing.
CASE_RAW_KEYS = {"i", "duration_ms", "exit", "timed_out", "exception", "stdout", "stderr"}

STATUS_ALLOWED = {"OK", "COMPILE_FAIL", "FUNCTION_MISSING", "ARCHIVE_FAIL",
                  "PIPELINE_MISS", "PIPELINE_FAIL", "CMDBUF_ERROR", "HANG", "NO_STATUS"}
VERDICT_ALLOWED = {"MATCH_EXPECTED", "MISMATCH_EXPECTED", "OBSERVED_NO_ORACLE", "FAULT"}

SMOKE_CASE = {"backend": "drawparam", "case_name": "smoke_baseline", "item": "SMOKE",
             "note": "non-recorded scratch case (shape only)"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def rec(argv, timeout, cwd):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(cwd), text=True,
                           capture_output=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": True, "exit": None,
                "stdout": out, "stderr": err, "exception": "TimeoutExpired"}
    except OSError as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": None,
                "stdout": "", "stderr": "", "exception": type(e).__name__}


def provenance():
    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, text=True, capture_output=True,
                              check=True).stdout
    exp = git("status", "--porcelain", "--", EXP_REL)
    return {
        "git_revision": git("rev-parse", "HEAD").strip(),
        "git_dirty": git("status", "--porcelain").strip() != "",
        "experiment_tree_dirty_entries": len([l for l in exp.splitlines() if l.strip()]),
        "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
        "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC},
    }


def parse_lines(stdout, prefixes):
    out = {k: None for k in prefixes.values()}
    for line in stdout.splitlines():
        for pfx, key in prefixes.items():
            if line.startswith(pfx):
                out[key] = line[len(pfx):].strip()
    return out


def compute_verdict(status, observed, expected):
    if status != "OK":
        return "FAULT"
    if expected is None:
        return "OBSERVED_NO_ORACLE"
    return "MATCH_EXPECTED" if observed == expected else "MISMATCH_EXPECTED"


# --- backend: srsweep / dstsweep (splice via tools/agxtest/agxtest.py) -----
def _agxtest_argv(shared, kernel, grid, tg, out_idx, out_n, splice_args, timeout):
    src = HERE / "kernels" / f"{kernel}.metal"
    return [sys.executable, "-B", str(REPO / "tools" / "agxtest" / "agxtest.py"),
           "--source", src, "--function", "k", "--grid", str(grid), "--tg", str(tg),
           "--no-fast-math", "--int",
           "--shdump", shared / "bin" / "shdump", "--agxrun", shared / "bin" / "agxrun",
           "--agxparse", REPO / "tools" / "shdump" / "agxparse.py",
           "--workdir", shared / kernel, "--run-timeout", timeout,
           "--out", f"{out_idx}={out_n}"] + [a for sp in splice_args for a in ("--splice", sp)]


def run_splice_case(shared, case, timeout):
    kernel = case["kernel"]
    splice_args = case["_splice_args"]
    if kernel == "srprobe":
        grid, tg, out_n = CM.SRSWEEP_N, CM.SRSWEEP_N, CM.SRSWEEP_N
    else:
        grid, tg, out_n = 1, 1, CM.DSTSWEEP_OUT_N
    argv = _agxtest_argv(shared, kernel, grid, tg, 0, out_n, splice_args, timeout)
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_lines(r["stdout"], {"STATUS ": "status", "PIPELINE_SOURCE": "pipeline_source",
                                       "RESULT 0 ": "result"})
    status = parsed["status"] or "NO_STATUS"
    observed = [int(x) for x in parsed["result"].split()] if parsed["result"] else None
    if r["timed_out"] or r["exception"] is not None:
        status = "HANG" if r["timed_out"] else status
    verdict = compute_verdict(status, observed, case["expected"])
    gated = {"backend": case["backend"], "kernel": kernel, "case_name": case["name"],
            "item": case["item"], "rep": case["rep"], "params": case["params"],
            "splice_args": splice_args,
            "changed_bytes": [off for off, _ in case["splice_changes"]],
            "status": status, "pipeline_source": parsed["pipeline_source"],
            "observed": observed, "expected": case["expected"], "verdict": verdict}
    raw = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
          "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, raw


# --- backend: drawparam (harness/agxvdraw, own compile, no splice) --------
def run_drawparam_case(shared, case, timeout):
    p = case["params"]
    argv = [shared / "bin" / "agxvdraw",
           "--source", HERE / "kernels" / "vdraw_probe.metal",
           "--vertex", "v_main", "--fragment", "f_main",
           "--indices", ",".join(str(x) for x in p["indices"]),
           "--instance-count", str(p["instance_count"]),
           "--base-vertex", str(p["base_vertex"]),
           "--base-instance", str(p["base_instance"]),
           "--primitive", p["primitive"], "--max-records", "4096"]
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    status = "NO_STATUS"
    recs = []
    for line in r["stdout"].splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("REC "):
            toks = line.split()
            vid = int(toks[2].split("=")[1]); iid = int(toks[3].split("=")[1])
            bv = int(toks[4].split("=")[1]); bi = int(toks[5].split("=")[1])
            recs.append((vid, iid, bv, bi))
    if r["timed_out"] or r["exception"] is not None:
        status = "HANG" if r["timed_out"] else status
    observed = sorted(recs) if status == "OK" else None
    verdict = compute_verdict(status, observed, case["expected"])
    gated = {"backend": case["backend"], "kernel": case["kernel"], "case_name": case["name"],
            "item": case["item"], "rep": case["rep"], "params": p, "splice_args": [],
            "changed_bytes": [], "status": status, "pipeline_source": None,
            "observed": [list(x) for x in observed] if observed is not None else None,
            "expected": [list(x) for x in case["expected"]] if case["expected"] is not None else None,
            "verdict": verdict}
    raw = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
          "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, raw


# --- backend: numworkgroups (harness/agxcdispatch, own compile, no splice) -
def run_numworkgroups_case(shared, case, timeout):
    p = case["params"]
    argv = [shared / "bin" / "agxcdispatch",
           "--source", HERE / "kernels" / "numwg_probe.metal", "--function", "k",
           "--mode", p["mode"], "--out-elems", "3",
           "--local-x", str(p["local"][0]), "--local-y", str(p["local"][1]),
           "--local-z", str(p["local"][2])]
    if p["mode"] == "direct":
        argv += ["--tg-x", str(p["tg"][0]), "--tg-y", str(p["tg"][1]), "--tg-z", str(p["tg"][2])]
    else:
        argv += ["--indirect-x", str(p["ind"][0]), "--indirect-y", str(p["ind"][1]),
                "--indirect-z", str(p["ind"][2])]
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_lines(r["stdout"], {"STATUS ": "status", "OUT ": "out_hex"})
    status = parsed["status"] or "NO_STATUS"
    observed = None
    if parsed["out_hex"]:
        b = bytes.fromhex(parsed["out_hex"])
        observed = list(struct.unpack_from("<3I", b, 0))
    if r["timed_out"] or r["exception"] is not None:
        status = "HANG" if r["timed_out"] else status
    verdict = compute_verdict(status, observed, case["expected"])
    gated = {"backend": case["backend"], "kernel": case["kernel"], "case_name": case["name"],
            "item": case["item"], "rep": case["rep"], "params": p, "splice_args": [],
            "changed_bytes": [], "status": status, "pipeline_source": None,
            "observed": observed, "expected": case["expected"], "verdict": verdict}
    raw = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
          "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, raw


BACKEND_RUNNERS = {"srsweep": run_splice_case, "dstsweep": run_splice_case,
                   "drawparam": run_drawparam_case, "numworkgroups": run_numworkgroups_case}


def run_one_case(shared, case, timeout):
    case = dict(case)
    case["_splice_args"] = CM.splice_args_from_bytes(case.get("splice_changes", []))
    return BACKEND_RUNNERS[case["backend"]](shared, case, timeout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved "
                         "pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ", ".join(RUNS))
    for gate in ("--selftest", "--seqtest"):
        if subprocess.run([sys.executable, "-B", "verify.py", gate], cwd=HERE).returncode:
            raise SystemExit("verify.py %s failed: no capture is authorized" % gate)
    gate = "--preflight" if a.run_id == RUNS[0] else "--between-runs"
    if subprocess.run([sys.executable, "-B", "verify.py", gate], cwd=HERE).returncode:
        raise SystemExit("run gate failed")
    current = provenance()
    if a.run_id == RUNS[1]:
        first = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        for k in ("authored_code_sha256", "authored_doc_sha256"):
            if first.get(k) != current[k]:
                raise SystemExit("run02 provenance differs from closed run01: " + k)

    raw = HERE / "raw" / a.run_id
    work = HERE / "work" / a.run_id
    if raw.exists() or work.exists():
        raise SystemExit("append-only path already exists")
    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    try:
        # --- PHASE 1 (pre-raw): build, baseline, NON-RECORDED smoke gate. ------
        shared = work / "shared"
        bin_dir = shared / "bin"
        shared.mkdir(parents=True)
        build = rec([HERE / "harness" / "build.sh", bin_dir], TIMEOUTS["host_build"], HERE)
        base = rec([sys.executable, "-B", "baseline.py", "--out", work / "baseline.json"],
                  TIMEOUTS["baseline"], HERE)
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None \
                or base["timed_out"] or base["exit"] != 0 or base["exception"] is not None:
            print(json.dumps({"pre_capture_stop": "host_build",
                              "harness_build": build, "baseline": base}, indent=2))
            raise SystemExit(3)
        derivation = json.loads((work / "baseline.json").read_text())
        if derivation["frozen_anchor_diffs"]:
            print(json.dumps({"pre_capture_stop": "baseline_anchor_mismatch",
                              "diffs": derivation["frozen_anchor_diffs"]}, indent=2))
            raise SystemExit(3)

        # --- NON-RECORDED smoke gate: one scratch drawparam case ---------------
        smoke_case = dict(CM.make_drawparam_cases()[0])
        smoke_case.update({"i": -1, "rep": -1})
        smoke_gated, smoke_raw = run_one_case(shared, smoke_case, TIMEOUTS["smoke_process"])
        smoke_ok = (smoke_gated["status"] == "OK" and smoke_gated["verdict"] == "MATCH_EXPECTED"
                   and not smoke_raw["timed_out"])
        if not smoke_ok:
            print(json.dumps({"pre_capture_stop": "smoke_gate",
                              "smoke_gated": smoke_gated, "smoke_raw": smoke_raw}, indent=2))
            raise SystemExit(3)

        # --- PHASE 2: the append-only capture -----------------------------------
        raw.mkdir(parents=True)
        results_path = raw / "04_results.jsonl"
        results_raw_path = raw / "04_results_raw.jsonl"
        env = {"schema": 1, **current,
              "sw_vers": rec(["sw_vers"], TIMEOUTS["env_command"], HERE),
              "xcrun_version": rec(["xcrun", "--version"], TIMEOUTS["env_command"], HERE),
              "python": sys.version.split()[0], "machine": platform.machine(),
              "boundary": BOUNDARY, "timeouts_seconds": TIMEOUTS}
        put(raw / "00_inputs.json", env)
        if any(env[z]["timed_out"] or env[z]["exit"] != 0 or env[z]["exception"] is not None
              for z in ("sw_vers", "xcrun_version")):
            put(raw / "STOP.json", {"schema": 1, "phase": "environment", "automatic_retry": False})
            return

        cases = CM.full_case_list()
        put(raw / "01_cases.json", {
            "schema": 1, "run_id": a.run_id, "total": len(cases),
            "cases": [{"i": c["i"], "backend": c["backend"], "kernel": c["kernel"],
                      "case_name": c["name"], "item": c["item"], "rep": c["rep"]}
                     for c in cases]})
        put(raw / "02_build.json", {"schema": 1, "harness_build": build, "baseline": base})

        status_counts = {}
        verdict_counts = {}
        try:
            with results_path.open("a") as rf, results_raw_path.open("a") as rrf:
                for c in cases:
                    gated, rawrec = run_one_case(shared, c, TIMEOUTS["case_process"])
                    gated_full = {"i": c["i"], **gated}
                    raw_full = {"i": c["i"], **rawrec}
                    assert set(gated_full) == CASE_KEYS, sorted(set(gated_full) ^ CASE_KEYS)
                    assert set(raw_full) == CASE_RAW_KEYS, sorted(set(raw_full) ^ CASE_RAW_KEYS)
                    rf.write(json.dumps(gated_full, sort_keys=True) + "\n")
                    rf.flush()
                    rrf.write(json.dumps(raw_full, sort_keys=True) + "\n")
                    rrf.flush()
                    status_counts[gated["status"]] = status_counts.get(gated["status"], 0) + 1
                    verdict_counts[gated["verdict"]] = verdict_counts.get(gated["verdict"], 0) + 1
        except Exception as e:
            put(raw / "STOP.json", {"schema": 1, "phase": "dispatch_loop",
                                    "automatic_retry": False,
                                    "error": "%s: %s" % (type(e).__name__, e),
                                    "cases_completed": sum(status_counts.values())})
            return

        results_lines = sum(1 for _ in results_path.open("rb"))
        dispatch = {"argv": [sys.executable] + sys.argv,
                   "cwd": str(HERE), "started_utc": started_utc,
                   "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "duration_seconds": round(time.monotonic() - t0, 3),
                   "n_cases": len(cases), "status_counts": status_counts,
                   "verdict_counts": verdict_counts, "results_sha256": sha(results_path),
                   "results_lines": results_lines}
        assert set(dispatch) == DISPATCH_KEYS
        put(raw / "03_dispatch.json", dispatch)
        if results_lines != len(cases):
            put(raw / "STOP.json", {"schema": 1, "phase": "dispatch_loop", "automatic_retry": False})
            return
        item_counts = {}
        for c in cases:
            item_counts[c["item"]] = item_counts.get(c["item"], 0) + 1
        put(raw / "05_run_manifest.json", {
            "schema": 1, "run_id": a.run_id, "total_cases": len(cases),
            "item_counts": dict(sorted(item_counts.items())),
            "runner_sha256": sha(HERE / "run.py"), "casematrix_sha256": sha(HERE / "casematrix.py"),
            "harness_sha256": sha(HERE / "harness" / "build.sh"),
            "baseline_sha256": sha(work / "baseline.json"), "cases_sha256": sha(raw / "01_cases.json"),
            "results_sha256": dispatch["results_sha256"]})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if subprocess.run([sys.executable, "-B", "make_manifest.py", "--write"], cwd=HERE).returncode:
        raise SystemExit("make_manifest --write failed after capture")


if __name__ == "__main__":
    main()
