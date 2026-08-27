#!/usr/bin/env python3
"""EXP-0076 capture runner. Never runs a device operation without --execute.

Each case is ONE fresh harness process (fresh device, library, pipeline,
buffers, queue, command buffer). The runner records the environment, the host
build, the complete frozen case matrix, one process receipt per case, and one
authoritative observation line per case into an append-only raw tree.

Harness/process discipline (lessons from EXP-0072/0073/0074, all applied):
  * --selftest must pass immediately before the run gate (no capture under an
    unproven verifier);
  * ONE authoritative record schema: verify.py imports every key set and
    constant from this module, so the runner and the verifier cannot disagree;
  * the harness is single-threaded and synchronous with a flushed, error-checked
    exit, so a record cannot be truncated by a racing exit;
  * a contract-named NON-RECORDED smoke invocation runs one scratch case
    (load_w32_align_in) into work/ BEFORE the append-only raw tree is created;
    a payload-shape or truncation defect is therefore a PRE-CAPTURE stop
    (EXP-0075 refinement of the EXP-0074 gate: raw/ is not burned).

Case-fault discipline (specific to this experiment): out-of-allocation access
is exactly the unknown under test, so a faulted, hung, or killed case is a
RESULT. It is recorded with status watchdog/proc_fail/proc_timeout and never
retried in place; the loop always continues with the next case in a fresh
process. Only three consecutive OS-level spawn failures (the machine itself
failing to start processes) stop the run.
"""
import argparse, datetime, hashlib, json, platform, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0076-m4-buffer-robustness-matrix"

RUNS = ("m4-20260827-run01", "m4-20260827-run02")

BOUNDARY = ("public Metal API; runtime MSL compile with fastMathEnabled=NO and mathMode=Safe; "
            "owned shared buffers sized exactly; no binary/archive/BO/compiled-shader-byte inspection")

TIMEOUTS = {"env_command": 10, "host_build": 60, "library_compile": 120,
            "dispatch_readback": 100, "case_process": 120}

AUTH_CODE = ("kernels/robustness_matrix.metal", "harness/probe.m", "run.py",
             "analysis.py", "make_manifest.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")

# ---- frozen buffer geometry and byte patterns (single source of truth) -------
GEOMETRY = {
    "main_bytes": 64,            # exact owned-buffer length; no slack
    "guard_bytes": 256,          # adjacent allocation before (G1) and after (G2)
    "result_payload_bytes": 32,  # zeroed payload between 64-byte result guards
    "result_guard_bytes": 64,
    "guard1_byte": "0x5A",
    "guard2_byte": "0xC3",
    "result_pre_guard_byte": "0x5A",
    "result_post_guard_byte": "0xA5",
    "fill_rule": "F(i) = (0xA5 + 0x1B*i) mod 256 for i in 0..63",
    "store_rule": "S(j) = (0xC7 + j) mod 256 for j in 0..15 (store value bytes, in order)",
    "far_offset": 1088,          # +1 KiB past the end of the 64-byte allocation
    "align_in_offset": 32,
    "mis1_offset": 33,
}

WIDTHS = (1, 2, 4, 8, 16)        # bytes: 8/16/32/64/128-bit accesses
IN_BOUND_CLASSES = ("align_in", "mis1", "mishalf", "last")
STATUS_VALUES = ("ok", "cb_error", "watchdog", "proc_fail", "proc_timeout")
SMOKE_CASE = "load_w32_align_in"
MAX_CONSECUTIVE_INFRA = 3

# One authoritative frozen key set per record slot (imported by verify.py).
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
            "stdout", "stderr", "exception"}
CASE_KEYS = {"i", "name", "op", "width", "off", "status", "exit", "timed_out",
             "cb_status", "err", "obs", "buf_after", "pre_ok", "g1_ok", "g2_ok",
             "res_g0_ok", "res_g1_ok"}
SUMMARY_KEYS = {"schema", "kernel", "op", "width", "off", "device", "registry_id",
                "machine", "os", "fast_math", "math_mode_raw", "language_version_raw",
                "library_compile_seconds", "dispatch_seconds", "command_buffer_status",
                "error", "obs", "buf_after", "pre_ok", "g1_ok", "g2_ok", "res_g0_ok",
                "res_g1_ok"}
DISPATCH_KEYS = {"schema", "run_id", "cases_planned", "cases_recorded", "n_ok",
                 "n_cb_error", "n_watchdog", "n_proc_fail", "n_proc_timeout",
                 "results_lines", "results_sha256"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
               "authored_code_sha256", "authored_doc_sha256", "sw_vers", "xcrun_version",
               "python", "machine", "boundary", "timeouts_seconds", "geometry"}
