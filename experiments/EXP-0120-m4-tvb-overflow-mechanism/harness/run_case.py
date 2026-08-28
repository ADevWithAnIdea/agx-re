"""Run exactly one EXP-0120 case as its own OS process. Never batches cases.

Used by run_sweep.py (official captures) and smoke.py (non-recorded dry run).
"""
import hashlib
import os
import subprocess
import time

from casematrix import BIN, IOTRACE_DYLIB

HARD_TIMEOUT_S = 150


def run_case(case, out_dir):
    """out_dir: directory this case may write its own artifacts into (already created).

    Returns a JSON-serializable record dict. Never raises for an ordinary
    process failure/timeout/fault -- those are recorded as results.
    """
    os.makedirs(out_dir, exist_ok=True)
    argv = [BIN, str(case["width"]), str(case["height"]), case["mode"],
            str(case["N"]), str(case["S"])]

    env = dict(os.environ)
    iotrace_log = None
    iotrace_maps = None
    if case["interposer"]:
        iotrace_log = os.path.join(out_dir, "iotrace.log")
        iotrace_maps = os.path.join(out_dir, "iotrace_maps")
        os.makedirs(iotrace_maps, exist_ok=True)
        env["DYLD_INSERT_LIBRARIES"] = IOTRACE_DYLIB
        env["IOTRACE_LOG"] = iotrace_log
        env["IOTRACE_DUMP_DIR"] = iotrace_maps
        for k, v in case["extra_env"].items():
            env[k] = v
    else:
        env.pop("DYLD_INSERT_LIBRARIES", None)
        for k in ("IOTRACE_LOG", "IOTRACE_DUMP_DIR", "IOTRACE_MAX_MAP", "G17P_DUMP_BEFORE_COMMIT"):
            env.pop(k, None)

    stdout_path = os.path.join(out_dir, "stdout.log")
    stderr_path = os.path.join(out_dir, "stderr.log")

    t0 = time.time()
    timed_out = False
    try:
        p = subprocess.run(argv, env=env, capture_output=True, timeout=HARD_TIMEOUT_S)
        returncode = p.returncode
        stdout_bytes = p.stdout
        stderr_bytes = p.stderr
    except subprocess.TimeoutExpired as e:
        timed_out = True
        returncode = None
        stdout_bytes = e.stdout or b""
        stderr_bytes = e.stderr or b""
    t1 = time.time()

    with open(stdout_path, "wb") as f:
        f.write(stdout_bytes)
    with open(stderr_path, "wb") as f:
        f.write(stderr_bytes)

    stdout_text = stdout_bytes.decode("utf-8", errors="replace")
    stdout_lines = stdout_text.splitlines()

    record = {
        "case_id": case["case_id"],
        "sweep": case["sweep"],
        "group": case.get("group"),
        "role": case.get("role"),
        "params": {"width": case["width"], "height": case["height"],
                    "mode": case["mode"], "N": case["N"], "S": case["S"]},
        "argv": argv,
        "interposer": case["interposer"],
        "extra_env": case["extra_env"],
        "timed_out": timed_out,
        "returncode": returncode,
        "elapsed_s": t1 - t0,
        "stdout_path": os.path.relpath(stdout_path, out_dir),
        "stderr_path": os.path.relpath(stderr_path, out_dir),
        "stdout_sha256": hashlib.sha256(stdout_bytes).hexdigest(),
        "stdout_tail": stdout_lines[-6:],
        "stdout_len": len(stdout_bytes),
        "stderr_len": len(stderr_bytes),
        "iotrace_log": os.path.relpath(iotrace_log, out_dir) if iotrace_log else None,
        "iotrace_maps_dir": os.path.relpath(iotrace_maps, out_dir) if iotrace_maps else None,
    }
    return record
