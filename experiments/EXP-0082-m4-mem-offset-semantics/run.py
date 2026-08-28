#!/usr/bin/env python3
"""EXP-0082 capture runner (successor of EXP-0081; root fix: timing/nondeter-
minism is fully isolated from the byte-compared payload). Never runs a device
operation without --execute.

EXP-0081 captured 2164 cases x2 runs cleanly (see
../EXP-0081-m4-mem-offset-semantics/QUARANTINE.md) but its recorded per-case
payload embedded `GPUTIME_NS` (inside raw `stdout`) and `duration_ms`, both
inherently nondeterministic, inside the SAME record the cross-run
`byte-exact repeat` gate compared -- making that gate unsatisfiable by
construction, no matter how reproducible the actual hardware observation was.
The fix here has three parts:

  1. `parse_agxtest` splits agxtest's stdout into a `semantic` dict (the
     deterministic line-prefixes the tool emits: MAIN_LEN, DEVICE, FUNCTION,
     PIPELINE_SOURCE, STATUS, OUT, and a content hash of RESULT) and a
     separate `gputime_ns` scalar. GPUTIME_NS -- and empirically, per
     EXP-0081's own raw data, the free-text wording of an agxrun ERROR
     diagnostic for the SAME deterministic CMDBUF_ERROR fault, which differed
     between its two runs ("Discarded (victim of GPU error/recovery)" vs
     "Caused GPU Hang Error") -- never enters `semantic`.
  2. `run_one_case` returns TWO records per case: `public` (CASE_KEYS, written
     to `04_results.jsonl`, the ONLY file the cross-run byte-exact gate
     compares) and `timing` (TIMING_KEYS, written to the SIBLING
     `04_timing.jsonl`, schema-checked every run but never byte-compared
     across runs).
  3. verify.py's `--selftest` gains a fixture (`cross_run_timing_only_diff_
     passes`) proving `gate_captured` PASSES for two synthetic runs whose
     `04_timing.jsonl` differ arbitrarily while `04_results.jsonl` is
     identical, alongside the pre-existing (and extended) fixtures proving it
     FAILS on any semantic-field difference.

Per case: ONE field-family change to ONE probe instruction of OUR OWN compiled
kernel, re-assembled with tools/agx-isa (assemble(decode(bytes)+override)),
spliced via tools/agxtest/agxtest.py into the binary archive of our own MSL,
executed by tools/agxtest/agxrun in a FRESH process on the local M4 under a
hard timeout, output read back and decoded. A fault, hang or timeout is a
RESULT: it is recorded and the sweep continues in a fresh process; nothing is
retried in place.

Schema constants (RUNS, AUTH_*, TIMEOUTS, key sets) are the single source of
truth; verify.py imports them from here rather than restating them.

Execution is single-threaded and synchronous: one case at a time, each agxtest
invocation is a blocking subprocess, and every raw record line is flushed to
disk before the next case starts.
"""
import argparse, datetime, hashlib, json, platform, shutil, struct, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0082-m4-mem-offset-semantics"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb            # noqa: E402  (read-only use)
import casematrix as CM  # noqa: E402
import baseline as BL   # noqa: E402

RUNS = ("m4-20260828-run01", "m4-20260828-run02")

BOUNDARY = ("public Metal API only; runtime MSL compile of our own kernels; binary-archive "
            "splice of our own compiled shader bytes re-assembled with tools/agx-isa; "
            "owned shared buffers; every case a fresh process; no Apple binary, archive, BO "
            "or command-stream inspection beyond our own compiled shader bytes")

TIMEOUTS = {"env_command": 10, "host_build": 60, "baseline": 180,
            "case_process": 120, "smoke_process": 120}

AUTH_CODE = ("kernels/ld_bank.metal", "kernels/st_bank.metal", "harness/build.sh",
             "baseline.py", "casematrix.py", "run.py", "analysis.py",
             "make_manifest.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")

# authoritative record key sets (imported by verify.py; never restated there)
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
            "stdout", "stderr", "exception"}
DISPATCH_KEYS = {"argv", "cwd", "started_utc", "finished_utc", "duration_seconds",
                 "n_cases", "status_counts", "results_sha256", "results_lines",
                 "timing_sha256", "timing_lines"}
# CASE_KEYS: the byte-gated semantic payload. NOTHING nondeterministic lives
# here -- no timing, no duration, no raw stdout/stderr (the EXP-0081 defect).
CASE_KEYS = {"i", "name", "item", "kernel", "idx", "splice_args", "probe_before",
             "probe_after", "changed_bytes", "exit", "timed_out", "exception",
             "status", "pipeline_source", "main_len", "device", "function",
             "out0_hex", "extra_hex", "result_sha256", "decoded", "raw_note"}
