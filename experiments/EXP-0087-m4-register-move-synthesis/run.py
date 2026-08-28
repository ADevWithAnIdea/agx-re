#!/usr/bin/env python3
"""EXP-0087 capture runner. Never runs a device operation without --execute.

Per case: ONE independently re-assembled compact-move instruction (built by
tools/agx-isa's own assemble(), or -- for the two MOVE-05 values no
descriptor covers -- raw bytes), spliced in place of an existing 4-byte
instruction of OUR OWN compiled kernel (kernels/synth_move.metal), executed
by tools/agxtest/agxrun in a FRESH process on the local M4 under a hard
timeout, output read back as 16 float32 values and diffed against the known
baseline. A fault, hang or timeout is a RESULT: it is recorded and the sweep
continues in a fresh process; nothing is retried in place.

Schema constants (RUNS, AUTH_*, TIMEOUTS, key sets) are the single source of
truth; verify.py imports them from here rather than restating them.

Execution is single-threaded and synchronous: one case at a time, each
agxtest invocation is a blocking subprocess, and every raw record line is
flushed (and fsync'd) to disk before the next case starts.
"""
import argparse, datetime, hashlib, json, os, platform, shutil, struct, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0087-m4-register-move-synthesis"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import casematrix as CM   # noqa: E402
import baseline as BL     # noqa: E402

RUNS = ("m4-20260827-run01", "m4-20260827-run02")

BOUNDARY = ("public Metal API only; runtime MSL compile of our own kernels; binary-archive "
            "splice of our own compiled shader bytes re-assembled with tools/agx-isa; owned "
            "shared buffers; every case a fresh process; no Apple binary, archive, BO or "
            "command-stream inspection beyond our own compiled shader bytes")

TIMEOUTS = {"env_command": 10, "host_build": 60, "baseline": 60,
            "case_process": 60, "smoke_process": 60}

AUTH_CODE = ("kernels/synth_move.metal", "kernels/census.metal", "harness/build.sh",
             "baseline.py", "casematrix.py", "run.py", "analysis.py",
             "make_manifest.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")

# authoritative record key sets (imported by verify.py; never restated there)
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
            "stdout", "stderr", "exception"}
DISPATCH_KEYS = {"argv", "cwd", "started_utc", "finished_utc", "duration_seconds",
                 "n_cases", "status_counts", "results_sha256", "results_lines"}
CASE_KEYS = {"i", "name", "item", "probe", "dst", "src", "byte2", "op_desc",
             "hex_before", "hex_after", "changed_bytes", "splice_args", "exit",
             "timed_out", "exception", "duration_ms", "status", "pipeline_source",
             "out_hex", "diff_from_baseline", "raw_note", "stdout", "stderr"}

SMOKE_CASE = {"name": "smoke_move01_b2_00", "item": "SMOKE", "probe": "src", "dst": 12,
              "src": 8, "byte2": 0x00, "op_desc": 0x08, "hex": None, "assembled_as": None,
              "pred": {}, "note": "non-recorded scratch case (shape only)"}
SMOKE_CASE["hex"], SMOKE_CASE["assembled_as"] = CM.assemble_move(0x00, 12, 8, 0x08)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, o):
    txt = json.dumps(o, indent=2, sort_keys=True) + "\n"
    with open(p, "w") as f:
        f.write(txt)
        f.flush()
        os.fsync(f.fileno())


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


# ---------------------------------------------------------------------------
# probe splice construction (single definition used by runner, verifier, and
# the synthetic-tree builder)
# ---------------------------------------------------------------------------
def splice_args_for(case, probe_off_map):
    """Diff case['hex'] against the case's probe's ORIGINAL bytes; emit one
    main-relative _agc.main@OFF=HH splice arg per changed byte only."""
    probe = case["probe"]
    orig = bytes.fromhex(BL.FROZEN["probe_src_hex"] if probe == "src"
                         else BL.FROZEN["probe_dst_hex"])
    new = bytes.fromhex(case["hex"])
    off0 = probe_off_map[probe]
    changed = [i for i in range(4) if orig[i] != new[i]]
    args = ["_agc.main@%d=%02x" % (off0 + i, new[i]) for i in changed]
    return orig.hex(), new.hex(), changed, args


def agxtest_argv(shared, case, splice_args):
    argv = [sys.executable, "-B", str(REPO / "tools" / "agxtest" / "agxtest.py"),
            "--source", HERE / "kernels" / "synth_move.metal", "--function", "k",
            "--grid", "1", "--tg", "1", "--no-fast-math",
            "--shdump", shared / "bin" / "shdump",
            "--agxrun", shared / "bin" / "agxrun",
            "--agxparse", REPO / "tools" / "shdump" / "agxparse.py",
            "--workdir", shared, "--run-timeout", TIMEOUTS["case_process"],
            "--buf", "1=@%s" % (shared / "in.bin"), "--out", "0=16"]
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
        elif line.startswith("OUT 0 "):
            out["out_hex"] = line[len("OUT 0 "):].strip()
    return out


