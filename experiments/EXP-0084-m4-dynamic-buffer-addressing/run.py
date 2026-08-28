#!/usr/bin/env python3
"""EXP-0084 capture runner (MEM-20/21/22 dynamic buffer addressing).

Never runs a device/compiler operation without --execute. Each case is ONE
fresh process (fresh device/library/pipeline/buffers for dispatch cases;
fresh shdump/agxparse/isadb invocation for decode/splice cases). Records the
environment, the host build, the frozen case matrix, one process receipt per
case (05_receipts.jsonl, NOT byte-compared across runs), and one authoritative
GATED observation line per case (04_results.jsonl, byte-compared across runs
-- see `case_line()`, which strips every timing/device/registry/address field
before a record is admitted to that file; the EXP-0081 quarantine lesson).

Harness/process discipline (EXP-0072/0073/0074/0075/0081 lessons, all
applied): --selftest AND --seqtest must pass immediately before any run gate;
ONE authoritative record schema per slot (imported from casematrix.py /
procutil.py, shared with verify.py); harnesses are single-threaded synchronous
with a flushed, error-checked exit; a NON-RECORDED smoke invocation (the
`ctrl_direct_baseline` case) runs into work/ BEFORE the append-only raw tree
is created; a faulted/hung/killed case is a RECORDED result, never retried in
place, and never crashes the run (only 3 consecutive OS-level spawn failures
stop it).
"""
import argparse
import datetime
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0084-m4-dynamic-buffer-addressing"

sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402
from procutil import rec, REC_KEYS  # noqa: E402

RUNS = ("m4-20260827-run01", "m4-20260827-run02")

BOUNDARY = ("public Metal API; runtime MSL compile with fastMathEnabled=NO and mathMode=Safe; "
            "owned shared buffers; dynamic device addresses obtained only via public "
            "MTLBuffer.gpuAddress / MTLArgumentEncoder; tools/shdump + tools/agx-isa (read-only, "
            "imported/invoked, never edited) for decode; tools/agxtest technique (own splice_run "
            "harness) for the splice case; no binary/archive/BO/Apple-code inspection")

TIMEOUTS = {"env_command": 10, "host_build": 90, "smoke_process": 60,
            "dispatch_case_process": 60, "decode_case_process": 90, "splice_case_process": 90}

AUTH_CODE = ("kernels/probes.metal", "kernels/gen_cap_kernels.py", "kernels/cap_kernels.metal",
             "harness/probe.m", "harness/splice_run.m", "harness/build.sh",
             "casematrix.py", "procutil.py", "run.py", "verify.py", "make_manifest.py",
             "analysis/decode_lib.py", "analysis/decode_case.py", "analysis/splice_case.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")
AUTH_TOOLS = ("tools/shdump/shdump.m", "tools/shdump/agxparse.py",
              "tools/agxtest/README.md", "tools/agx-isa/isadb.py", "tools/agx-isa/db.json")

SMOKE_CASE_NAME = CM.SMOKE_CASE_NAME
MAX_CONSECUTIVE_INFRA = 3
STATUS_VALUES = ("ok", "compile_reject", "cb_error", "identification_failed", "baseline_failed",
                 "refuted", "confirmed", "watchdog", "proc_fail", "proc_timeout")

# ---- ONE frozen key set per record slot (imported by verify.py) -----------
DISPATCH_SUMMARY_KEYS = {"schema", "mode", "kernel", "function", "n", "grid", "tg", "sel_u",
                         "k_outlier", "use_resource", "device", "machine", "os", "fast_math",
                         "math_mode_raw", "language_version_raw", "library_compile_seconds",
                         "dispatch_seconds", "compile_ok", "compile_error", "dispatch_ok",
                         "command_buffer_status", "error", "out_hex", "outb_hex", "outsel_hex"}
DISPATCH_CASE_KEYS = {"i", "name", "kind", "mode", "function", "n", "sel", "k", "use_resource",
                      "status", "exit", "timed_out", "compile_ok", "dispatch_ok", "cb_status",
                      "out_hex", "outb_hex", "outsel_hex"}
