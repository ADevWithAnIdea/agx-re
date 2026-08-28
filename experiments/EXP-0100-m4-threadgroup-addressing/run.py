#!/usr/bin/env python3
"""EXP-0100 capture runner. Never runs a device operation without --execute.

Two independent case families sharing one contract, one pair of append-only
runs, and one gate set (methodology copied from
../EXP-0082-m4-mem-offset-semantics/run.py):

  * SPLICE cases (casematrix.CASES, 3 kernels: tga/tg_ld/tg_st) -- ONE
    field-family byte splice into a frozen probe instruction, re-assembled
    with tools/agx-isa where the field is real (b3/b4/b5, idx_off, elem_size,
    index_reg, space) or by DIRECT RAW BYTE PATCH where it is not (tga's
    byte0/byte+1/byte+2, which tools/agx-isa's `match` clause pins and its
    assembler therefore cannot vary -- a first-class tooling-gap finding, not
    a shortcut). Executed via tools/agxtest/agxtest.py exactly as EXP-0082.
  * BUDGET cases (casematrix.BUDGET_CASES) -- a public-Metal boundary sweep,
    NO splicing: each case compiles a fresh, argv-parametrized kernel via
    harness/tgbudget.m (own-MSL, public Metal API only) and reports
    compile/pipeline/dispatch status plus a full-range fill+verify byte
    count.

Every nondeterministic field (wall time, GPU time, raw stdout/stderr) lives
in a SEPARATE, non-cross-run-gated timing file per family (the EXP-0081/0082
root fix, reused unchanged here): 04_results.jsonl / 04_timing.jsonl for
SPLICE, 06_budget_results.jsonl / 06_budget_timing.jsonl for BUDGET.

Execution is single-threaded and synchronous: one case at a time, one
subprocess per case, every raw record line flushed to disk before the next
case starts.
"""
import argparse, datetime, hashlib, json, platform, shutil, struct, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0100-m4-threadgroup-addressing"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb            # noqa: E402  (read-only use)
import casematrix as CM  # noqa: E402

RUNS = ("m4-20260828-run01", "m4-20260828-run02")

BOUNDARY = ("public Metal API only; runtime MSL compile of our own kernels; binary-archive "
            "splice of our own compiled shader bytes re-assembled with tools/agx-isa OR (tga "
            "byte0/byte+1/byte+2 only) direct raw byte patch where the DB's own match clause "
            "pins the byte and its assembler cannot vary it; a separate PUBLIC-Metal-API-only "
            "boundary sweep with no splicing at all (harness/tgbudget.m); owned shared buffers; "
            "every case a fresh process; no Apple binary, archive, BO or command-stream "
            "inspection beyond our own compiled shader bytes")

TIMEOUTS = {"env_command": 10, "host_build": 60, "baseline": 180,
            "case_process": 60, "budget_process": 30, "smoke_process": 60}

AUTH_CODE = ("kernels/tga.metal", "kernels/tg_ld.metal", "kernels/tg_st.metal",
             "harness/build.sh", "harness/tgbudget.m", "baseline.py", "casematrix.py",
             "run.py", "analysis.py", "make_manifest.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")

REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
            "stdout", "stderr", "exception"}
DISPATCH_KEYS = {"argv", "cwd", "started_utc", "finished_utc", "duration_seconds",
                 "n_splice_cases", "n_budget_cases", "splice_status_counts",
                 "budget_status_counts", "results_sha256", "results_lines",
                 "timing_sha256", "timing_lines", "budget_results_sha256",
                 "budget_results_lines", "budget_timing_sha256", "budget_timing_lines"}
# CASE_KEYS: the byte-gated SPLICE semantic payload. Nothing nondeterministic here.
CASE_KEYS = {"i", "name", "item", "kernel", "idx", "splice_args", "probe_before",
             "probe_after", "changed_bytes", "exit", "timed_out", "exception",
             "status", "pipeline_source", "main_len", "device", "function",
             "out0_hex", "extra_hex", "result_sha256", "decoded", "raw_note"}