# TIMING_KEYS: every nondeterministic field lives HERE, in the sibling
# 04_timing.jsonl -- schema-checked every run, never byte-compared across runs.
TIMING_KEYS = {"i", "name", "duration_ms", "gputime_ns", "stdout_raw", "stderr_raw"}

SMOKE_CASE = {"name": "smoke_ld_off1_idx64", "item": "SMOKE", "kernel": "ld",
              "idx": [64, 0, 77, 909], "fields": {"idx_off": 1},
              "pred": {}, "note": "non-recorded scratch case (shape only)"}


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


# ---------------------------------------------------------------------------
# probe-instruction splice construction (single field-family change per case)
# ---------------------------------------------------------------------------
FIELD_BYTES = {"idx_off": {9, 10, 11}, "elem_size": {12}, "index_reg": {5},
               "space": {1}, "access_desc": {6}, "ldform_hi11": {11},
               "dst_ext9": {9}, "st_format_ext": {9}, "st_desc_hi": {11}}


def splice_case(probe_hex, fields, main_offset):
    """Decode the frozen probe instruction, apply ONE field-family override set,
    re-assemble with our DB. Returns (new_hex, splice_args, changed_bytes).
    splice_args are MAIN-RELATIVE (_agc.main@<main_offset+i>): the smoke gate
    proved instruction-relative offsets splice the wrong bytes. This is the
    single definition used by the runner, the verifier, and the synthetic-tree
    builder (the EXP-0080 defect was generator/checker disagreement about it)."""
    base = bytes.fromhex(probe_hex)
    recd, _ = isadb.decode_one(base)
    assert isadb.assemble(recd["mnemonic"], recd["fields"]) == base
    flds = dict(recd["fields"])
    flds.update(fields)
    new = isadb.assemble(recd["mnemonic"], flds)
    changed = [i for i in range(len(base)) if base[i] != new[i]]
    allowed = set()
    for k in fields:
        allowed |= FIELD_BYTES[k]
    assert set(changed) <= allowed, "field splice leaked outside its byte range: %s" % changed
    args = ["_agc.main@%d=%02x" % (main_offset + i, new[i]) for i in changed]
    return new.hex(), args, changed


def agxtest_argv(shared, case):
    src = HERE / ("kernels/%s_bank.metal" % case["kernel"])
    argv = [sys.executable, "-B", str(REPO / "tools" / "agxtest" / "agxtest.py"),
            "--source", src, "--function", "k", "--grid", "1", "--tg", "1",
            "--no-fast-math", "--int",
            "--shdump", shared / "bin" / "shdump",
            "--agxrun", shared / "bin" / "agxrun",
            "--agxparse", REPO / "tools" / "shdump" / "agxparse.py",
            "--workdir", shared, "--run-timeout", TIMEOUTS["case_process"]]
    if case["kernel"] == "ld":
        argv += ["--buf", "2=@%s" % (shared / "a.bin"),
                 "--buf", "3=@%s" % (shared / "idx.bin"),
                 "--out", "0=1", "--out", "1=1"]
    else:
        argv += ["--buf", "3=@%s" % (shared / "idx.bin"),
                 "--out", "0=1", "--out", "1=%d" % CM.TGT_WORDS]
    for sp in case.get("splice_args", []):
        argv += ["--splice", sp]
    return argv


def parse_agxtest(stdout):
    """Split agxtest stdout into (semantic, gputime_ns).

    `semantic` carries ONLY the deterministic line-prefixes the tool emits on
    a normal run -- MAIN_LEN, DEVICE, FUNCTION, PIPELINE_SOURCE, STATUS,
    OUT <idx> <hex> (0/1) -- plus `result_sha256`, a content hash of every
    `RESULT <idx> ...` line in original order (RESULT is the tool's decimal
    echo of OUT; for the store probe's full 8 KiB readback it would otherwise
    duplicate a large, fully redundant value inside the gated record, so its
    exact content is compared via hash instead of stored twice).

    `GPUTIME_NS` -- the tool's own per-dispatch GPU timer -- is inherently
    nondeterministic and is returned separately; it never enters `semantic`.
    Free-text lines the tool can also emit (`ERROR` diagnostics, `SPLICE`
    echo) are OMITTED from `semantic` on purpose: EXP-0081's raw evidence
    showed the exact wording of an `ERROR` line for the SAME deterministic
    `CMDBUF_ERROR` fault is NOT byte-stable across runs (see PRE_REGISTRATION.md)
    -- it is a nondeterministic field by the same rule that excludes
    GPUTIME_NS, not a semantic outcome. Both are preserved uncompared in the
    timing/diagnostic record (see run_one_case)."""
    sem = {"status": "NO_STATUS", "pipeline_source": None, "main_len": None,
           "device": None, "function": None, "out0_hex": None, "extra_hex": None}
    result_lines = []
    gputime_ns = None
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            sem["status"] = line.split(None, 1)[1].strip()
        elif line.startswith("PIPELINE_SOURCE"):
            sem["pipeline_source"] = line.split(None, 1)[1].strip()
        elif line.startswith("MAIN_LEN "):
            try:
                sem["main_len"] = int(line.split()[1])
            except (IndexError, ValueError):
                pass
        elif line.startswith("DEVICE "):
            sem["device"] = line.split(None, 1)[1].strip()
        elif line.startswith("FUNCTION "):
            sem["function"] = line.split(None, 1)[1].strip()
        elif line.startswith("RESULT "):
            result_lines.append(line)
        elif line.startswith("GPUTIME_NS "):
            try:
                gputime_ns = int(line.split()[1])
            except (IndexError, ValueError):
                pass
        elif line.startswith("OUT "):
            parts = line.split(None, 2)
            if len(parts) == 3:
                _, idx, hexb = parts
                if idx == "0":
                    sem["out0_hex"] = hexb.strip()
                elif idx == "1":
                    sem["extra_hex"] = hexb.strip()
    sem["result_sha256"] = hashlib.sha256("\n".join(result_lines).encode()).hexdigest()
    return sem, gputime_ns