DECODE_SUMMARY_KEYS = {"schema", "function", "build_ok", "main_len", "preamble_len",
                       "main_leftover_len", "preamble_leftover_len", "n_device_load_main",
                       "n_device_load_preamble", "l1", "l2", "confirmation_ok"}
DECODE_CASE_KEYS = {"i", "name", "kind", "function", "status", "exit", "timed_out", "build_ok",
                    "main_len", "preamble_len", "main_leftover_len", "preamble_leftover_len",
                    "n_device_load_main", "n_device_load_preamble", "confirmation_ok",
                    "l1_base_slot", "l1_index_reg", "l1_addr_mode", "l1_idx_off", "l1_dst_reg",
                    "l1_offset", "l2_base_slot", "l2_index_reg", "l2_addr_mode", "l2_idx_off",
                    "l2_dst_reg", "l2_offset"}
SPLICE_SUMMARY_KEYS = {"schema", "function", "build_ok", "ident", "baseline", "target",
                       "splice_offset_abs", "splice_from", "splice_to", "spliced_result", "outcome"}
SPLICE_CASE_KEYS = {"i", "name", "kind", "function", "status", "exit", "timed_out", "build_ok",
                    "confirmation_ok", "baseline_out_hex", "baseline_outb_hex",
                    "target_index_reg", "other_index_reg", "splice_offset_abs", "splice_from",
                    "splice_to", "spliced_out_hex", "spliced_outb_hex", "outcome"}
RECEIPT_LINE_KEYS = REC_KEYS | {"i", "name", "kind"}
DISPATCH_KEYS = ({"schema", "run_id", "cases_planned", "cases_recorded",
                  "results_lines", "results_sha256"}
                 | {"n_%s" % s for s in STATUS_VALUES})
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
              "authored_code_sha256", "authored_doc_sha256", "authored_tools_sha256",
              "sw_vers", "xcrun_version", "python", "machine", "boundary",
              "timeouts_seconds"}
RUN_MANIFEST_KEYS = {"schema", "run_id", "cases_planned", "cases_recorded",
                     "matrix_sha256", "results_sha256", "receipts_sha256"}
MATRIX_CASE_KEYS = set(CM.CASES[0].keys())
RAW_FILES = ("00_inputs.json", "01_matrix.json", "02_build.json", "03_dispatch.json",
            "04_results.jsonl", "05_receipts.jsonl", "06_run_manifest.json")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


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
        "authored_tools_sha256": {p: sha(REPO / p) for p in AUTH_TOOLS},
    }


# ---------------------------------------------------------------------------
# Per-kind invocation + gated record builder (single source of truth).
# ---------------------------------------------------------------------------
def dispatch_argv(bin_dir, c):
    argv = [bin_dir / "probe", "--mode", c["mode"],
            "--source", HERE / "kernels" / c["source"], "--function", c["function"]]
    if c["n"] >= 0:
        argv += ["--n", str(c["n"])]
    if c["sel"] >= 0:
        argv += ["--sel", str(c["sel"])]
    if c["k"] >= 0:
        argv += ["--k", str(c["k"])]
    if c["use_resource"] >= 0:
        argv += ["--use-resource", str(c["use_resource"])]
    return argv


def decode_argv(bin_dir, work, c):
    return [sys.executable, "-B", HERE / "analysis" / "decode_case.py",
            "--shdump", bin_dir / "shdump", "--source", HERE / "kernels" / c["source"],
            "--function", c["function"], "--work-archive", work / ("decode_%d.bin" % c["i"])]


def splice_argv(bin_dir, work, c):
    return [sys.executable, "-B", HERE / "analysis" / "splice_case.py",
            "--shdump", bin_dir / "shdump", "--splice-run", bin_dir / "splice_run",
            "--source", HERE / "kernels" / c["source"], "--function", c["function"],
            "--work", work / ("splice_%d" % c["i"])]


def _parse_json_stdout(z):
    if z["timed_out"] or z["exception"] is not None or z["exit"] is None:
        return None
    try:
        p = json.loads(z["stdout"])
    except ValueError:
        return None
    return p if isinstance(p, dict) else None


