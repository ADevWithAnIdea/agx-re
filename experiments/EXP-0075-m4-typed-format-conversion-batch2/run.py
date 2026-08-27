#!/usr/bin/env python3
"""Opt-in capture runner; never runs unless --execute is explicit.

Each case is one fresh harness process (fresh device, library, pipelines,
buffers, texture, command buffer). The runner records argv, cwd, timeouts,
timestamps, and complete stdout/stderr receipts into an append-only raw tree.
API-level rejections (exit 0 with a non-"ok" status) are recorded outcomes.
Any nonzero exit, timeout, or OS error is a harness fault: STOP.json is
written, the run ends, and nothing is retried automatically.

EXP-0075 adds the pre-capture NON-RECORDED SMOKE INVOCATION (the EXP-0072
quarantine fix, fix 2): after the host build and BEFORE the append-only raw
tree is created, exactly one scratch case is executed to work/<run-id>/smoke/
(outside raw/) and its stdout must parse as one complete, self-consistent JSON
record with every contracted field present. Any payload-shape or truncation
defect is therefore a PRE-CAPTURE stop: raw/ is never created, the work tree
with its STOP.json is retained as the failure record, and the pre-capture
repair of the harness/runner is authorized because nothing was captured.

The record builders (env_record, run_manifest_record, case_argv) and the smoke
validator (smoke_problems) are separate functions so verify.py --selftest can
prove the capture schema and the smoke gate are satisfiable before any GPU
work (lesson from quarantined EXP-0073), including against the exact
truncation class that quarantined EXP-0072.
"""
import argparse, datetime, hashlib, json, platform, shutil, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
RUNS = ("m4-20260827-run01", "m4-20260827-run02")
AUTH = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "kernels/format_batch2.metal",
        "harness/probe.m", "run.py", "analysis.py", "make_manifest.py", "verify.py")
BOUNDARY = "public Metal only; owned in-bounds buffers; no binary/archive/BO inspection"
SMOKE_CASE = "r32float_exact"
SMOKE_TIMEOUT = 300

def contract():
    return json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())

def cases():
    return contract()["cases"]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def provenance():
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True, capture_output=True, check=True).stdout.strip()
    por = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=HERE, text=True, capture_output=True, check=True).stdout.splitlines()
    return {"git_revision": rev, "git_dirty": bool(por), "authored_sha256": {x: sha(HERE / x) for x in AUTH}}

def put(p, o):
    p.write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")

def rec(argv, timeout):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run([str(x) for x in argv], cwd=HERE, text=True, capture_output=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": True, "exit": None,
                "stdout": e.stdout or "", "stderr": e.stderr or "", "exception": "TimeoutExpired"}
    except OSError as e:
        return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": None,
                "stdout": "", "stderr": "", "exception": type(e).__name__}

def env_record():
    return {"schema": 1, **provenance(),
            "sw_vers": rec(["sw_vers"], 5),
            "xcrun_version": rec(["xcrun", "--version"], 5),
            "device_model": rec(["sysctl", "-n", "hw.model"], 5),
            "machine": platform.machine(), "boundary": BOUNDARY}

def build_argv(work_dir):
    return ["xcrun", "clang", "-fobjc-arc", "-o", work_dir / "probe", HERE / "harness/probe.m",
            "-framework", "Metal", "-framework", "Foundation"]

def case_argv(work_dir, c):
    return [work_dir / "probe", "--source", HERE / "kernels/format_batch2.metal",
            "--case", c["case"], "--format", c["format"],
            "--texel-bytes", str(c["texel_bytes"]), "--reader", c["reader"]]

def run_manifest_record(run_id, case_ids):
    return {"schema": 1, "run_id": run_id, "cases": list(case_ids), "fresh_process_per_case": True,
            "runner_sha256": sha(HERE / "run.py"),
            "harness_sha256": sha(HERE / "harness/probe.m"),
            "kernel_sha256": sha(HERE / "kernels/format_batch2.metal"),
            "contract_sha256": sha(HERE / "CAPTURE_CONTRACT.json")}

