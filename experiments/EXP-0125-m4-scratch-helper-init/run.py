#!/usr/bin/env python3
"""EXP-0125 capture runner.

Order of operations, none skippable:
  1. `verify.py --selftest` and `verify.py --seqtest` must both pass (no
     device, no raw/).
  2. A NON-RECORDED smoke pass (one I-family nospill checkpoint walk, one
     B-family trial, one C-family n_queues=1 level, all in a scratch work/
     dir, never under raw/) must complete cleanly. A smoke defect aborts
     here -- no run id burned, no raw/<run-id> created.
  3. Only then: mkdir raw/<run-id> (refuses if it already exists -- run ids
     are never reused), and the three families run in order (I, then B,
     then C), each record appended+fflush'd immediately as it completes.

PROGRESS.md gets one line per I-checkpoint, per B-trial, and per C-level.
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import casematrix as CM   # noqa: E402
import traceparse as TP   # noqa: E402

RUNS = ("m4-20260828-run01", "m4-20260828-run02")

AUTH_CODE = ("kernels/kernelgen.py", "harness/inittrace.c", "harness/initprobe.m",
            "harness/ceiling.m", "harness/concurrent.m", "casematrix.py",
            "traceparse.py", "run.py", "verify.py", "analysis/analyze.py",
            "make_manifest.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "README.md")

BOUNDARY = ("public Metal API only (runtime MSL compile via our own harness/initprobe.m, "
           "harness/ceiling.m, harness/concurrent.m); DATA-TRACE of our own process's IOKit "
           "boundary traffic (harness/inittrace.c, an interposer over the public IOKit "
           "user-client surface), checkpointed across device/queue/pipeline lifecycle, "
           "including a bounded content PREFIX of every BO our own process registers via the "
           "resource-map selector and a best-effort read of our own process's own selector-5 "
           "shared-page CPU pointers -- never a pointer found inside one followed to open "
           "another object, and no Apple binary/framework/kext/firmware ever opened, "
           "disassembled, or introspected")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def append_jsonl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def progress(raw_dir, line):
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(raw_dir.parent.parent / "PROGRESS.md", "a") as f:
        f.write(f"- {ts} [{raw_dir.name}] {line}\n")
        f.flush()


def provenance():
    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, text=True, capture_output=True).stdout
    return {
        "git_revision_informational_only": git("rev-parse", "HEAD").strip(),
        "git_dirty_informational_only": git("status", "--porcelain").strip() != "",
        "note": "informational only -- NOT a cross-run gate (CODEX.md 'pin the revision, do "
                "not gate on live HEAD'; repo HEAD moves as the orchestrator commits sibling "
                "experiments)",
        "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
        "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC if (HERE / p).is_file()},
        "python": platform.python_version(), "platform": platform.platform(),
        "macos_sw_vers": subprocess.run(["sw_vers"], text=True, capture_output=True).stdout,
        "hostname_class": "local M4 test target (per CLAUDE.md target discipline)",
    }


def build_tools(work):
    inittrace = work / "inittrace.dylib"
    initprobe = work / "initprobe"
    ceiling = work / "ceiling"
    concurrent = work / "concurrent"
    steps = [
        (["clang", "-dynamiclib", "-o", str(inittrace), str(HERE / "harness/inittrace.c"),
          "-framework", "IOKit", "-framework", "CoreFoundation"], "inittrace"),
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", str(initprobe), str(HERE / "harness/initprobe.m")], "initprobe"),
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", str(ceiling), str(HERE / "harness/ceiling.m")], "ceiling"),
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", str(concurrent), str(HERE / "harness/concurrent.m")], "concurrent"),
    ]
    for argv, label in steps:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=CM.TIMEOUTS["env_command"] * 2)
        if r.returncode:
            raise SystemExit(f"{label} build failed:\n{r.stderr}")
    return inittrace, initprobe, ceiling, concurrent


# ---------------------------------------------------------------------------
# I family
# ---------------------------------------------------------------------------
def run_i_case(case, inittrace, initprobe, dump_root, case_path, timing_path):
    variant = case["variant"]
    dump_dir = dump_root / case["name"]
    log_path = dump_root / f"{case['name']}.trace.log"
    cplog_path = dump_root / f"{case['name']}.checkpoints.jsonl"
    argv = [str(initprobe), "--variant", variant,
           "--trivial", str(HERE / "kernels/cs_trivial.metal"),
           "--checkpoints-log", str(cplog_path),
           "--grid", str(CM.I_GRID), "--tg", str(CM.I_TG)]
    if variant == "spill":
        argv += ["--spill", str(HERE / "kernels" / f"cs_k{CM.I_K}.metal"), "--k", str(CM.I_K)]
    env = os.environ.copy()
    env.update({"DYLD_INSERT_LIBRARIES": str(inittrace), "MAPTRACE_LOG": str(log_path),
               "MAPTRACE_DUMP_DIR": str(dump_dir), "MAPTRACE_PREFIX_CAP": "4096"})
    t0 = time.monotonic()
    try:
        cp = subprocess.run(argv, cwd=HERE, capture_output=True, text=True,
                            timeout=CM.TIMEOUTS["i_probe"], env=env)
        dur = int((time.monotonic() - t0) * 1000)
        timed_out, exit_code, stdout, stderr = False, cp.returncode, cp.stdout, cp.stderr
    except subprocess.TimeoutExpired as e:
        dur = int((time.monotonic() - t0) * 1000)
        timed_out, exit_code = True, None
        stdout = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")

    status, checksum = "NO_STATUS", None
    for line in (stdout or "").splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("RESULT "):
            for tok in line.split():
                if tok.startswith("checksum="):
                    checksum = tok.split("=", 1)[1]

    append_jsonl(case_path.parent / "02b_i_summary.jsonl", {
        "case": case["name"], "variant": variant, "probe_exit": exit_code,
        "probe_timed_out": timed_out, "probe_status": status, "checksum": checksum,
    })
    append_jsonl(timing_path, {"record": f"I:{case['name']}", "duration_ms": dur,
                               "stdout": stdout, "stderr": stderr})

    log_text = log_path.read_text() if log_path.is_file() else ""
    cp_log_index = TP.parse_checkpoint_log_lines(log_text)
    cp_records = TP.read_checkpoints_jsonl(cplog_path)
    for rec in cp_records:
        idx, label = rec["idx"], rec["label"]
        cp_dir = dump_dir / f"cp{idx:02d}"
        bos, shape, total, code_present, code_size = TP.checkpoint_snapshot(cp_dir)
        a0, a1 = TP.shared_pages_snapshot(cp_dir)
        logged = cp_log_index.get(idx, {})
        gated = {
            "case": case["name"], "variant": variant, "cp_idx": idx, "cp_label": label,
            "nbo": len(bos), "bo_total_bytes": total, "resource_map_shape": shape,
            "nshared": logged.get("nshared", 0), "shared_addr0_present": a0, "shared_addr1_present": a1,
            "code_window_present": code_present, "code_window_size": code_size,
        }
        append_jsonl(case_path, gated)
        # cross-check: our own snapshot's nbo must equal inittrace.c's own
        # bookkeeping at that instant, or the discrepancy itself is logged
        # (never silently reconciled) into the ungated timing stream.
        if logged.get("nbo") is not None and logged["nbo"] != len(bos):
            append_jsonl(timing_path, {"record": f"I:{case['name']}:cp{idx}:NBO_MISMATCH",
                                       "duration_ms": 0,
                                       "stdout": f"snapshot={len(bos)} tracelog={logged['nbo']}",
                                       "stderr": ""})
        progress(case_path.parent, f"I {case['name']} cp{idx} {label}: nbo={len(bos)} "
                f"bo_total_bytes={total} code_window={code_present}")
    return timed_out or exit_code not in (0,)


# ---------------------------------------------------------------------------
# B family
# ---------------------------------------------------------------------------
def run_b_stage(stage, ceiling, work, raw):
    trial_path = raw / "04a_b_trials.jsonl"
    result_path = raw / "04b_b_results.jsonl"
    timing_path = raw / "03_timing.jsonl"
    src_dir = work / f"bsrc_{stage}"
    src_dir.mkdir(parents=True, exist_ok=True)
    hard_fault = [False]

    def oracle(k):
        srcfile = src_dir / f"{stage}_k{k}.metal"
        gen = subprocess.run([sys.executable, "-B", str(HERE / "kernels/kernelgen.py"),
                              "--emit", stage, "--k", str(k)],
                             cwd=HERE, capture_output=True, text=True,
                             timeout=CM.TIMEOUTS["env_command"])
        srcfile.write_text(gen.stdout)
        t0 = time.monotonic()
        try:
            cp = subprocess.run([str(ceiling), "--stage", stage, "--source", str(srcfile)],
                                capture_output=True, text=True, timeout=CM.TIMEOUTS["b_trial"])
            dur = int((time.monotonic() - t0) * 1000)
            timed_out, exit_code, stdout, stderr = False, cp.returncode, cp.stdout, cp.stderr
        except subprocess.TimeoutExpired as e:
            dur = int((time.monotonic() - t0) * 1000)
            timed_out, exit_code = True, None
            stdout = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        status = "NO_STATUS"
        for line in (stdout or "").splitlines():
            if line.startswith("STATUS "):
                status = line.split(None, 1)[1].strip()
        append_jsonl(timing_path, {"record": f"B:{stage}:k{k}", "duration_ms": dur,
                                   "stdout": stdout, "stderr": stderr})
        if timed_out:
            hard_fault[0] = True
        ok = (not timed_out) and exit_code == 0 and status == "OK"
        return ok

    trials, result = CM.run_bisection(oracle)
    for t in trials:
        rec = {"stage": stage, **t}
        append_jsonl(trial_path, rec)
        progress(raw, f"B {stage} step{t['step']} ({t['phase']}) k={t['k']}: ok={t['ok']}")
        if hard_fault[0]:
            progress(raw, f"B {stage} HARD FAULT/TIMEOUT during step {t['step']}: aborting stage")
            break
    append_jsonl(result_path, {"stage": stage, "n_trials": len(trials), **result})
    progress(raw, f"B {stage} finished: last_ok={result['last_ok']} first_fail={result['first_fail']} "
            f"bracket_ok={result['bracket_ok']} n_trials={len(trials)}")
    return hard_fault[0]


# ---------------------------------------------------------------------------
# C family. Each level runs CM.C_REPEATS independent trials (see
# casematrix.py's module docstring: single-trial-per-level was tried first
# during pre-capture reconnaissance and found the failure mode is
# intermittent, not a monotonic wall -- repeats characterize a FAILURE RATE
# instead of a single pass/fail). No escalation-stop: only a hard fault
# (timeout or a crash/unexpected exit code) aborts the run early.
# ---------------------------------------------------------------------------
def run_c_trial(n_queues, trial_idx, concurrent, raw):
    level_path = raw / "05_c_levels.jsonl"
    timing_path = raw / "03_timing.jsonl"
    name = f"C_nq{n_queues}"
    argv = [str(concurrent), "--source", str(HERE / "kernels" / f"cs_k{CM.C_K}.metal"),
           "--n-queues", str(n_queues), "--grid", str(CM.C_GRID), "--tg", str(CM.C_TG)]
    t0 = time.monotonic()
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=CM.c_timeout(n_queues))
        dur = int((time.monotonic() - t0) * 1000)
        timed_out, exit_code, stdout, stderr = False, cp.returncode, cp.stdout, cp.stderr
    except subprocess.TimeoutExpired as e:
        dur = int((time.monotonic() - t0) * 1000)
        timed_out, exit_code = True, None
        stdout = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    status = "NO_STATUS"
    ok_q = execfail_q = nonfinite_q = mismatch_q = None
    for line in (stdout or "").splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("SUMMARY "):
            parts = dict(tok.split("=") for tok in line.split()[1:])
            ok_q = int(parts.get("ok", -1))
            execfail_q = int(parts.get("execfail", -1))
            nonfinite_q = int(parts.get("nonfinite", -1))
            mismatch_q = int(parts.get("checksum_mismatch", -1))
    append_jsonl(timing_path, {"record": f"C:{name}:t{trial_idx}", "duration_ms": dur,
                               "stdout": stdout, "stderr": stderr})
    append_jsonl(level_path, {
        "name": name, "n_queues": n_queues, "trial": trial_idx, "executed": True,
        "exit": exit_code, "timed_out": timed_out, "status": status,
        "ok_queues": ok_q, "execfail_queues": execfail_q,
        "nonfinite_queues": nonfinite_q, "checksum_mismatch": mismatch_q,
    })
    progress(raw, f"C {name} trial{trial_idx}: status={status} ok={ok_q}/{n_queues} timed_out={timed_out}")
    hard_fault = timed_out or exit_code not in (0, 1)  # exit 1 == DEGRADED, still a captured result
    return hard_fault


# ---------------------------------------------------------------------------
# Smoke gate (non-recorded)
# ---------------------------------------------------------------------------
def smoke_test(inittrace, initprobe, ceiling, concurrent, scratch_root):
    try:
        dump_root = scratch_root / "smoke_dumps"
        dump_root.mkdir(parents=True, exist_ok=True)
        log_path = dump_root / "smoke.trace.log"
        cplog_path = dump_root / "smoke.checkpoints.jsonl"
        dump_dir = dump_root / "SMOKE_I"
        env = os.environ.copy()
        env.update({"DYLD_INSERT_LIBRARIES": str(inittrace), "MAPTRACE_LOG": str(log_path),
                   "MAPTRACE_DUMP_DIR": str(dump_dir), "MAPTRACE_PREFIX_CAP": "2048"})
        cp = subprocess.run([str(initprobe), "--variant", "nospill",
                             "--trivial", str(HERE / "kernels/cs_trivial.metal"),
                             "--checkpoints-log", str(cplog_path), "--grid", "1024", "--tg", "64"],
                            cwd=HERE, capture_output=True, text=True, timeout=CM.TIMEOUTS["smoke"], env=env)
        if cp.returncode != 0 or "STATUS OK" not in cp.stdout:
            print("SMOKE FAIL (I):", cp.stdout, cp.stderr[-500:], file=sys.stderr)
            return False
        recs = TP.read_checkpoints_jsonl(cplog_path)
        if len(recs) != len(CM.CHECKPOINT_LABELS):
            print("SMOKE FAIL (I checkpoints):", recs, file=sys.stderr)
            return False

        src = scratch_root / "smoke_cs_k1024.metal"
        gen = subprocess.run([sys.executable, "-B", str(HERE / "kernels/kernelgen.py"),
                              "--emit", "cs", "--k", "1024"], cwd=HERE,
                             capture_output=True, text=True, timeout=CM.TIMEOUTS["env_command"])
        src.write_text(gen.stdout)
        cp2 = subprocess.run([str(ceiling), "--stage", "cs", "--source", str(src)],
                             capture_output=True, text=True, timeout=CM.TIMEOUTS["b_trial"])
        if cp2.returncode != 0 or "STATUS OK" not in cp2.stdout:
            print("SMOKE FAIL (B):", cp2.stdout, cp2.stderr[-500:], file=sys.stderr)
            return False

        cp3 = subprocess.run([str(concurrent), "--source", str(HERE / f"kernels/cs_k{CM.C_K}.metal"),
                              "--n-queues", "1", "--grid", "1024", "--tg", "64"],
                             capture_output=True, text=True, timeout=CM.c_timeout(1))
        if cp3.returncode != 0 or "STATUS OK" not in cp3.stdout:
            print("SMOKE FAIL (C):", cp3.stdout, cp3.stderr[-500:], file=sys.stderr)
            return False
        return True
    except Exception as e:  # noqa: BLE001
        print("SMOKE FAIL (exception):", repr(e), file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ", ".join(RUNS))

    for gate in ("--selftest", "--seqtest"):
        r = subprocess.run([sys.executable, "-B", "verify.py", gate], cwd=HERE)
        if r.returncode:
            raise SystemExit("verify.py %s failed: no capture is authorized" % gate)

    gen = subprocess.run([sys.executable, "-B", "kernels/kernelgen.py"], cwd=HERE,
                         capture_output=True, text=True, timeout=CM.TIMEOUTS["env_command"])
    if gen.returncode:
        raise SystemExit("kernel generation failed:\n" + gen.stderr)

    work_root = HERE / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="build-", dir=work_root))
    inittrace, initprobe, ceiling, concurrent = build_tools(work)

    if not smoke_test(inittrace, initprobe, ceiling, concurrent, work):
        raise SystemExit("SMOKE GATE FAILED: no run id burned, no raw/ artifact created")
    print("smoke gate: OK (non-recorded)")

    raw = HERE / "raw" / a.run_id
    if raw.exists():
        raise SystemExit("run id already has a raw/ directory -- run ids are never reused: %s" % raw)
    raw.mkdir(parents=True)
    dump_root = raw / "dumps"
    dump_root.mkdir()
    progress(raw, f"run {a.run_id} started; smoke gate passed")

    put(raw / "00_inputs.json", {"run_id": a.run_id, "started_utc":
                                 datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                 "provenance": provenance(), "boundary": BOUNDARY})

    if a.run_id == RUNS[1]:
        prev = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        cur = json.loads((raw / "00_inputs.json").read_text())
        for k in ("authored_code_sha256", "authored_doc_sha256"):
            if prev["provenance"][k] != cur["provenance"][k]:
                raise SystemExit("run02 authored-file hashes differ from run01 (harness changed "
                                 "mid-experiment): " + k)

    i_path = raw / "02a_i_checkpoints.jsonl"
    i_summary_path = raw / "02b_i_summary.jsonl"
    b_trial_path = raw / "04a_b_trials.jsonl"
    b_result_path = raw / "04b_b_results.jsonl"
    c_path = raw / "05_c_levels.jsonl"
    timing_path = raw / "03_timing.jsonl"
    for p in (i_path, i_summary_path, b_trial_path, b_result_path, c_path, timing_path):
        p.touch()

    aborted = False

    # --- I family ---
    for case in CM.I_CASES:
        hard = run_i_case(case, inittrace, initprobe, dump_root, i_path, timing_path)
        if hard:
            progress(raw, f"HARD FAULT/TIMEOUT at I case {case['name']}: aborting entire remaining run")
            aborted = True
            break

    # --- B family ---
    if not aborted:
        for stage in CM.B_STAGES:
            hard = run_b_stage(stage, ceiling, work, raw)
            if hard:
                progress(raw, f"HARD FAULT/TIMEOUT during B stage {stage}: aborting entire remaining run")
                aborted = True
                break

    # --- C family (no escalation-stop; see casematrix.py docstring) ---
    if not aborted:
        for n in CM.C_LEVELS:
            for trial_idx in range(CM.C_REPEATS):
                hard = run_c_trial(n, trial_idx, concurrent, raw)
                if hard:
                    progress(raw, f"HARD FAULT/TIMEOUT at C n_queues={n} trial{trial_idx}: "
                            f"aborting entire remaining run")
                    aborted = True
                    break
            if aborted:
                break

    summary = {
        "run_id": a.run_id, "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "aborted_on_hard_fault": aborted,
        "i_checkpoints_sha256": sha(i_path), "i_summary_sha256": sha(i_summary_path),
        "b_trials_sha256": sha(b_trial_path), "b_results_sha256": sha(b_result_path),
        "c_levels_sha256": sha(c_path), "timing_sha256": sha(timing_path),
    }
    put(raw / "01_summary.json", summary)
    progress(raw, f"run {a.run_id} finished; aborted={aborted}")
    print(json.dumps(summary, indent=2))
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