def case_line_dispatch(c, z, timeout_key):
    line = {k: None for k in DISPATCH_CASE_KEYS}
    line.update({"i": c["i"], "name": c["name"], "kind": c["kind"], "mode": c["mode"],
                "function": c["function"], "n": c["n"], "sel": c["sel"], "k": c["k"],
                "use_resource": c["use_resource"], "exit": z["exit"], "timed_out": z["timed_out"]})
    if z["timed_out"]:
        line.update({"status": "proc_timeout", "compile_ok": None, "dispatch_ok": None,
                    "cb_status": None, "out_hex": "", "outb_hex": "", "outsel_hex": ""})
        return line
    if z["exception"] is not None or z["exit"] is None or z["exit"] not in (0,):
        line.update({"status": "proc_fail", "compile_ok": None, "dispatch_ok": None,
                    "cb_status": None, "out_hex": "", "outb_hex": "", "outsel_hex": ""})
        return line
    p = _parse_json_stdout(z)
    if p is None:
        line.update({"status": "proc_fail", "compile_ok": None, "dispatch_ok": None,
                    "cb_status": None, "out_hex": "", "outb_hex": "", "outsel_hex": ""})
        return line
    if set(p) != DISPATCH_SUMMARY_KEYS or p["schema"] != 1 \
            or p["function"] != c["function"] or p["n"] != c["n"] \
            or not isinstance(p["compile_ok"], bool) or not isinstance(p["dispatch_ok"], bool):
        raise SystemExit("harness record defect for case %s: shape/echo mismatch" % c["name"])
    if not p["compile_ok"]:
        status = "compile_reject"
    elif not p["dispatch_ok"]:
        status = "cb_error"
    else:
        status = "ok" if p["command_buffer_status"] == 4 else "cb_error"
    line.update({"status": status, "compile_ok": p["compile_ok"], "dispatch_ok": p["dispatch_ok"],
                "cb_status": p["command_buffer_status"], "out_hex": p["out_hex"],
                "outb_hex": p["outb_hex"], "outsel_hex": p["outsel_hex"]})
    return line


def case_line_decode(c, z):
    line = {k: None for k in DECODE_CASE_KEYS}
    line.update({"i": c["i"], "name": c["name"], "kind": c["kind"], "function": c["function"],
                "exit": z["exit"], "timed_out": z["timed_out"]})
    if z["timed_out"]:
        line["status"] = "proc_timeout"
        return line
    if z["exception"] is not None or z["exit"] != 0:
        line["status"] = "proc_fail"
        return line
    p = _parse_json_stdout(z)
    if p is None or set(p) != DECODE_SUMMARY_KEYS or p["schema"] != 1 or p["function"] != c["function"]:
        raise SystemExit("decode record defect for case %s: shape/echo mismatch" % c["name"])
    status = "ok" if p["build_ok"] and p["confirmation_ok"] else \
        ("identification_failed" if p["build_ok"] else "compile_reject")
    line.update({"status": status, "build_ok": p["build_ok"], "main_len": p["main_len"],
                "preamble_len": p["preamble_len"], "main_leftover_len": p["main_leftover_len"],
                "preamble_leftover_len": p["preamble_leftover_len"],
                "n_device_load_main": p["n_device_load_main"],
                "n_device_load_preamble": p["n_device_load_preamble"],
                "confirmation_ok": p["confirmation_ok"]})
    for key in ("l1", "l2"):
        d = p.get(key) or {}
        for f in ("base_slot", "index_reg", "addr_mode", "idx_off", "dst_reg", "offset"):
            line["%s_%s" % (key, f)] = d.get(f)
    return line


# Fine-grained analysis-script `outcome` -> coarse frozen `status` bucket
# (the exact outcome string is ALSO kept verbatim in the `outcome` field).
SPLICE_OUTCOME_TO_STATUS = {
    "build_fail": "compile_reject",
    "identification_failed": "identification_failed",
    "baseline_run_failed": "baseline_failed",
    "baseline_unexpected_tags": "baseline_failed",
    "splice_precondition_failed": "baseline_failed",
    "spliced_run_process_fault": "proc_fail",
    "spliced_run_rejected_or_faulted": "cb_error",
    "confirmed": "confirmed",
    "refuted": "refuted",
}