_EMPTY_SEM = {"status": "NO_STATUS", "pipeline_source": None, "main_len": None,
              "device": None, "function": None, "out0_hex": None, "extra_hex": None,
              "result_sha256": hashlib.sha256(b"").hexdigest()}


def run_one_case(shared, case, probe_hex_map, probe_off_map, timeout):
    """Execute one case in a fresh process. Returns (public, timing, sem):
    `public` is the byte-gated semantic record (CASE_KEYS; written to
    04_results.jsonl, required identical across run01/run02); `timing` carries
    every nondeterministic field (wall/GPU timing, raw stdout/stderr) into the
    SEPARATE, non-cross-run-gated 04_timing.jsonl -- never mixed back into
    `public` (the EXP-0081 quarantine class)."""
    i = case["i"]
    probe_hex = probe_hex_map[case["kernel"]]
    poff = probe_off_map[case["kernel"]]
    new_hex, sp_args, changed = splice_case(probe_hex, case["fields"], poff)
    c = dict(case)
    c["splice_args"] = sp_args
    (shared / "idx.bin").write_bytes(CM.fill_idx(case["idx"]))
    argv = agxtest_argv(shared, c)
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    if r["stdout"]:
        sem, gputime_ns = parse_agxtest(r["stdout"])
    else:
        sem, gputime_ns = dict(_EMPTY_SEM), None
    decoded = None
    raw_note = ""
    if sem.get("status") == "OK" and sem.get("out0_hex"):
        try:
            v = int.from_bytes(bytes.fromhex(sem["out0_hex"][:8]), "little")
            if case["kernel"] == "ld":
                d = CM.decode_load_value(v)
                decoded = {"byte_offset": d[0], "word": d[1], "residue": d[2],
                           "ambiguous": d[3]} if d else None
                raw_note = "undecodable" if d is None else ""
            else:
                # st: extra_hex is the whole tgt buffer; decode the store window
                hb = bytes.fromhex(sem["extra_hex"]) if sem.get("extra_hex") else b""
                words = list(struct.unpack("<%dI" % (len(hb) // 4), hb)) if hb else []
                d = CM.decode_store_diff(words)
                decoded = d
        except ValueError as e:
            decoded = None
            raw_note = "parse_error:%s" % e
    extra_hex_out = None if case["kernel"] == "st" or not sem.get("extra_hex") \
        or len(sem.get("extra_hex") or "") > 64 else sem["extra_hex"]
    public = {"i": i, "name": case["name"], "item": case["item"], "kernel": case["kernel"],
              "idx": ["0x%08X" % (v & 0xFFFFFFFF) for v in case["idx"]],
              "splice_args": sp_args, "probe_before": probe_hex, "probe_after": new_hex,
              "changed_bytes": changed, "exit": r["exit"], "timed_out": r["timed_out"],
              "exception": r["exception"],
              "status": sem.get("status", "NO_STATUS"),
              "pipeline_source": sem.get("pipeline_source"),
              "main_len": sem.get("main_len"), "device": sem.get("device"),
              "function": sem.get("function"),
              "out0_hex": sem.get("out0_hex"), "extra_hex": extra_hex_out,
              "result_sha256": sem["result_sha256"],
              "decoded": decoded, "raw_note": raw_note}
    timing = {"i": i, "name": case["name"], "duration_ms": dur, "gputime_ns": gputime_ns,
              "stdout_raw": r["stdout"], "stderr_raw": r["stderr"]}
    return public, timing, sem


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
        # clean pre-capture stop with NO burned run id (EXP-0077's lesson).
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
        probe_hex_map = {k: derivation["kernels"][k]["probe_hex"] for k in ("ld", "st")}
        probe_off_map = {k: derivation["kernels"][k]["probe_main_offset"] for k in ("ld", "st")}

        # shared input files (written once; idx.bin is rewritten per case)
        (shared / "a.bin").write_bytes(CM.fill_a())

        # --- NON-RECORDED smoke gate: build+splice+run ONE scratch case -------
        smoke_rc, _smoke_timing, _smoke_sem = run_one_case(
            shared, dict(SMOKE_CASE, i=-1), probe_hex_map, probe_off_map,
            TIMEOUTS["smoke_process"])
        smoke_ok = (smoke_rc["status"] == "OK"
                    and smoke_rc["pipeline_source"] == "archive"
                    and isinstance(smoke_rc["out0_hex"], str) and len(smoke_rc["out0_hex"]) >= 8
                    and smoke_rc["decoded"] is not None
                    and len(smoke_rc["splice_args"]) == 1
                    and not smoke_rc["timed_out"])
        if not smoke_ok:
            print(json.dumps({"pre_capture_stop": "smoke_gate",
                              "smoke_record": {k: smoke_rc[k] for k in
                                               ("status", "pipeline_source", "out0_hex",
                                                "decoded", "splice_args", "timed_out",
                                                "exit", "exception")}}, indent=2))
            raise SystemExit(3)

        # --- PHASE 2: the append-only capture -----------------------------------
        raw.mkdir(parents=True)
        results_path = raw / "04_results.jsonl"
        timing_path = raw / "04_timing.jsonl"
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
            "cases": [{"i": c["i"], "name": c["name"], "item": c["item"],
                       "kernel": c["kernel"],
                       "idx": ["0x%08X" % (v & 0xFFFFFFFF) for v in c["idx"]],
                       "fields": {k: c["fields"][k] for k in sorted(c["fields"])},
                       "pred": {k: c["pred"][k] for k in sorted(c["pred"])},
                       "note": c["note"]} for c in cases]})
        put(raw / "02_build.json", {"schema": 1, "harness_build": build, "baseline": base})

        # --- the frozen sweep --------------------------------------------------
        status_counts = {}
        try:
            with results_path.open("a") as rf, timing_path.open("a") as tf:
                for c in cases:
                    public, timing, _sem = run_one_case(shared, c, probe_hex_map,
                                                         probe_off_map,
                                                         TIMEOUTS["case_process"])
                    assert set(public) == CASE_KEYS
                    assert set(timing) == TIMING_KEYS
                    rf.write(json.dumps(public, sort_keys=True) + "\n")
                    rf.flush()
                    tf.write(json.dumps(timing, sort_keys=True) + "\n")
                    tf.flush()
                    status_counts[public["status"]] = status_counts.get(public["status"], 0) + 1
        except Exception as e:            # harness defect mid-sweep: stop cleanly
            put(raw / "STOP.json", {"schema": 1, "phase": "dispatch_loop",
                                    "automatic_retry": False,
                                    "error": "%s: %s" % (type(e).__name__, e),
                                    "cases_completed": sum(status_counts.values())})
            return

        results_lines = sum(1 for _ in results_path.open("rb"))
        timing_lines = sum(1 for _ in timing_path.open("rb"))
        dispatch = {"argv": [sys.executable] + sys.argv,
                    "cwd": str(HERE), "started_utc": started_utc,
                    "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "duration_seconds": round(time.monotonic() - t0, 3),
                    "n_cases": len(cases), "status_counts": status_counts,
                    "results_sha256": sha(results_path),
                    "results_lines": results_lines,
                    "timing_sha256": sha(timing_path),
                    "timing_lines": timing_lines}
        assert set(dispatch) == DISPATCH_KEYS
        put(raw / "03_dispatch.json", dispatch)
        if results_lines != len(cases) or timing_lines != len(cases):
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
            "kernel_ld_sha256": sha(HERE / "kernels" / "ld_bank.metal"),
            "kernel_st_sha256": sha(HERE / "kernels" / "st_bank.metal"),
            "baseline_sha256": sha(work / "baseline.json"),
            "cases_sha256": sha(raw / "01_cases.json"),
            "results_sha256": dispatch["results_sha256"],
            "probe_hex": probe_hex_map, "probe_main_offset":
            {k: probe_off_map[k] for k in ("ld", "st")}})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if subprocess.run([sys.executable, "-B", "make_manifest.py", "--write"],
                      cwd=HERE).returncode:
        raise SystemExit("make_manifest --write failed after capture")


if __name__ == "__main__":
    main()
