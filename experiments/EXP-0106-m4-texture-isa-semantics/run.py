#!/usr/bin/env python3
"""Opt-in capture runner for EXP-0106, never runs without --execute.
Architecture independently re-authored from the proven EXP-0079/EXP-0083/
EXP-0095 pattern (this project's own prior work): every case invokes ONE
fresh harness process (harness/probe.m) -- fresh device, library (if any),
resources, one command buffer. A public-API rejection (exit 0, a non-"ok"
but CONTRACTED status such as "abort"/"library_failed"/"pipeline_rejected")
is a RECORDED OUTCOME, not a harness fault. Any other nonzero exit, timeout,
or OS error is a harness fault: STOP.json is written and the run ends;
nothing is retried automatically.
"""
import argparse, datetime, hashlib, json, platform, shutil, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
RUNS = ("m4-20260830-run01", "m4-20260830-run02")
BOUNDARY = "public Metal only; owned in-bounds resources; no binary/archive/BO inspection"
SMOKE_TIMEOUT = 60

def contract():
    return json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())

def cases():
    return contract()["cases"]

def auth_files():
    return tuple(contract()["blob_sha256"].keys()) + ("CAPTURE_CONTRACT.json",)

def sha(p):
    return hashlib.sha256((HERE / p).read_bytes()).hexdigest()

def provenance():
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True, capture_output=True, check=True).stdout.strip()
    por = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=HERE, text=True, capture_output=True, check=True).stdout.splitlines()
    return {"git_revision": rev, "git_dirty": bool(por), "authored_sha256": {x: sha(x) for x in auth_files()}}

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
    argv = [work_dir / "probe", "--family", c["family"], "--case", c["case"]]
    if c.get("kernel_file"):
        argv += ["--source", HERE / c["kernel_file"]]
    argv += ["--args", json.dumps(c["args"], sort_keys=True)]
    return argv

def run_manifest_record(run_id, case_ids):
    c = contract()
    return {"schema": 1, "run_id": run_id, "cases": list(case_ids), "fresh_process_per_case": True,
            "runner_sha256": sha("run.py"), "harness_sha256": sha("harness/probe.m"),
            "authored_sha256": {x: sha(x) for x in auth_files()},
            "contract_sha256": sha("CAPTURE_CONTRACT.json")}

def env_problems(env):
    bad = []
    for name in ("sw_vers", "xcrun_version", "device_model"):
        z = env[name]
        if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
            bad.append("environment command failed: " + name)
    return bad

def payload_status_ok(status, expect):
    return status == expect

def smoke_problems(z, c, statuses):
    """Pre-capture smoke validator (pure -- exercised by verify.py --selftest
    too). z is a rec() receipt for the SMOKE_CASE; c is its contract record."""
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
    keys = set(p)
    dispatch_keys = {"schema", "family", "case", "status", "library_ok", "library_error", "pipelines",
                      "resource_ok", "resource_error", "command_buffer_status", "command_buffer_error",
                      "device", "machine", "os", "prefix_guard_ok", "suffix_guard_ok", "out_hex", "out_words"}
    if keys != dispatch_keys:
        bad.append("smoke payload key set differs: missing=%s extra=%s" % (sorted(dispatch_keys - keys), sorted(keys - dispatch_keys)))
        return bad
    if p.get("family") != c["family"] or p.get("case") != c["case"]:
        bad.append("smoke identity mismatch")
    if not payload_status_ok(p.get("status"), c.get("expect_status", "ok")):
        bad.append("smoke status %r does not match contracted expect_status %r" % (p.get("status"), c.get("expect_status")))
    if p.get("command_buffer_status") != 4 or p.get("command_buffer_error") != "":
        bad.append("smoke command buffer status %r error %r" % (p.get("command_buffer_status"), p.get("command_buffer_error")))
    if p.get("device") != "Apple M4" or p.get("machine") != "arm64" or not isinstance(p.get("os"), str) or not p["os"]:
        bad.append("smoke device identity %r/%r" % (p.get("device"), p.get("machine")))
    if p.get("prefix_guard_ok") is not True or p.get("suffix_guard_ok") is not True:
        bad.append("smoke guard flags not both true")
    oh = p.get("out_hex")
    ow = p.get("out_words")
    if not (isinstance(oh, str) and len(oh) == 192 and all(ch in "0123456789abcdef" for ch in oh)):
        bad.append("smoke out_hex is not 192 lowercase hex chars")
    if not (isinstance(ow, list) and len(ow) == 16 and all(type(x) is int and 0 <= x < 2 ** 32 for x in ow)):
        bad.append("smoke out_words grammar")
        return bad
    if isinstance(oh, str) and len(oh) == 192:
        b = bytes.fromhex(oh)
        if b[:16] != b"\x5a" * 16 or b[80:96] != b"\xa5" * 16:
            bad.append("smoke guard bytes in out_hex do not match the guard flags")
        derived_words = [int.from_bytes(b[16 + 4 * i:20 + 4 * i], "little") for i in range(16)]
        if derived_words != ow:
            bad.append("smoke out_words is not out_hex[16:80] little-endian")
    return bad