RECEIPT_LINE_KEYS = REC_KEYS | {"i", "name"}
RUN_MANIFEST_KEYS = {"schema", "run_id", "cases_planned", "cases_recorded",
                     "runner_sha256", "harness_sha256", "kernel_sha256", "matrix_sha256",
                     "results_sha256", "receipts_sha256"}
MATRIX_CASE_KEYS = {"i", "name", "op", "kernel", "width", "off", "cls", "store_hex"}
RAW_FILES = ("00_inputs.json", "01_matrix.json", "02_build.json", "03_dispatch.json",
             "04_results.jsonl", "05_receipts.jsonl", "06_run_manifest.json")


def fill(i):
    return (0xA5 + 0x1B * i) & 0xFF


def store_value_hex(op, _width):
    """Frozen store pattern bytes (or all-zero words for pure loads)."""
    if op == "load":
        return "00" * 16
    return "".join("%02x" % ((0xC7 + j) & 0xFF) for j in range(16))


def offset_classes(w):
    """Frozen offset classes for access width w bytes (allocation = 64 bytes)."""
    cl = [("align_in", GEOMETRY["align_in_offset"])]
    if w >= 2:
        cl.append(("mis1", GEOMETRY["mis1_offset"]))
    if w >= 8:
        cl.append(("mishalf", 32 + w // 2 - 1))       # 35 @ 64-bit, 39 @ 128-bit
    cl.append(("last", 64 - w))                        # last full element in-bounds
    cl.append(("oob1", 64))                            # first element fully OOB
    cl.append(("far", GEOMETRY["far_offset"]))         # +1 KiB past the end
    for c in range(1, w):                              # cross the end by c bytes
        cl.append(("straddle_%d" % c, 64 - w + c))
    return cl


def matrix():
    """Frozen ordered case list; 106 cases. Nothing about it may drift."""
    m = []
    for op in ("load", "store"):
        for w in WIDTHS:
            for cls, off in offset_classes(w):
                m.append({"i": len(m), "name": "%s_w%d_%s" % (op, 8 * w, cls),
                          "op": op, "kernel": "k_%s_w%d" % (op, 8 * w),
                          "width": w, "off": off, "cls": cls,
                          "store_hex": store_value_hex(op, w)})
    for cls, off in (("align_in", 32), ("oob1", 64)):
        m.append({"i": len(m), "name": "axch_w32_%s" % cls, "op": "axch",
                  "kernel": "k_axch_w32", "width": 4, "off": off, "cls": cls,
                  "store_hex": store_value_hex("axch", 4)})
    return m


CASES = matrix()
TOTAL = len(CASES)


def obs_len(width, op):
    return 0 if op == "store" else 2 * max(4, width)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def provenance():
    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, text=True, capture_output=True, check=True).stdout
    exp = git("status", "--porcelain", "--", EXP_REL)
    return {
        "git_revision": git("rev-parse", "HEAD").strip(),
        "git_dirty": git("status", "--porcelain").strip() != "",
        "experiment_tree_dirty_entries": len([l for l in exp.splitlines() if l.strip()]),
        "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
        "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC},
    }


def put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def rec(argv, timeout, cwd=HERE):
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


def build_argv(work_dir):
    return ["xcrun", "clang", "-fobjc-arc", "-Wno-deprecated-declarations",
            "-o", work_dir / "probe", HERE / "harness/probe.m",
            "-framework", "Metal", "-framework", "Foundation"]


def case_argv(work_dir, c):
    return [work_dir / "probe", "--source", HERE / "kernels/robustness_matrix.metal",
            "--kernel", c["kernel"], "--op", c["op"], "--width", str(c["width"]),
            "--offset", str(c["off"]), "--store-hex", c["store_hex"]]


def _hex_ok(s, n):
    return isinstance(s, str) and len(s) == n and all(ch in "0123456789abcdef" for ch in s)


def case_line(c, z):
    """Build the one authoritative observation line for case c from receipt z.

    Pure function (used unchanged by verify.py's selftest). Hardware-level
    anomalies (command-buffer error, watchdog, kill, timeout) map to recorded
    statuses; only harness-level defects (echo mismatch, malformed record)
    raise, because those mean the record itself is untrustworthy.
    """
    line = {k: None for k in CASE_KEYS}
    line.update({"i": c["i"], "name": c["name"], "op": c["op"], "width": c["width"],
                 "off": c["off"], "exit": z["exit"], "timed_out": z["timed_out"]})
    if z["timed_out"]:
        line.update({"status": "proc_timeout", "cb_status": None, "err": None,
                     "obs": "", "buf_after": ""})
        return line
    if z["exception"] is not None or z["exit"] is None:
        line.update({"status": "proc_fail", "cb_status": None, "err": None,
                     "obs": "", "buf_after": ""})
        return line
    p = None
    try:
        q = json.loads(z["stdout"])
        if isinstance(q, dict):
            p = q
    except ValueError:
        p = None
    if p is None:
        if z["exit"] in (97, 98):
            line.update({"status": "watchdog", "cb_status": None, "err": None,
                         "obs": "", "buf_after": ""})
        else:
            line.update({"status": "proc_fail", "cb_status": None, "err": None,
                         "obs": "", "buf_after": ""})
        return line
    if set(p) != SUMMARY_KEYS \
            or p["schema"] != 1 or p["kernel"] != c["kernel"] or p["op"] != c["op"] \
            or p["width"] != c["width"] or p["off"] != c["off"] \
            or not _hex_ok(p["obs"], obs_len(c["width"], c["op"])) \
            or not _hex_ok(p["buf_after"], 128) \
            or not all(isinstance(p[k], bool) for k in
                       ("pre_ok", "g1_ok", "g2_ok", "res_g0_ok", "res_g1_ok")) \
            or not isinstance(p["command_buffer_status"], int) or not isinstance(p["error"], str):
        raise SystemExit("harness record defect for case %s: shape mismatch" % c["name"])
    line.update({"status": "ok" if p["command_buffer_status"] == 4 else "cb_error",
                 "cb_status": p["command_buffer_status"], "err": p["error"],
                 "obs": p["obs"], "buf_after": p["buf_after"],
                 "pre_ok": p["pre_ok"], "g1_ok": p["g1_ok"], "g2_ok": p["g2_ok"],
                 "res_g0_ok": p["res_g0_ok"], "res_g1_ok": p["res_g1_ok"]})
    return line


def smoke_problems(z, c):
    """Pre-capture smoke validator (pure; exercised by verify.py --selftest).

    Asserts RECORD SHAPE ONLY -- no value expectation on obs/buf_after -- so it
    cannot bias the observation. Its failure classes are pre-capture stops.
    """
    bad = []
    if z.get("timed_out") is not False:
        bad.append("smoke invocation timed out")
    if z.get("exception") is not None:
        bad.append("smoke OS exception: %r" % (z.get("exception"),))
    if z.get("exit") != 0:
        bad.append("smoke exit code %r" % (z.get("exit"),))
    out = z.get("stdout") or ""
    try:
        p = json.loads(out)
    except ValueError:
        return bad + ["smoke stdout is not exactly one JSON object (%d bytes)" % len(out)]
    if not isinstance(p, dict):
        return bad + ["smoke stdout is not a JSON object"]
    missing, extra = sorted(SUMMARY_KEYS - set(p)), sorted(set(p) - SUMMARY_KEYS)
    if missing or extra:
        return bad + ["smoke payload key set differs: missing=%s extra=%s" % (missing, extra)]
    if (p["schema"], p["kernel"], p["op"], p["width"], p["off"]) != \
            (1, c["kernel"], c["op"], c["width"], c["off"]):
        bad.append("smoke identity mismatch")
    if p["device"] != "Apple M4" or p["machine"] != "arm64" or not isinstance(p["os"], str) or not p["os"]:
        bad.append("smoke device identity %r/%r" % (p.get("device"), p.get("machine")))
    if p["fast_math"] is not False or p["math_mode_raw"] != 0 \
            or not isinstance(p["language_version_raw"], int):
        bad.append("smoke compile record %r/%r/%r"
                   % (p.get("fast_math"), p.get("math_mode_raw"), p.get("language_version_raw")))
    if p["command_buffer_status"] != 4 or p["error"] != "":
        bad.append("smoke command buffer status %r error %r"
                   % (p.get("command_buffer_status"), p.get("error")))
    if not all(p[k] is True for k in ("pre_ok", "g1_ok", "g2_ok", "res_g0_ok", "res_g1_ok")):
        bad.append("smoke integrity flags %r"
                   % ([(k, p.get(k)) for k in ("pre_ok", "g1_ok", "g2_ok", "res_g0_ok", "res_g1_ok")],))
    if not _hex_ok(p["obs"], obs_len(c["width"], c["op"])):
        bad.append("smoke obs is not %d lowercase hex chars" % obs_len(c["width"], c["op"]))
    if not _hex_ok(p["buf_after"], 128):
        bad.append("smoke buf_after is not 128 lowercase hex chars")
    if not isinstance(p["library_compile_seconds"], (int, float)) \
            or not isinstance(p["dispatch_seconds"], (int, float)) \
            or not isinstance(p["registry_id"], int):
        bad.append("smoke timing/registry grammar")
    return bad


def smoke_gate(work_root):
    c = next(x for x in CASES if x["name"] == SMOKE_CASE)
    d = work_root / "smoke"
    d.mkdir(parents=True)
    z = rec(case_argv(work_root, c), TIMEOUTS["case_process"])
    put(d / "smoke.json", z)
    return smoke_problems(z, c)


def env_problems(env):
    bad = []
    for name in ("sw_vers", "xcrun_version"):
        z = env[name]
        if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
            bad.append("environment command failed: " + name)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ", ".join(RUNS))
    for g in (("--selftest",), ("--preflight" if a.run_id == RUNS[0] else "--between-runs",)):
        if subprocess.run([sys.executable, "-B", "verify.py", g[0]], cwd=HERE).returncode:
            raise SystemExit("run gate failed: " + g[0])
    current = provenance()
    if a.run_id == RUNS[1]:
        first = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        for k in ("git_revision", "git_dirty", "authored_code_sha256", "authored_doc_sha256"):
            if first.get(k) != current[k]:
                raise SystemExit("run02 provenance differs from closed run01: " + k)
    raw = HERE / "raw" / a.run_id
    work_root = HERE / "work"
    work = work_root / a.run_id
    if raw.exists():
        raise SystemExit("append-only raw path already exists")
    if work.exists() or (work_root.exists() and any(work_root.iterdir())):
        raise SystemExit("scratch path already exists or work is not empty")
    work.mkdir(parents=True)
    # --- everything up to raw.mkdir() is PRE-CAPTURE: a failure here writes a
    # retained work/<run-id>/STOP.json and never creates the append-only tree.
    try:
        env = {"schema": 1, **current,
               "sw_vers": rec(["sw_vers"], TIMEOUTS["env_command"]),
               "xcrun_version": rec(["xcrun", "--version"], TIMEOUTS["env_command"]),
               "python": sys.version.split()[0], "machine": platform.machine(),
               "boundary": BOUNDARY, "timeouts_seconds": TIMEOUTS, "geometry": GEOMETRY}
        if env_problems(env):
            put(work / "STOP.json", {"schema": 1, "phase": "environment",
                                     "problems": env_problems(env),
                                     "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: environment")
        build = rec(build_argv(work), TIMEOUTS["host_build"])
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None:
            put(work / "STOP.json", {"schema": 1, "phase": "host_build",
                                     "problems": ["host build failed"], "receipt": build,
                                     "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: host build")
        problems = smoke_gate(work)
        if problems:
            put(work / "STOP.json", {"schema": 1, "phase": "pre_capture_smoke",
                                     "case": SMOKE_CASE, "problems": problems,
                                     "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: smoke gate (raw tree not created; "
                             "pre-capture repair authorized)")

        # The smoke gate passed: the capture may begin (append-only from here).
        raw.mkdir(parents=True)
        put(raw / "00_inputs.json", env)
        put(raw / "01_matrix.json", {"schema": 1, "run_id": a.run_id, "cases": CASES})
        put(raw / "02_build.json", build)

        lines, receipts = [], []
        infra = 0
        stopped = None
        for c in CASES:
            z = rec(case_argv(work, c), TIMEOUTS["case_process"])
            line = case_line(c, z)
            lines.append(json.dumps(line, sort_keys=True))
            receipts.append(json.dumps({"i": c["i"], "name": c["name"], **z}, sort_keys=True))
            if z["exception"] is not None:
                infra += 1
                if infra >= MAX_CONSECUTIVE_INFRA:
                    stopped = {"schema": 1, "phase": "consecutive_infra_failures",
                               "at_case": c["name"], "automatic_retry": False}
                    break
            else:
                infra = 0

        results_txt = "\n".join(lines) + "\n"
        receipts_txt = "\n".join(receipts) + "\n"
        (work / "results.jsonl").write_text(results_txt)
        (work / "receipts.jsonl").write_text(receipts_txt)
        counts = {s: sum(1 for l in lines if json.loads(l)["status"] == s)
                  for s in STATUS_VALUES}
        put(raw / "03_dispatch.json", {
            "schema": 1, "run_id": a.run_id, "cases_planned": TOTAL,
            "cases_recorded": len(lines), **{"n_%s" % s: counts[s] for s in STATUS_VALUES},
            "results_lines": len(lines), "results_sha256": sha(work / "results.jsonl")})
        shutil.move(str(work / "results.jsonl"), str(raw / "04_results.jsonl"))
        shutil.move(str(work / "receipts.jsonl"), str(raw / "05_receipts.jsonl"))
        put(raw / "06_run_manifest.json", {
            "schema": 1, "run_id": a.run_id, "cases_planned": TOTAL,
            "cases_recorded": len(lines), "runner_sha256": sha(HERE / "run.py"),
            "harness_sha256": sha(HERE / "harness/probe.m"),
            "kernel_sha256": sha(HERE / "kernels/robustness_matrix.metal"),
            "matrix_sha256": sha(raw / "01_matrix.json"),
            "results_sha256": sha(raw / "04_results.jsonl"),
            "receipts_sha256": sha(raw / "05_receipts.jsonl")})
        if stopped is not None:
            put(raw / "STOP.json", stopped)
    finally:
        if not (work / "STOP.json").exists():
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
