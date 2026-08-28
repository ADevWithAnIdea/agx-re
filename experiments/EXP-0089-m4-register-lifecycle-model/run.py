#!/usr/bin/env python3
"""EXP-0089 capture runner. Never runs a device operation without --execute.

Per case: ONE semantic change (a single field, or one raw byte, applied at
one or two FROZEN anchor sites -- see casematrix.py) to OUR OWN compiled
kernel, re-assembled with tools/agx-isa (assemble(decode(bytes)+override)) or
raw-byte patched, spliced via tools/agxtest/agxtest.py into the binary
archive of our own MSL, executed by tools/agxtest/agxrun in a FRESH process
on the local M4 under a hard timeout, output read back and compared to an
INDEPENDENT host-side oracle (casematrix.EXPECTED). A fault, hang, or timeout
is a RESULT: recorded, and the sweep continues in a fresh process; nothing is
retried in place.

Two records per case, split per the standing NO-NONDETERMINISM gate:
  04_results.jsonl      -- GATED (byte/JSON-comparable across runs): case
                            identity, splice, status, decoded outputs, VERDICT.
                            Contains NO timing/duration field.
  04_results_raw.jsonl  -- NOT gated: full subprocess receipt (stdout/stderr/
                            duration_ms/exit/timed_out/exception) per case,
                            append-only evidence, timing included.

Execution is single-threaded and synchronous: one case at a time, each
agxtest invocation is a blocking subprocess in its OWN fresh process, and
every raw record line is flushed to disk before the next case starts.

NOTE on cross-run gating (lesson carried over from a sibling experiment's
QUARANTINE, recorded in ../SUBAGENT_BRIEF.md): the run02 pre-flight gate
requires the AUTHORED SOURCE HASHES to match run01's, but does NOT require
live `git rev-parse HEAD` to be unchanged -- the orchestrator commits other
experiments' work between runs, and that is not contamination of THIS
experiment's frozen inputs.
"""
import argparse, datetime, hashlib, json, platform, shutil, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0089-m4-register-lifecycle-model"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import casematrix as CM   # noqa: E402

RUNS = ("m4-lifecycle-20260828-run01", "m4-lifecycle-20260828-run02")

BOUNDARY = ("public Metal API only; runtime MSL compile of our own kernels; binary-archive "
            "splice of our own compiled shader bytes re-assembled with tools/agx-isa; "
            "owned shared buffers; every case a fresh process; no Apple binary, archive, BO "
            "or command-stream inspection beyond our own compiled shader bytes")

TIMEOUTS = {"env_command": 10, "host_build": 60, "baseline": 180,
            "case_process": 60, "smoke_process": 60}

AUTH_CODE = tuple(f"kernels/{k}.metal" for k in CM.KERNELS) + (
    "harness/build.sh", "baseline.py", "casematrix.py", "run.py", "analysis.py",
    "make_manifest.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")

# authoritative record key sets (imported by verify.py; never restated there)
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
            "stdout", "stderr", "exception"}
DISPATCH_KEYS = {"argv", "cwd", "started_utc", "finished_utc", "duration_seconds",
                 "n_cases", "status_counts", "verdict_counts", "results_sha256",
                 "results_lines"}
# GATED (04_results.jsonl) -- must never contain a timing/duration/pid/address field.
CASE_KEYS = {"i", "kernel", "case_name", "item", "rep", "splice_args", "changed_bytes",
             "status", "pipeline_source", "out_values", "expected_values", "verdict",
             "mismatch_indices"}
# NOT gated (04_results_raw.jsonl) -- full receipt including timing.
CASE_RAW_KEYS = {"i", "duration_ms", "exit", "timed_out", "exception", "stdout", "stderr"}

TOL_REL = 1e-4

SMOKE_CASE = {"kernel": "adjacent", "case_name": "smoke_baseline", "item": "SMOKE",
             "splice": [], "note": "non-recorded scratch case (shape only)"}


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


def agxtest_argv(shared, kernel, splice_args):
    src = HERE / "kernels" / f"{kernel}.metal"
    a_path = shared / f"a_{kernel}.bin"
    argv = [sys.executable, "-B", str(REPO / "tools" / "agxtest" / "agxtest.py"),
            "--source", src, "--function", "k", "--grid", "1", "--tg", "1",
            "--no-fast-math",
            "--shdump", shared / "bin" / "shdump",
            "--agxrun", shared / "bin" / "agxrun",
            "--agxparse", REPO / "tools" / "shdump" / "agxparse.py",
            "--workdir", shared / kernel, "--run-timeout", TIMEOUTS["case_process"],
            "--buf", "0=@%s" % a_path,
            "--out", "1=%d" % CM.OUT_N[kernel]]
    for sp in splice_args:
        argv += ["--splice", sp]
    return argv


def parse_agxtest(stdout):
    out = {"status": "NO_STATUS", "pipeline_source": None, "out_hex": None}
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            out["status"] = line.split(None, 1)[1].strip()
        elif line.startswith("PIPELINE_SOURCE"):
            out["pipeline_source"] = line.split(None, 1)[1].strip()
        elif line.startswith("OUT 1 "):
            out["out_hex"] = line.split(None, 2)[2].strip()
    return out


def decode_floats(hexstr):
    import struct
    b = bytes.fromhex(hexstr)
    n = len(b) // 4
    return [struct.unpack_from("<f", b, i * 4)[0] for i in range(n)]


def compute_verdict(kernel, status, out_values):
    if status != "OK" or out_values is None:
        return "FAULT", []
    expected = CM.EXPECTED[kernel](CM.INPUTS[kernel])
    mism = []
    for i, (got, exp) in enumerate(zip(out_values, expected)):
        tol = TOL_REL * max(1.0, abs(exp))
        if abs(got - exp) > tol:
            mism.append(i)
    return ("MATCH_EXPECTED" if not mism else "MISMATCH_EXPECTED"), mism