def case_line_splice(c, z):
    line = {k: None for k in SPLICE_CASE_KEYS}
    line.update({"i": c["i"], "name": c["name"], "kind": c["kind"], "function": c["function"],
                "exit": z["exit"], "timed_out": z["timed_out"]})
    if z["timed_out"]:
        line["status"] = "proc_timeout"
        return line
    if z["exception"] is not None or z["exit"] != 0:
        line["status"] = "proc_fail"
        return line
    p = _parse_json_stdout(z)
    if p is None or set(p) != SPLICE_SUMMARY_KEYS or p["schema"] != 1 or p["function"] != c["function"]:
        raise SystemExit("splice record defect for case %s: shape/echo mismatch" % c["name"])
    outcome = p["outcome"]
    if outcome not in SPLICE_OUTCOME_TO_STATUS:
        raise SystemExit("splice record defect for case %s: unknown outcome %r" % (c["name"], outcome))
    baseline = p.get("baseline") or {}
    spliced = p.get("spliced_result") or {}
    target = p.get("target") or {}
    ident = p.get("ident") or {}
    # `other` = whichever of ident.l1/l2 is NOT `target`, identified unambiguously
    # by instruction offset (not by index_reg value, which is exactly the field
    # under test and may coincide in a degenerate/refuted case).
    other_reg = None
    l1, l2 = ident.get("l1"), ident.get("l2")
    if l1 and l2 and target:
        if l1.get("offset") == target.get("offset"):
            other_reg = l2.get("index_reg")
        elif l2.get("offset") == target.get("offset"):
            other_reg = l1.get("index_reg")
    line.update({"status": SPLICE_OUTCOME_TO_STATUS[outcome], "build_ok": p["build_ok"],
                "confirmation_ok": ident.get("confirmation_ok"),
                "baseline_out_hex": baseline.get("out_hex"), "baseline_outb_hex": baseline.get("outb_hex"),
                "target_index_reg": target.get("index_reg"), "other_index_reg": other_reg,
                "splice_offset_abs": p.get("splice_offset_abs"), "splice_from": p.get("splice_from"),
                "splice_to": p.get("splice_to"), "spliced_out_hex": spliced.get("out_hex"),
                "spliced_outb_hex": spliced.get("outb_hex"), "outcome": outcome})
    return line


def run_case(bin_dir, work, c):
    """Returns (receipt, case_line). One fresh process for every kind."""
    if c["kind"] == "dispatch":
        z = rec(dispatch_argv(bin_dir, c), TIMEOUTS["dispatch_case_process"], HERE)
        return z, case_line_dispatch(c, z, "dispatch_case_process")
    if c["kind"] == "decode":
        z = rec(decode_argv(bin_dir, work, c), TIMEOUTS["decode_case_process"], HERE)
        return z, case_line_decode(c, z)
    if c["kind"] == "splice":
        z = rec(splice_argv(bin_dir, work, c), TIMEOUTS["splice_case_process"], HERE)
        return z, case_line_splice(c, z)
    raise SystemExit("unknown case kind: %r" % c["kind"])