def env_problems(env):
    bad = []
    for name in ("sw_vers", "xcrun_version", "device_model"):
        z = env[name]
        if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
            bad.append("environment command failed: " + name)
    return bad

def smoke_problems(z, c, keys, statuses):
    """Pre-capture smoke validator (pure, so the self-test can exercise it).

    z is a receipt from rec(); c is the contract case record for SMOKE_CASE;
    keys is the contracted payload key set; statuses is the contracted set of
    exit-zero statuses. Returns a list of defect strings; empty means the smoke
    invocation produced exactly one complete, self-consistent record and the
    capture may begin.
    """
    bad = []
    if z.get("timed_out") is not False:
        bad.append("smoke invocation timed out")
    if z.get("exception") is not None:
        bad.append("smoke OS exception: " + str(z.get("exception")))
    if z.get("exit") != 0:
        bad.append("smoke exit code %r" % (z.get("exit"),))
    out = z.get("stdout") or ""
    try:
        p = json.loads(out)
    except ValueError:
        return bad + ["smoke stdout is not exactly one JSON object (%d bytes)" % len(out)]
    if not isinstance(p, dict):
        return bad + ["smoke stdout is not a JSON object"]
    missing, extra = sorted(set(keys) - set(p)), sorted(set(p) - set(keys))
    if missing or extra:
        bad.append("smoke payload key set differs: missing=%s extra=%s" % (missing, extra))
        return bad
    for k, want in (("case", c["case"]), ("format", c["format"]),
                    ("texel_bytes", c["texel_bytes"]), ("reader", c["reader"])):
        if p.get(k) != want:
            bad.append("smoke identity %s=%r (contract %r)" % (k, p.get(k), want))
    if p.get("status") not in statuses:
        bad.append("smoke status %r outside the contracted status set" % (p.get("status"),))
    elif p.get("status") != "ok":
        bad.append("smoke status %r: the scratch case must complete, not reject, before capture" % (p.get("status"),))
    if (p.get("library_ok"), p.get("store_pipeline_ok"), p.get("read_pipeline_ok"), p.get("texture_ok")) != (True, True, True, True):
        bad.append("smoke stage flags %r" % ([(k, p.get(k)) for k in ("library_ok", "store_pipeline_ok", "read_pipeline_ok", "texture_ok")],))
    if p.get("command_buffer_status") != 4 or p.get("command_buffer_error") != "":
        bad.append("smoke command buffer status %r error %r" % (p.get("command_buffer_status"), p.get("command_buffer_error")))
    if p.get("device") != "Apple M4" or p.get("machine") != "arm64" or not isinstance(p.get("os"), str) or not p["os"]:
        bad.append("smoke device identity %r/%r" % (p.get("device"), p.get("machine")))
    if p.get("fast_math_enabled") is not False or p.get("storage_mode") != "MTLStorageModeShared":
        bad.append("smoke compile/storage record %r/%r" % (p.get("fast_math_enabled"), p.get("storage_mode")))
    n = c["texel_bytes"]
    bh, rh, th, ws = p.get("backing_hex"), p.get("result_hex"), p.get("physical_texel_hex"), p.get("read_words_le")
    for name, v, ln in (("backing_hex", bh, 768), ("result_hex", rh, 288), ("physical_texel_hex", th, 2 * n)):
        if not isinstance(v, str) or len(v) != ln or any(ch not in "0123456789abcdef" for ch in v):
            bad.append("smoke %s is not %d lowercase hex chars" % (name, ln))
    if not (isinstance(ws, list) and len(ws) == 4 and all(type(x) is int and 0 <= x < 2 ** 32 for x in ws)):
        bad.append("smoke read_words_le grammar")
        return bad
    if isinstance(bh, str) and len(bh) == 768 and isinstance(rh, str) and len(rh) == 288 and isinstance(th, str) and len(th) == 2 * n:
        b, r = bytes.fromhex(bh), bytes.fromhex(rh)
        if th != b[64:64 + n].hex():
            bad.append("smoke physical_texel_hex is not backing bytes 64..%d" % (64 + n))
        if ws != [int.from_bytes(r[64 + i:68 + i], "little") for i in range(0, 16, 4)]:
            bad.append("smoke read_words_le is not result bytes 64..80 little-endian")
        derived = (b[:64] == b"\x5a" * 64, b[320:] == b"\xa5" * 64, r[:64] == b"\x5a" * 64, r[80:] == b"\xa5" * 64)
        flags = tuple(p.get(k) for k in ("backing_prefix_guard", "backing_suffix_guard", "result_prefix_guard", "result_suffix_guard"))
        if flags != derived or any(v is not True for v in derived):
            bad.append("smoke guard regions %r (derived %r)" % (flags, derived))
    return bad