def run_one_case(shared, case, probe_off_map, timeout):
    i = case.get("i", -1)
    hex_before, hex_after, changed, sp_args = splice_args_for(case, probe_off_map)
    argv = agxtest_argv(shared, case, sp_args)
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_agxtest(r["stdout"]) if r["stdout"] else {}
    diff = None
    raw_note = ""
    if parsed.get("status") == "OK" and parsed.get("out_hex"):
        values = CM.decode_out(parsed["out_hex"])
        if values is None:
            raw_note = "undecodable_out_hex"
        else:
            diff = {str(k): v for k, v in CM.diff_from_baseline(values).items()}
    line = {"i": i, "name": case["name"], "item": case["item"], "probe": case["probe"],
            "dst": case["dst"], "src": case["src"], "byte2": case["byte2"],
            "op_desc": case["op_desc"], "hex_before": hex_before, "hex_after": hex_after,
            "changed_bytes": changed, "splice_args": sp_args, "exit": r["exit"],
            "timed_out": r["timed_out"], "exception": r["exception"], "duration_ms": dur,
            "status": parsed.get("status", "NO_STATUS"),
            "pipeline_source": parsed.get("pipeline_source"),
            "out_hex": parsed.get("out_hex"), "diff_from_baseline": diff,
            "raw_note": raw_note, "stdout": r["stdout"], "stderr": r["stderr"]}
    return line, parsed


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
        for k in ("git_revision", "git_dirty", "authored_code_sha256", "authored_doc_sha256"):
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
        # Nothing in this phase creates any raw/ artifact: a defect here is a
        # clean pre-capture stop with NO burned run id (the EXP-0077 lesson).
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
        probe_off_map = {"src": derivation["synth_move"]["probe_src_offset"],
                         "dst": derivation["synth_move"]["probe_dst_offset"]}

        (shared / "in.bin").write_bytes(CM.fill_in())

        # --- NON-RECORDED smoke gate: build+splice+run ONE scratch case -------
        smoke_rc, smoke_parsed = run_one_case(shared, dict(SMOKE_CASE, i=-1),
                                              probe_off_map, TIMEOUTS["smoke_process"])
        smoke_ok = (smoke_rc["status"] == "OK" and smoke_rc["pipeline_source"] == "archive"
                    and isinstance(smoke_rc["out_hex"], str) and len(smoke_rc["out_hex"]) >= 128
                    and len(smoke_rc["splice_args"]) >= 1 and not smoke_rc["timed_out"])
        if not smoke_ok:
            print(json.dumps({"pre_capture_stop": "smoke_gate",
                              "smoke_record": {k: smoke_rc[k] for k in
                                               ("status", "pipeline_source", "out_hex",
                                                "splice_args", "timed_out", "exit",
                                                "exception")}}, indent=2))
            raise SystemExit(3)

        # --- PHASE 2: the append-only capture -----------------------------------
        raw.mkdir(parents=True)
        # Persist the full baseline derivation (probe anchors + the compiler-
        # emitted-move CENSUS of kernels/census.metal) as append-only evidence
        # BEFORE work/ is deleted -- otherwise the census data computed above
        # would be lost with only its hash surviving in 05_run_manifest.json.
        shutil.copy2(work / "baseline.json", raw / "06_baseline.json")
        results_path = raw / "04_results.jsonl"
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

        cases = [dict(c, i=i) for i, c in enumerate(CM.CASES)]
        put(raw / "01_cases.json", {
            "schema": 1, "run_id": a.run_id, "total": len(cases),
            "cases": [{"i": c["i"], "name": c["name"], "item": c["item"], "probe": c["probe"],
                       "dst": c["dst"], "src": c["src"], "byte2": c["byte2"],
                       "op_desc": c["op_desc"], "hex": c["hex"], "assembled_as": c["assembled_as"],
                       "pred": c["pred"], "note": c["note"]} for c in cases]})
        put(raw / "02_build.json", {"schema": 1, "harness_build": build, "baseline": base})

        # --- the frozen sweep --------------------------------------------------
        status_counts = {}
        try:
            with results_path.open("a") as rf:
                for c in cases:
                    line, parsed = run_one_case(shared, c, probe_off_map,
                                                TIMEOUTS["case_process"])
                    assert set(line) == CASE_KEYS
                    rf.write(json.dumps(line, sort_keys=True) + "\n")
                    rf.flush()
                    os.fsync(rf.fileno())
                    if rf.closed:
                        raise IOError("results file unexpectedly closed")
                    status_counts[line["status"]] = status_counts.get(line["status"], 0) + 1
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
            "harness_sha256": sha(HERE / "harness" / "build.sh"),
            "kernel_synth_sha256": sha(HERE / "kernels" / "synth_move.metal"),
            "kernel_census_sha256": sha(HERE / "kernels" / "census.metal"),
            "baseline_sha256": sha(raw / "06_baseline.json"),
            "cases_sha256": sha(raw / "01_cases.json"),
            "results_sha256": dispatch["results_sha256"],
            "probe_src_hex": derivation["synth_move"]["probe_src_hex"],
            "probe_dst_hex": derivation["synth_move"]["probe_dst_hex"],
            "probe_src_offset": derivation["synth_move"]["probe_src_offset"],
            "probe_dst_offset": derivation["synth_move"]["probe_dst_offset"]})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if subprocess.run([sys.executable, "-B", "make_manifest.py", "--write"],
                      cwd=HERE).returncode:
        raise SystemExit("make_manifest --write failed after capture")


if __name__ == "__main__":
    main()