def smoke_gate(work_root, cs):
    smoke_case_name = contract()["capture"]["pre_capture_smoke"]["case"]
    c = next(x for x in cs if x["case"] == smoke_case_name)
    d = work_root / "smoke"
    d.mkdir(parents=True)
    z = rec(case_argv(work_root, c), SMOKE_TIMEOUT)
    put(d / "smoke.json", z)
    return smoke_problems(z, c, None)

GATE_TIMEOUT = 900

def run_gate(args):
    try:
        r = subprocess.run(["python3", "-B"] + args, cwd=HERE, timeout=GATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SystemExit("run gate timed out after %ds: %s" % (GATE_TIMEOUT, " ".join(args)))
    if r.returncode:
        raise SystemExit("run gate failed: " + " ".join(args))

def is_recorded_nonzero_ok(c, z):
    """A case whose contracted expect_status != 'ok' can legitimately exit
    with a negative signal (abort) OR exit 0 with a non-'ok' JSON status
    (library_failed/pipeline_rejected) -- both are recorded outcomes, not
    harness faults, PROVIDED the process did not time out or hit an OS
    exception."""
    if z["timed_out"] or z["exception"] is not None or z["exit"] is None:
        return False
    expect = c.get("expect_status", "ok")
    if expect == "abort":
        return z["exit"] < 0
    if expect in ("library_failed", "pipeline_rejected"):
        if z["exit"] != 0:
            return False
        try:
            p = json.loads(z["stdout"])
        except json.JSONDecodeError:
            return False
        return p.get("status") == expect
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ",".join(RUNS))
    run_gate(["verify.py", "--selftest"])
    run_gate(["verify.py", "--seqtest"])
    run_gate(["make_manifest.py", "--check"])
    run_gate(["verify.py", "--preflight" if a.run_id == RUNS[0] else "--between-runs"])
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
            put(work_root / "STOP.json", {"schema": 1, "phase": "pre_capture_smoke", "problems": problems,
                                          "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: smoke gate (raw tree not created; pre-capture repair authorized)")
        raw.mkdir(parents=True)
        put(raw / "00_inputs.json", env)
        put(raw / "01_host_build.json", build)
        for c in cs:
            z = rec(case_argv(work_root, c), c.get("timeout_seconds", 60))
            put(raw / f"case_{c['case']}.json", z)
            expect = c.get("expect_status", "ok")
            if expect != "ok":
                if not is_recorded_nonzero_ok(c, z):
                    put(raw / "STOP.json", {"schema": 1, "phase": "case", "case": c["case"],
                                            "problems": ["expected outcome %r not observed" % expect],
                                            "automatic_retry": False})
                    return
                continue
            if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
                put(raw / "STOP.json", {"schema": 1, "phase": "case", "case": c["case"], "automatic_retry": False})
                return
        put(raw / "run_manifest.json", run_manifest_record(a.run_id, [c["case"] for c in cs]))
    finally:
        if not (work_root / "STOP.json").exists():
            shutil.rmtree(work_root, ignore_errors=True)

if __name__ == "__main__":
    main()