TIMING_KEYS = {"i", "name", "duration_ms", "gputime_ns", "stdout_raw", "stderr_raw"}
# BUDGET_KEYS: the byte-gated BUDGET semantic payload.
BUDGET_KEYS = {"i", "name", "item", "mode", "static_bytes", "dynamic_bytes", "exit",
               "timed_out", "exception", "compile_status", "pipeline_status",
               "pso_static_tgmem", "dispatch_status", "bad_byte_count", "status"}
BUDGET_TIMING_KEYS = {"i", "name", "duration_ms", "stdout_raw", "stderr_raw"}

SMOKE_SPLICE_CASE = {"name": "smoke_ld_off1_idx64", "item": "SMOKE", "kernel": "tg_ld",
                     "idx": [64, 0, 77, 909], "fields": {"idx_off": 1},
                     "pred": {}, "note": "non-recorded scratch case (shape only)"}
SMOKE_BUDGET_CASE = {"name": "smoke_static_256", "item": "SMOKE", "mode": "static",
                     "static_bytes": 256, "dynamic_bytes": 0,
                     "expect_pipeline_ok": True, "expect_clean": True,
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


# ---------------------------------------------------------------------------
# SPLICE: probe-instruction splice construction. tga uses two mutually
# exclusive mechanisms (raw byte patch OR isadb field override); tg_ld/tg_st
# use isadb exclusively (idx_off/elem_size/index_reg/space are real DB
# fields), exactly as EXP-0082.
# ---------------------------------------------------------------------------
RAW_KEYS = {"raw_byte0_hi", "raw_byte1", "raw_byte2"}
DB_KEYS_TGA = {"b3", "b4", "b5"}


def raw_write_idx_off_wide(base, value):
    """Direct raw byte patch for tg_ld/tg_st bytes+9/10/11, bypassing
    isadb's 11-bit width check on `idx_off`. Treats the COMBINED 17-bit
    region spanning idx_off (global bits 79..89, EXP-0082's established
    layout: byte+9 bit7 = LSB, byte+10 = bits 1..8, byte+11 bits 0..1 =
    bits 9..10) and the adjacent `ldform_hi11` tail (byte+11 bits 2..7) as
    ONE contiguous little-endian-from-bit-79 field, and writes `value`
    (0..0x1FFFF) into it wholesale -- necessarily overwriting `ldform_hi11`
    too for any value >= 2048. This is the ONLY way to construct an
    idx_off-region value the assembler's field mechanism refuses to emit
    (a first-class tooling-gap finding, see casematrix.py)."""
    b = bytearray(base)
    value &= 0x1FFFF
    b[9] = (b[9] & 0x7F) | (((value >> 0) & 1) << 7)
    b[10] = (value >> 1) & 0xFF
    b[11] = (value >> 9) & 0xFF
    return bytes(b)


RAW_WIDE_KEYS = {"idx_off_wide_raw"}


def splice_case(kernel, probe_hex, fields, main_offset):
    base = bytes.fromhex(probe_hex)
    if kernel == "tga":
        used_raw = set(fields) & RAW_KEYS
        used_db = set(fields) & DB_KEYS_TGA
        assert not (used_raw and used_db), "tga: one splice family per case"
        assert used_raw or used_db or not fields, "tga: unknown field key(s) %s" % fields
        new = bytearray(base)
        if "raw_byte0_hi" in fields:
            new[0] = ((fields["raw_byte0_hi"] & 0xF) << 4) | 0x0C
        if "raw_byte1" in fields:
            new[1] = fields["raw_byte1"] & 0xFF
        if "raw_byte2" in fields:
            new[2] = fields["raw_byte2"] & 0xFF
        if used_db:
            recd, _ = isadb.decode_one(bytes(new))
            flds = dict(recd["fields"])
            flds.update({k: v for k, v in fields.items() if k in DB_KEYS_TGA})
            new = bytearray(isadb.assemble(recd["mnemonic"], flds))
        new = bytes(new)
    elif set(fields) & RAW_WIDE_KEYS:
        assert set(fields) <= RAW_WIDE_KEYS, "tg_ld/tg_st: idx_off_wide_raw is exclusive per case"
        new = raw_write_idx_off_wide(base, fields["idx_off_wide_raw"])
    else:
        recd, _ = isadb.decode_one(base)
        flds = dict(recd["fields"])
        flds.update(fields)
        new = isadb.assemble(recd["mnemonic"], flds)
    changed = [i for i in range(len(base)) if base[i] != new[i]]
    args = ["_agc.main@%d=%02x" % (main_offset + i, new[i]) for i in changed]
    return new.hex(), args, changed


def agxtest_argv(shared, case):
    src = HERE / ("kernels/%s.metal" % case["kernel"])
    argv = [sys.executable, "-B", str(REPO / "tools" / "agxtest" / "agxtest.py"),
            "--source", src, "--function", "k", "--no-fast-math",
            "--shdump", shared / "bin" / "shdump",
            "--agxrun", shared / "bin" / "agxrun",
            "--agxparse", REPO / "tools" / "shdump" / "agxparse.py",
            "--workdir", shared, "--run-timeout", TIMEOUTS["case_process"]]
    if case["kernel"] == "tga":
        argv += ["--grid", "256", "--tg", "256",
                 "--buf", "1=@%s" % (shared / "aid.bin"), "--out", "0=256"]
    elif case["kernel"] == "tg_ld":
        argv += ["--grid", "1", "--tg", "1", "--int",
                 "--buf", "2=@%s" % (shared / "a.bin"),
                 "--buf", "3=@%s" % (shared / "idx.bin"),
                 "--out", "0=1", "--out", "1=1"]
    else:  # tg_st
        argv += ["--grid", "1", "--tg", "1", "--int",
                 "--buf", "3=@%s" % (shared / "idx.bin"),
                 "--out", "0=1", "--out", "1=%d" % CM.TGT_WORDS]
    for sp in case.get("splice_args", []):
        argv += ["--splice", sp]
    return argv


def parse_agxtest(stdout):
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


def run_one_splice_case(shared, case, probe_hex_map, probe_off_map, timeout):
    i = case["i"]
    probe_hex = probe_hex_map[case["kernel"]]
    poff = probe_off_map[case["kernel"]]
    new_hex, sp_args, changed = splice_case(case["kernel"], probe_hex, case["fields"], poff)
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
    if sem.get("status") == "OK":
        try:
            if case["kernel"] == "tga":
                decoded = CM.tga_summary(CM.decode_tga_output(sem.get("out0_hex")))
                raw_note = "undecodable" if not decoded.get("decodable") else ""
            elif case["kernel"] == "tg_ld":
                v = int.from_bytes(bytes.fromhex((sem["out0_hex"] or "00000000")[:8]), "little")
                d = CM.decode_load_value(v)
                decoded = ({"byte_offset": d[0], "word": d[1], "residue": d[2],
                           "ambiguous": d[3]} if d else None)
                raw_note = "undecodable" if d is None else ""
            else:  # tg_st
                hb = bytes.fromhex(sem["extra_hex"]) if sem.get("extra_hex") else b""
                words = list(struct.unpack("<%dI" % (len(hb) // 4), hb)) if hb else []
                decoded = CM.decode_store_diff(words)
        except ValueError as e:
            decoded = None
            raw_note = "parse_error:%s" % e
    out0_hex_out = sem.get("out0_hex") if (sem.get("out0_hex") and len(sem["out0_hex"]) <= 64) \
        else None
    extra_hex_out = sem.get("extra_hex") if (sem.get("extra_hex")
                                             and len(sem["extra_hex"]) <= 64) else None
    public = {"i": i, "name": case["name"], "item": case["item"], "kernel": case["kernel"],
              "idx": ["0x%08X" % (v & 0xFFFFFFFF) for v in case["idx"]],
              "splice_args": sp_args, "probe_before": probe_hex, "probe_after": new_hex,
              "changed_bytes": changed, "exit": r["exit"], "timed_out": r["timed_out"],
              "exception": r["exception"],
              "status": sem.get("status", "NO_STATUS"),
              "pipeline_source": sem.get("pipeline_source"),
              "main_len": sem.get("main_len"), "device": sem.get("device"),
              "function": sem.get("function"),
              "out0_hex": out0_hex_out, "extra_hex": extra_hex_out,
              "result_sha256": sem["result_sha256"],
              "decoded": decoded, "raw_note": raw_note}
    timing = {"i": i, "name": case["name"], "duration_ms": dur, "gputime_ns": gputime_ns,
              "stdout_raw": r["stdout"], "stderr_raw": r["stderr"]}
    return public, timing


# ---------------------------------------------------------------------------
# BUDGET: tgbudget.m invocation (no splicing; a fresh compile per case).
# ---------------------------------------------------------------------------
def tgbudget_argv(shared, case):
    return [shared / "bin" / "tgbudget", "--mode", case["mode"],
            "--static-bytes", str(case["static_bytes"]),
            "--dynamic-bytes", str(case["dynamic_bytes"])]


def parse_tgbudget(stdout):
    sem = {"compile_status": None, "pipeline_status": None, "pso_static_tgmem": None,
           "dispatch_status": None, "bad_byte_count": None, "status": "NO_STATUS"}
    for line in stdout.splitlines():
        if line.startswith("COMPILE_STATUS "):
            sem["compile_status"] = line.split(None, 1)[1].strip()
        elif line.startswith("PIPELINE_STATUS "):
            sem["pipeline_status"] = line.split(None, 1)[1].strip()
        elif line.startswith("PSO_STATIC_TGMEM "):
            try:
                sem["pso_static_tgmem"] = int(line.split()[1])
            except (IndexError, ValueError):
                pass
        elif line.startswith("DISPATCH_STATUS "):
            sem["dispatch_status"] = line.split(None, 1)[1].strip()
        elif line.startswith("BAD_BYTE_COUNT "):
            try:
                sem["bad_byte_count"] = int(line.split()[1])
            except (IndexError, ValueError):
                pass
        elif line.startswith("STATUS "):
            sem["status"] = line.split(None, 1)[1].strip()
    return sem


def run_one_budget_case(shared, case, timeout):
    i = case["i"]
    argv = tgbudget_argv(shared, case)
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    sem = parse_tgbudget(r["stdout"]) if r["stdout"] else {
        "compile_status": None, "pipeline_status": None, "pso_static_tgmem": None,
        "dispatch_status": None, "bad_byte_count": None, "status": "NO_STATUS"}
    public = {"i": i, "name": case["name"], "item": case["item"], "mode": case["mode"],
              "static_bytes": case["static_bytes"], "dynamic_bytes": case["dynamic_bytes"],
              "exit": r["exit"], "timed_out": r["timed_out"], "exception": r["exception"],
              "compile_status": sem["compile_status"], "pipeline_status": sem["pipeline_status"],
              "pso_static_tgmem": sem["pso_static_tgmem"],
              "dispatch_status": sem["dispatch_status"], "bad_byte_count": sem["bad_byte_count"],
              "status": sem["status"]}
    timing = {"i": i, "name": case["name"], "duration_ms": dur,
              "stdout_raw": r["stdout"], "stderr_raw": r["stderr"]}
    return public, timing


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
        # --- PHASE 1 (pre-raw): build, baseline, NON-RECORDED smoke gates. -----
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
        probe_hex_map = {k: derivation["kernels"][k]["probe_hex"] for k in ("tga", "tg_ld", "tg_st")}
        probe_off_map = {k: derivation["kernels"][k]["probe_main_offset"]
                         for k in ("tga", "tg_ld", "tg_st")}

        (shared / "a.bin").write_bytes(CM.fill_a())
        (shared / "aid.bin").write_bytes(CM.fill_a_identity_f32())

        smoke_rc, _ = run_one_splice_case(shared, dict(SMOKE_SPLICE_CASE, i=-1),
                                          probe_hex_map, probe_off_map, TIMEOUTS["smoke_process"])
        smoke_ok = (smoke_rc["status"] == "OK" and smoke_rc["pipeline_source"] == "archive"
                   and isinstance(smoke_rc["out0_hex"], str) and len(smoke_rc["out0_hex"]) >= 8
                   and smoke_rc["decoded"] is not None and len(smoke_rc["splice_args"]) == 1
                   and not smoke_rc["timed_out"])
        if not smoke_ok:
            print(json.dumps({"pre_capture_stop": "smoke_gate_splice",
                              "smoke_record": {k: smoke_rc[k] for k in
                                               ("status", "pipeline_source", "out0_hex",
                                                "decoded", "splice_args", "timed_out",
                                                "exit", "exception")}}, indent=2))
            raise SystemExit(3)

        budget_smoke_rc, _ = run_one_budget_case(shared, dict(SMOKE_BUDGET_CASE, i=-1),
                                                  TIMEOUTS["budget_process"])
        budget_smoke_ok = (budget_smoke_rc["status"] == "OK"
                           and budget_smoke_rc["compile_status"] == "OK"
                           and budget_smoke_rc["pipeline_status"] == "OK"
                           and budget_smoke_rc["bad_byte_count"] == 0
                           and not budget_smoke_rc["timed_out"])
        if not budget_smoke_ok:
            print(json.dumps({"pre_capture_stop": "smoke_gate_budget",
                              "smoke_record": budget_smoke_rc}, indent=2))
            raise SystemExit(3)

        # --- PHASE 2: the append-only capture ------------------------------
        raw.mkdir(parents=True)
        results_path = raw / "04_results.jsonl"
        timing_path = raw / "04_timing.jsonl"
        budget_results_path = raw / "06_budget_results.jsonl"
        budget_timing_path = raw / "06_budget_timing.jsonl"
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
        bcases = [dict(c, i=i) for i, c in enumerate(CM.BUDGET_CASES)]
        put(raw / "01_cases.json", {
            "schema": 1, "run_id": a.run_id, "total": len(cases),
            "cases": [{"i": c["i"], "name": c["name"], "item": c["item"],
                       "kernel": c["kernel"],
                       "idx": ["0x%08X" % (v & 0xFFFFFFFF) for v in c["idx"]],
                       "fields": {k: c["fields"][k] for k in sorted(c["fields"])},
                       "note": c["note"]} for c in cases]})
        put(raw / "01b_budget_cases.json", {
            "schema": 1, "run_id": a.run_id, "total": len(bcases),
            "cases": [{"i": c["i"], "name": c["name"], "item": c["item"], "mode": c["mode"],
                       "static_bytes": c["static_bytes"], "dynamic_bytes": c["dynamic_bytes"],
                       "expect_pipeline_ok": c["expect_pipeline_ok"],
                       "expect_clean": c["expect_clean"], "note": c["note"]} for c in bcases]})
        put(raw / "02_build.json", {"schema": 1, "harness_build": build, "baseline": base})

        status_counts = {}
        try:
            with results_path.open("a") as rf, timing_path.open("a") as tf:
                for c in cases:
                    public, timing = run_one_splice_case(shared, c, probe_hex_map,
                                                         probe_off_map, TIMEOUTS["case_process"])
                    assert set(public) == CASE_KEYS
                    assert set(timing) == TIMING_KEYS
                    rf.write(json.dumps(public, sort_keys=True) + "\n"); rf.flush()
                    tf.write(json.dumps(timing, sort_keys=True) + "\n"); tf.flush()
                    status_counts[public["status"]] = status_counts.get(public["status"], 0) + 1
        except Exception as e:
            put(raw / "STOP.json", {"schema": 1, "phase": "splice_dispatch_loop",
                                    "automatic_retry": False,
                                    "error": "%s: %s" % (type(e).__name__, e),
                                    "cases_completed": sum(status_counts.values())})
            return

        budget_status_counts = {}
        try:
            with budget_results_path.open("a") as rf, budget_timing_path.open("a") as tf:
                for c in bcases:
                    public, timing = run_one_budget_case(shared, c, TIMEOUTS["budget_process"])
                    assert set(public) == BUDGET_KEYS
                    assert set(timing) == BUDGET_TIMING_KEYS
                    rf.write(json.dumps(public, sort_keys=True) + "\n"); rf.flush()
                    tf.write(json.dumps(timing, sort_keys=True) + "\n"); tf.flush()
                    budget_status_counts[public["status"]] = \
                        budget_status_counts.get(public["status"], 0) + 1
        except Exception as e:
            put(raw / "STOP.json", {"schema": 1, "phase": "budget_dispatch_loop",
                                    "automatic_retry": False,
                                    "error": "%s: %s" % (type(e).__name__, e),
                                    "cases_completed": sum(budget_status_counts.values())})
            return

        dispatch = {"argv": [sys.executable] + sys.argv, "cwd": str(HERE),
                    "started_utc": started_utc,
                    "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "duration_seconds": round(time.monotonic() - t0, 3),
                    "n_splice_cases": len(cases), "n_budget_cases": len(bcases),
                    "splice_status_counts": status_counts,
                    "budget_status_counts": budget_status_counts,
                    "results_sha256": sha(results_path),
                    "results_lines": sum(1 for _ in results_path.open("rb")),
                    "timing_sha256": sha(timing_path),
                    "timing_lines": sum(1 for _ in timing_path.open("rb")),
                    "budget_results_sha256": sha(budget_results_path),
                    "budget_results_lines": sum(1 for _ in budget_results_path.open("rb")),
                    "budget_timing_sha256": sha(budget_timing_path),
                    "budget_timing_lines": sum(1 for _ in budget_timing_path.open("rb"))}
        assert set(dispatch) == DISPATCH_KEYS
        put(raw / "03_dispatch.json", dispatch)
        if dispatch["results_lines"] != len(cases) or dispatch["timing_lines"] != len(cases) \
                or dispatch["budget_results_lines"] != len(bcases) \
                or dispatch["budget_timing_lines"] != len(bcases):
            put(raw / "STOP.json", {"schema": 1, "phase": "dispatch_loop", "automatic_retry": False})
            return
        item_counts, budget_item_counts = {}, {}
        for c in cases:
            item_counts[c["item"]] = item_counts.get(c["item"], 0) + 1
        for c in bcases:
            budget_item_counts[c["item"]] = budget_item_counts.get(c["item"], 0) + 1
        put(raw / "05_run_manifest.json", {
            "schema": 1, "run_id": a.run_id, "total_splice_cases": len(cases),
            "total_budget_cases": len(bcases),
            "item_counts": dict(sorted(item_counts.items())),
            "budget_item_counts": dict(sorted(budget_item_counts.items())),
            "runner_sha256": sha(HERE / "run.py"),
            "harness_sha256": sha(HERE / "harness" / "build.sh"),
            "tgbudget_sha256": sha(HERE / "harness" / "tgbudget.m"),
            "kernel_tga_sha256": sha(HERE / "kernels" / "tga.metal"),
            "kernel_tg_ld_sha256": sha(HERE / "kernels" / "tg_ld.metal"),
            "kernel_tg_st_sha256": sha(HERE / "kernels" / "tg_st.metal"),
            "baseline_sha256": sha(work / "baseline.json"),
            "cases_sha256": sha(raw / "01_cases.json"),
            "budget_cases_sha256": sha(raw / "01b_budget_cases.json"),
            "results_sha256": dispatch["results_sha256"],
            "budget_results_sha256": dispatch["budget_results_sha256"],
            "probe_hex": probe_hex_map,
            "probe_main_offset": {k: probe_off_map[k] for k in ("tga", "tg_ld", "tg_st")}})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if subprocess.run([sys.executable, "-B", "make_manifest.py", "--write"],
                      cwd=HERE).returncode:
        raise SystemExit("make_manifest --write failed after capture")


if __name__ == "__main__":
    main()
