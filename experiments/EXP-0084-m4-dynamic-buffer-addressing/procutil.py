#!/usr/bin/env python3
"""EXP-0084 single authoritative subprocess-receipt builder. Imported by
run.py, verify.py, and every analysis/ script -- never redefined elsewhere."""
import datetime
import subprocess

REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out",
            "exit", "stdout", "stderr", "exception"}


def rec(argv, timeout, cwd):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    argv = [str(x) for x in argv]
    try:
        p = subprocess.run(argv, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
        return {"argv": argv, "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        return {"argv": argv, "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": True, "exit": None,
                "stdout": e.stdout or "", "stderr": e.stderr or "", "exception": "TimeoutExpired"}
    except OSError as e:
        return {"argv": argv, "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": None,
                "stdout": "", "stderr": "", "exception": type(e).__name__}
