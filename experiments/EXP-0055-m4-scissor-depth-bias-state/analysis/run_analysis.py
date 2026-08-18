#!/usr/bin/env python3
"""Run EXP-0055 derivation with a hard timeout and retain the invocation."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
argv = [sys.executable, str(HERE / "analyze.py"),
        "--json", str(HERE / "summary.json"),
        "--report", str(HERE / "report.txt")]
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
record: dict[str, object] = {"argv": argv, "timeout_seconds": 60,
                             "started_utc": started}
try:
    cp = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    record.update(exit=cp.returncode, stdout=cp.stdout, stderr=cp.stderr)
except subprocess.TimeoutExpired as exc:
    def text(value: object) -> str:
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return str(value or "")
    record.update(exit=None, timed_out=True, stdout=text(exc.stdout),
                  stderr=text(exc.stderr))
(HERE / "invocation.json").write_text(
    json.dumps(record, indent=2, sort_keys=True) + "\n")
raise SystemExit(0 if record.get("exit") == 0 else 1)