def run_one_case(shared, kernel, case_name, item, rep, splice_args, changed_bytes, timeout):
    argv = agxtest_argv(shared, kernel, splice_args)
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_agxtest(r["stdout"]) if r["stdout"] else {}
    out_values = None
    if parsed.get("out_hex"):
        try:
            out_values = decode_floats(parsed["out_hex"])
        except ValueError:
            out_values = None
    verdict, mism = compute_verdict(kernel, parsed.get("status", "NO_STATUS"), out_values)
    if r["timed_out"] or r["exception"] is not None:
        verdict = "FAULT"
    gated = {"kernel": kernel, "case_name": case_name, "item": item, "rep": rep,
             "splice_args": splice_args, "changed_bytes": changed_bytes,
             "status": parsed.get("status", "NO_STATUS"),
             "pipeline_source": parsed.get("pipeline_source"),
             "out_values": ["%.8g" % v for v in out_values] if out_values is not None else None,
             "expected_values": ["%.8g" % v for v in CM.EXPECTED[kernel](CM.INPUTS[kernel])],
             "verdict": verdict, "mismatch_indices": mism}
    raw = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
           "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, raw


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
        # Authored-hash equality is the contract; live git HEAD is explicitly
        # NOT required to be unchanged (the orchestrator commits other
        # experiments between runs -- see run.py module docstring).
        for k in ("authored_code_sha256", "authored_doc_sha256"):
            if first.get(k) != current[k]:
                raise SystemExit("run02 authored-hash provenance differs from closed run01: " + k)

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
        base = rec([sys.executable, "-B", "baseline.py", "--bin-dir", bin_dir,
                    "--out", work / "baseline.json"], TIMEOUTS["baseline"], HERE)
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

        # shared per-kernel input buffers (written once; fixed for the whole run)
        for kernel in CM.KERNELS:
            (shared / f"a_{kernel}.bin").write_bytes(CM.input_bytes(kernel))

        # --- NON-RECORDED smoke gate: build+splice(none)+run ONE scratch case --
        (shared / SMOKE_CASE["kernel"]).mkdir(parents=True, exist_ok=True)
        smoke_gated, smoke_raw = run_one_case(shared, SMOKE_CASE["kernel"],
                                              SMOKE_CASE["case_name"], SMOKE_CASE["item"],
                                              -1, [], [], TIMEOUTS["smoke_process"])
        smoke_ok = (smoke_gated["status"] == "OK"
                    and smoke_gated["pipeline_source"] == "archive"
                    and smoke_gated["out_values"] is not None
                    and len(smoke_gated["out_values"]) == CM.OUT_N[SMOKE_CASE["kernel"]]
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
               "boundary": BOUNDARY, "timeouts_seconds": TIMEOUTS,
               "repeat_n": CM.REPEAT_N, "tol_rel": TOL_REL}
        put(raw / "00_inputs.json", env)
        if any(env[z]["timed_out"] or env[z]["exit"] != 0 or env[z]["exception"] is not None
               for z in ("sw_vers", "xcrun_version")):
            put(raw / "STOP.json", {"schema": 1, "phase": "environment", "automatic_retry": False})
            return

        cases = CM.full_case_list()
        put(raw / "01_cases.json", {
            "schema": 1, "run_id": a.run_id, "total": len(cases),
            "cases": [{"i": c["i"], "kernel": c["kernel"], "case_name": c["name"],
                       "item": c["item"], "rep": c["rep"], "note": c["note"]}
                      for c in cases]})
        put(raw / "02_build.json", {"schema": 1, "harness_build": build, "baseline": base})

        # --- the frozen sweep --------------------------------------------------
        status_counts = {}
        verdict_counts = {}
        try:
            with results_path.open("a") as rf, results_raw_path.open("a") as rrf:
                for c in cases:
                    anc = CM.get_anchor(c["kernel"])
                    mm = {site: anc[site]["hex"] for site in CM.anchor_site_keys(c["kernel"])}
                    splice_args, changed = CM.build_splice_args(c["kernel"], c, mm)
                    gated, rawrec = run_one_case(shared, c["kernel"], c["name"], c["item"],
                                                 c["rep"], splice_args, changed,
                                                 TIMEOUTS["case_process"])
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
        except Exception as e:            # harness defect mid-sweep: stop cleanly
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
                    "verdict_counts": verdict_counts,
                    "results_sha256": sha(results_path),
                    "results_lines": results_lines}
        assert set(dispatch) == DISPATCH_KEYS
        put(raw / "03_dispatch.json", dispatch)
        if results_lines != len(cases):
            put(raw / "STOP.json", {"schema": 1, "phase": "dispatch_loop",
                                    "automatic_retry": False})
            return
        item_counts = {}
        for c in cases:
            item_counts[c["item"]] = item_counts.get(c["item"], 0) + 1
        put(raw / "05_run_manifest.json", {
            "schema": 1, "run_id": a.run_id, "total_cases": len(cases),
            "item_counts": dict(sorted(item_counts.items())),
            "runner_sha256": sha(HERE / "run.py"),
            "casematrix_sha256": sha(HERE / "casematrix.py"),
            "harness_sha256": sha(HERE / "harness" / "build.sh"),
            "baseline_sha256": sha(work / "baseline.json"),
            "cases_sha256": sha(raw / "01_cases.json"),
            "results_sha256": dispatch["results_sha256"]})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if subprocess.run([sys.executable, "-B", "make_manifest.py", "--write"],
                      cwd=HERE).returncode:
        raise SystemExit("make_manifest --write failed after capture")


if __name__ == "__main__":
    main()