def smoke_problems(work):
    c = CM.by_name(SMOKE_CASE_NAME)
    bin_dir = work / "bin"
    d = work / "smoke"
    d.mkdir(parents=True)
    z = rec(dispatch_argv(bin_dir, c), TIMEOUTS["smoke_process"], HERE)
    put(d / "smoke.json", z)
    bad = []
    if z["timed_out"]:
        bad.append("smoke invocation timed out")
    if z["exception"] is not None:
        bad.append("smoke OS exception: %r" % (z["exception"],))
    if z["exit"] != 0:
        bad.append("smoke exit code %r" % (z["exit"],))
    p = _parse_json_stdout(z)
    if p is None:
        return bad + ["smoke stdout is not exactly one JSON object (%d bytes)" % len(z.get("stdout") or "")]
    missing, extra = sorted(DISPATCH_SUMMARY_KEYS - set(p)), sorted(set(p) - DISPATCH_SUMMARY_KEYS)
    if missing or extra:
        bad.append("smoke payload key set differs: missing=%s extra=%s" % (missing, extra))
        return bad
    if not (p["compile_ok"] is True and p["dispatch_ok"] is True and p["command_buffer_status"] == 4):
        bad.append("smoke did not cleanly compile+dispatch: %r" %
                   ((p["compile_ok"], p["dispatch_ok"], p["command_buffer_status"]),))
    expect = "".join("%08x" % (1000 + i) for i in range(32))
    if p["out_hex"] != expect:
        bad.append("smoke out_hex mismatch: got %r want %r" % (p["out_hex"], expect))
    return bad


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
    for gate in (("--selftest",), ("--seqtest",),
                ("--preflight" if a.run_id == RUNS[0] else "--between-runs",)):
        if subprocess.run([sys.executable, "-B", "verify.py", gate[0]], cwd=HERE).returncode:
            raise SystemExit("run gate failed: " + gate[0])
    current = provenance()
    if a.run_id == RUNS[1]:
        first = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        for k in ("git_revision", "git_dirty", "authored_code_sha256", "authored_doc_sha256",
                 "authored_tools_sha256"):
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
    try:
        env = {"schema": 1, **current,
               "sw_vers": rec(["sw_vers"], TIMEOUTS["env_command"], HERE),
               "xcrun_version": rec(["xcrun", "--version"], TIMEOUTS["env_command"], HERE),
               "python": sys.version.split()[0], "machine": platform.machine(),
               "boundary": BOUNDARY, "timeouts_seconds": TIMEOUTS}
        ep = env_problems(env)
        if ep:
            put(work / "STOP.json", {"schema": 1, "phase": "environment", "problems": ep,
                                     "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: environment")

        bin_dir = work / "bin"
        build = rec(["/bin/sh", HERE / "harness" / "build.sh", bin_dir], TIMEOUTS["host_build"], HERE)
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None:
            put(work / "STOP.json", {"schema": 1, "phase": "host_build",
                                     "problems": ["host build failed"], "receipt": build,
                                     "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: host build")

        problems = smoke_problems(work)
        if problems:
            put(work / "STOP.json", {"schema": 1, "phase": "pre_capture_smoke",
                                     "case": SMOKE_CASE_NAME, "problems": problems,
                                     "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: smoke gate (raw tree not created; "
                             "pre-capture repair authorized)")

        # Smoke passed: capture may begin (append-only from here).
        raw.mkdir(parents=True)
        put(raw / "00_inputs.json", env)
        put(raw / "01_matrix.json", {"schema": 1, "run_id": a.run_id, "cases": CM.CASES})
        put(raw / "02_build.json", build)

        lines, receipts = [], []
        infra = 0
        stopped = None
        for c in CM.CASES:
            z, line = run_case(bin_dir, work, c)
            lines.append(json.dumps(line, sort_keys=True))
            receipts.append(json.dumps({"i": c["i"], "name": c["name"], "kind": c["kind"], **z},
                                       sort_keys=True))
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
        counts = {s: sum(1 for l in lines if json.loads(l)["status"] == s) for s in STATUS_VALUES}
        put(raw / "03_dispatch.json", {
            "schema": 1, "run_id": a.run_id, "cases_planned": CM.TOTAL,
            "cases_recorded": len(lines), **{"n_%s" % s: counts[s] for s in STATUS_VALUES},
            "results_lines": len(lines), "results_sha256": sha(work / "results.jsonl")})
        shutil.move(str(work / "results.jsonl"), str(raw / "04_results.jsonl"))
        shutil.move(str(work / "receipts.jsonl"), str(raw / "05_receipts.jsonl"))
        put(raw / "06_run_manifest.json", {
            "schema": 1, "run_id": a.run_id, "cases_planned": CM.TOTAL,
            "cases_recorded": len(lines),
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