def smoke_gate(work_root, cs):
    """Execute the one non-recorded scratch invocation; return its defects."""
    c = next(x for x in cs if x["case"] == SMOKE_CASE)
    cap = contract()["capture"]
    d = work_root / "smoke"
    d.mkdir(parents=True)
    z = rec(case_argv(work_root, c), SMOKE_TIMEOUT)
    put(d / "smoke.json", z)
    return smoke_problems(z, c, cap["payload_keys"], cap["statuses_exit_zero"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ",".join(RUNS))
    gates = ("--preflight", "--selftest") if a.run_id == RUNS[0] else ("--between-runs", "--selftest")
    for g in gates:
        if subprocess.run(["python3", "-B", "verify.py", g], cwd=HERE).returncode:
            raise SystemExit("run gate failed: " + g)
    current = provenance()
    if a.run_id == RUNS[1]:
        first = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        for key in ("git_revision", "authored_sha256"):
            if first.get(key) != current[key]:
                raise SystemExit("run02 provenance differs from closed run01")
    raw = HERE / "raw" / a.run_id
    work_root = HERE / "work" / a.run_id
    if raw.exists():
        raise SystemExit("append-only raw path already exists")
    work_parent = HERE / "work"
    if work_root.exists() or (work_parent.exists() and any(work_parent.iterdir())):
        raise SystemExit("scratch path already exists or work is not empty; remove a retained pre-capture stop first")
    work_root.mkdir(parents=True)
    # Everything from here to raw.mkdir() is pre-capture: a failure writes the
    # retained work/<run-id>/STOP.json and never creates the append-only tree,
    # so an authorized pre-capture repair remains possible.
    try:
        cs = cases()
        env = env_record()
        if env_problems(env):
            put(work_root / "STOP.json", {"schema": 1, "phase": "environment", "problems": env_problems(env),
                                          "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: environment")
        build = rec(build_argv(work_root), 120)
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None:
            put(work_root / "STOP.json", {"schema": 1, "phase": "host_build", "problems": ["host build failed"],
                                          "receipt": build, "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: host build")
        problems = smoke_gate(work_root, cs)
        if problems:
            put(work_root / "STOP.json", {"schema": 1, "phase": "pre_capture_smoke", "case": SMOKE_CASE,
                                          "problems": problems, "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: smoke gate (raw tree not created; pre-capture repair authorized)")
        # The smoke gate passed: every defect class that truncated EXP-0072 is
        # now excluded, and the append-only capture may begin.
        raw.mkdir(parents=True)
        put(raw / "00_inputs.json", env)
        put(raw / "01_host_build.json", build)
        for c in cs:
            z = rec(case_argv(work_root, c), 300)
            put(raw / f"case_{c['case']}.json", z)
            if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
                put(raw / "STOP.json", {"schema": 1, "phase": "case", "case": c["case"], "automatic_retry": False})
                return
        put(raw / "run_manifest.json", run_manifest_record(a.run_id, [c["case"] for c in cs]))
    finally:
        if not (work_root / "STOP.json").exists():
            shutil.rmtree(work_root, ignore_errors=True)

if __name__ == "__main__":
    main()
