#!/usr/bin/env python3
"""EXP-0107 capture runner.

Order of operations, none skippable:
  1. `verify.py --selftest` and `verify.py --seqtest` (synthetic-fixture
     gates; no device, no raw/) must both pass.
  2. A NON-RECORDED smoke case (compile+dispatch+maptrace of a small, known-
     safe kernel, in a scratch temp dir, never written under raw/) must
     complete with STATUS OK. A smoke defect aborts here -- no run id is
     burned and no raw/<run-id> directory is created.
  3. Only then: mkdir raw/<run-id> (must not already exist -- run ids are
     never reused), and the real case matrix (casematrix.ALL_CASES) runs,
     one case per fresh subprocess, in order, with escalation-stop policy
     (see casematrix.py's module docstring).

Every JSONL record is appended and fflush'd immediately after the case that
produced it completes -- never buffered in memory for a bulk write at the
end -- so a kill costs at most the one in-flight case. PROGRESS.md gets one
line per completed case.
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP_REL = "experiments/EXP-0107-m4-scratch-helper-abi"
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import casematrix as CM   # noqa: E402
import traceparse as TP   # noqa: E402

RUNS = ("m4-20260827-run01", "m4-20260827-run02")

AUTH_CODE = ("kernels/generate.py", "harness/probe.m", "harness/maptrace.c",
            "harness/metadata.py", "casematrix.py", "traceparse.py", "run.py",
            "verify.py", "analysis/analyze.py", "make_manifest.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "README.md")

BOUNDARY = ("public Metal API only (runtime MSL compile via our own harness/probe.m and "
           "tools/shdump); OWN-SHADER metadata read from our own just-compiled archive "
           "(harness/metadata.py, the established EXP-0041/EXP-0020 pattern); DATA-TRACE of "
           "our own process's IOKit boundary traffic (harness/maptrace.c, an interposer over "
           "the public IOKit user-client surface) including a bounded content PREFIX of every "
           "BO our own process registers via the resource-map selector -- never a pointer found "
           "inside one followed to open another object, and no Apple binary/framework/kext/"
           "firmware ever opened, disassembled, or introspected")

SMOKE_CASE = {"name": "SMOKE", "family": "SMOKE", "stage": "cs", "k": 32,
             "source": "cs_k32.metal", "grid": 8, "tg": 8, "n": 1}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def append_jsonl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def progress(run_dir, line):
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(run_dir.parent.parent / "PROGRESS.md", "a") as f:
        f.write(f"- {ts} [{run_dir.name}] {line}\n")
        f.flush()


def provenance():
    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, text=True, capture_output=True).stdout
    return {
        "git_revision_informational_only": git("rev-parse", "HEAD").strip(),
        "git_dirty_informational_only": git("status", "--porcelain").strip() != "",
        "note": "informational only -- NOT a cross-run gate (repo HEAD moves as the "
                "orchestrator commits sibling experiments; see CODEX.md / dispatch brief "
                "'pin the revision, do not gate on live HEAD')",
        "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
        "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC if (HERE / p).is_file()},
        "python": platform.python_version(), "platform": platform.platform(),
        "macos_sw_vers": subprocess.run(["sw_vers"], text=True, capture_output=True).stdout,
        "hostname_class": "local M4 test target (per CLAUDE.md target discipline)",
    }


def build_tools(work):
    maptrace = work / "maptrace.dylib"
    probe = work / "probe"
    b1 = subprocess.run(["clang", "-dynamiclib", "-o", str(maptrace), str(HERE / "harness/maptrace.c"),
                         "-framework", "IOKit", "-framework", "CoreFoundation"],
                        capture_output=True, text=True, timeout=CM.TIMEOUTS["env_command"] * 2)
    if b1.returncode:
        raise SystemExit("maptrace build failed:\n" + b1.stderr)
    b2 = subprocess.run(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
                         "-o", str(probe), str(HERE / "harness/probe.m")],
                        capture_output=True, text=True, timeout=CM.TIMEOUTS["env_command"] * 2)
    if b2.returncode:
        raise SystemExit("probe build failed:\n" + b2.stderr)
    return maptrace, probe


def run_metadata(case, timeout):
    stage = case["stage"]
    source = HERE / "kernels" / case["source"]
    t0 = time.monotonic()
    try:
        cp = subprocess.run([sys.executable, "-B", str(HERE / "harness/metadata.py"),
                             "--stage", stage, "--source", str(source)],
                            cwd=HERE, capture_output=True, text=True, timeout=timeout)
        dur = int((time.monotonic() - t0) * 1000)
        timed_out, exc = False, None
    except subprocess.TimeoutExpired as e:
        dur = int((time.monotonic() - t0) * 1000)
        cp = argparse.Namespace(returncode=None,
                                stdout=(e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                                stderr=(e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or ""))
        timed_out, exc = True, "TimeoutExpired"
    parsed = {"status": "NO_STATUS", "gpr_field_0": None, "scratch_field_41_or_14": None,
              "all_u32_fields": None, "main_bytes": None, "main_sha256": None}
    if not timed_out and cp.returncode == 0:
        try:
            d = json.loads(cp.stdout)
            key = "compute" if stage == "cs" else stage  # vs/fs metadata carries both stages
            if stage == "cs":
                s = d["stages"]["compute"]; m = d["own_main_code"]["compute"]
            else:
                target = "vertex" if stage == "vs" else "fragment"
                s = d["stages"][target]; m = d["own_main_code"][target]
            parsed.update({"status": "OK", "gpr_field_0": s["gpr_field_0"],
                           "scratch_field_41_or_14": s["scratch_field_41_or_14"],
                           "all_u32_fields": s["all_u32_fields"],
                           "main_bytes": m["bytes"], "main_sha256": m["sha256"]})
        except Exception as e:  # noqa: BLE001
            parsed["status"] = f"PARSE_FAIL:{type(e).__name__}"
    elif not timed_out:
        if "exceeds available stack space" in (cp.stderr or ""):
            parsed["status"] = "PIPELINE_FAIL_STACK_SPACE"
        elif "compile" in (cp.stderr or "").lower():
            parsed["status"] = "COMPILE_FAIL"
        else:
            parsed["status"] = "FAIL"
    return parsed, {"exit": None if timed_out else cp.returncode, "timed_out": timed_out,
                    "exception": exc, "duration_ms": dur, "stdout": cp.stdout, "stderr": cp.stderr}


def parse_probe_stdout(stdout):
    status, detail, checksum = "NO_STATUS", None, None
    for line in (stdout or "").splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("DETAIL "):
            detail = line.split(None, 1)[1].strip()
        elif line.startswith("RESULT "):
            m = re.search(r"checksum=(\S+)", line)
            if m:
                checksum = m.group(1)
    return status, detail, checksum


def run_probe(case, maptrace, probe, timeout, dump_root):
    source = HERE / "kernels" / case["source"]
    argv = [str(probe), "--stage", case["stage"], "--source", str(source), "--k", str(case["k"])]
    if case["grid"] is not None:
        argv += ["--grid", str(case["grid"]), "--tg", str(case["tg"])]
    argv += ["--n", str(case["n"])]
    dump_dir = dump_root / case["name"]
    log_path = dump_root / f"{case['name']}.maptrace.log"
    env = os.environ.copy()
    env.update({"DYLD_INSERT_LIBRARIES": str(maptrace), "MAPTRACE_LOG": str(log_path),
               "MAPTRACE_DUMP_DIR": str(dump_dir), "MAPTRACE_PREFIX_CAP": "16384",
               "MAPTRACE_DUMP_GPU_VAS": ""})
    t0 = time.monotonic()
    try:
        cp = subprocess.run(argv, cwd=HERE, capture_output=True, text=True, timeout=timeout, env=env)
        dur = int((time.monotonic() - t0) * 1000)
        timed_out, exc = False, None
        exit_code, stdout, stderr = cp.returncode, cp.stdout, cp.stderr
    except subprocess.TimeoutExpired as e:
        dur = int((time.monotonic() - t0) * 1000)
        timed_out, exc = True, "TimeoutExpired"
        exit_code = None
        stdout = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    status, detail, checksum = parse_probe_stdout(stdout)
    log_text = log_path.read_text() if log_path.is_file() else ""
    maps = TP.parse_resource_maps(log_text)
    shape = TP.resource_map_shape(maps)
    allbo = TP.parse_allbo_dumps(log_text)
    seq = TP.bo_content_sequence(allbo, dump_dir)
    return {
        "status": status, "detail": detail, "checksum": checksum,
        "exit": exit_code, "timed_out": timed_out, "exception": exc, "duration_ms": dur,
        "stdout": stdout, "stderr": stderr, "log_lines": len(log_text.splitlines()),
        "resource_map_shape": shape, "bo_count": len(seq),
        "bo_total_bytes": sum(b["size"] for b in seq),
        "bo_content_seq_sha256": TP.bo_content_seq_sha256(seq),
        "raw_maps": maps,  # kept only in the (ungated) 05_raw_maps.jsonl by the caller
    }


def do_case(case, maptrace, probe, dump_root):
    meta, meta_t = run_metadata(case, CM.TIMEOUTS["metadata"])
    pr = run_probe(case, maptrace, probe, CM.probe_timeout(case), dump_root)
    public = {
        "i": case["i"], "name": case["name"], "family": case["family"], "stage": case["stage"],
        "k": case["k"], "grid": case["grid"], "tg": case["tg"], "n": case["n"],
        "source": case["source"], "executed": True,
        "meta_exit": meta_t["exit"], "meta_timed_out": meta_t["timed_out"], "meta_status": meta["status"],
        "gpr_field_0": meta["gpr_field_0"], "scratch_field_41_or_14": meta["scratch_field_41_or_14"],
        "all_u32_fields": meta["all_u32_fields"], "main_bytes": meta["main_bytes"],
        "main_sha256": meta["main_sha256"],
        "probe_exit": pr["exit"], "probe_timed_out": pr["timed_out"], "probe_status": pr["status"],
        "probe_detail": pr["detail"], "checksum": pr["checksum"],
        "resource_map_shape": pr["resource_map_shape"], "bo_count": pr["bo_count"],
        "bo_total_bytes": pr["bo_total_bytes"], "bo_content_seq_sha256": pr["bo_content_seq_sha256"],
    }
    timing = {"i": case["i"], "name": case["name"],
             "meta_duration_ms": meta_t["duration_ms"], "probe_duration_ms": pr["duration_ms"],
             "meta_stdout": meta_t["stdout"], "meta_stderr": meta_t["stderr"],
             "probe_stdout": pr["stdout"], "probe_stderr": pr["stderr"],
             "maptrace_log_lines": pr["log_lines"]}
    raw_maps = {"i": case["i"], "name": case["name"], "raw_resource_maps": pr["raw_maps"]}
    is_hard_fault = meta_t["timed_out"] or pr["timed_out"] or meta_t["exception"] or pr["exception"]
    is_clean_negative = (not is_hard_fault) and pr["status"] not in ("OK",)
    return public, timing, raw_maps, is_hard_fault, is_clean_negative


def smoke_test(maptrace, probe, scratch_root):
    """NON-RECORDED: runs the smoke case end to end in a throwaway temp
    tree, never under raw/. Returns True/False; never raises past main()."""
    dump_root = scratch_root / "smoke_dumps"
    dump_root.mkdir(parents=True, exist_ok=True)
    try:
        meta, meta_t = run_metadata(SMOKE_CASE, CM.TIMEOUTS["smoke"])
        if meta["status"] != "OK" or meta_t["timed_out"]:
            print("SMOKE FAIL (metadata):", meta, meta_t["stderr"][-500:], file=sys.stderr)
            return False
        pr = run_probe(SMOKE_CASE, maptrace, probe, CM.TIMEOUTS["smoke"], dump_root)
        if pr["status"] != "OK" or pr["timed_out"] or pr["bo_count"] < 1:
            print("SMOKE FAIL (probe):", pr["status"], pr["detail"], pr["stderr"][-500:], file=sys.stderr)
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

    gen = subprocess.run([sys.executable, "-B", "kernels/generate.py"], cwd=HERE,
                         capture_output=True, text=True, timeout=CM.TIMEOUTS["env_command"])
    if gen.returncode:
        raise SystemExit("kernel generation failed:\n" + gen.stderr)
    missing = [s for s in CM.REQUIRED_SOURCES if not (HERE / "kernels" / s).is_file()]
    if missing:
        raise SystemExit("missing generated sources: %s" % missing)

    import tempfile
    work_root = HERE / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="build-", dir=work_root))
    maptrace, probe = build_tools(work)

    # --- NON-RECORDED smoke gate: BEFORE any raw/ artifact exists. ---
    if not smoke_test(maptrace, probe, work):
        raise SystemExit("SMOKE GATE FAILED: no run id burned, no raw/ artifact created")
    print("smoke gate: OK (non-recorded)")

    raw = HERE / "raw" / a.run_id
    if raw.exists():
        raise SystemExit("run id already has a raw/ directory -- run ids are never reused: %s" % raw)
    raw.mkdir(parents=True)
    dump_root = raw / "dumps"
    dump_root.mkdir()
    progress(raw, f"run {a.run_id} started; smoke gate passed; {len(CM.ALL_CASES)} cases queued")

    put(raw / "00_inputs.json", {"run_id": a.run_id, "started_utc":
                                 datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                 "provenance": provenance(), "boundary": BOUNDARY,
                                 "case_count": len(CM.ALL_CASES), "families": sorted({c["family"] for c in CM.ALL_CASES})})

    if a.run_id == RUNS[1]:
        prev = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        cur = json.loads((raw / "00_inputs.json").read_text())
        for k in ("authored_code_sha256", "authored_doc_sha256"):
            if prev["provenance"][k] != cur["provenance"][k]:
                raise SystemExit("run02 authored-file hashes differ from run01 (harness changed "
                                 "mid-experiment): " + k)

    case_path, timing_path, raw_maps_path = raw / "02_cases.jsonl", raw / "03_timing.jsonl", raw / "05_raw_maps.jsonl"
    case_path.touch(); timing_path.touch(); raw_maps_path.touch()

    stopped_family = set()
    grace_used = set()
    aborted = False
    for case in CM.ALL_CASES:
        fam = case["family"]
        if fam in stopped_family:
            skip = dict(case); skip["executed"] = False
            for k in ("meta_exit", "meta_timed_out", "meta_status", "gpr_field_0",
                     "scratch_field_41_or_14", "all_u32_fields", "main_bytes", "main_sha256",
                     "probe_exit", "probe_timed_out", "probe_status", "probe_detail", "checksum",
                     "resource_map_shape", "bo_count", "bo_total_bytes", "bo_content_seq_sha256"):
                skip[k] = None
            append_jsonl(case_path, skip)
            progress(raw, f"case {case['name']} SKIPPED (family {fam} escalation-stopped)")
            continue

        public, timing, raw_maps, hard_fault, clean_negative = do_case(case, maptrace, probe, dump_root)
        append_jsonl(case_path, public)
        append_jsonl(timing_path, timing)
        append_jsonl(raw_maps_path, raw_maps)
        progress(raw, f"case {case['name']} done: probe_status={public['probe_status']} "
                     f"meta_status={public['meta_status']} scratch={public['scratch_field_41_or_14']} "
                     f"bo_count={public['bo_count']} hard_fault={hard_fault}")

        if hard_fault:
            progress(raw, f"HARD FAULT/TIMEOUT at case {case['name']}: aborting entire remaining run")
            aborted = True
            break
        if fam in CM.FAMILIES_ESCALATING and clean_negative:
            if fam == "K" and fam not in grace_used:
                grace_used.add(fam)  # allow exactly one more K case past the first non-OK
            else:
                stopped_family.add(fam)

    summary = {
        "run_id": a.run_id, "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "aborted_on_hard_fault": aborted,
        "cases_total": len(CM.ALL_CASES),
        "case_sha256": sha(case_path), "timing_sha256": sha(timing_path),
        "raw_maps_sha256": sha(raw_maps_path),
    }
    put(raw / "01_summary.json", summary)
    progress(raw, f"run {a.run_id} finished; aborted={aborted}")
    print(json.dumps(summary, indent=2))
    import shutil
    shutil.rmtree(work, ignore_errors=True)  # build artifacts only (our own compiled binaries); raw/ already has all evidence


if __name__ == "__main__":
    main()
