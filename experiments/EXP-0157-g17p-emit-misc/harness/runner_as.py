#!/usr/bin/env python3
"""EXP-0157 persistent-runner wrapper.

`tools/agxtest/persistrun.py` is used UNMODIFIED. This subclass only teaches it
that our AS-capable runner prints one extra `ACCEL <kind> <status> <ntris>`
line before `READY`, and passes the `--accel` flags through. Nothing else
changes, so every safety property of the upstream driver (per-request watchdog,
kill-and-restart on a wedge) is inherited rather than reimplemented.
"""
import os
import subprocess
import sys
from pathlib import Path

TOOLS = Path(os.environ.get("AGX_TOOLS", str(Path.home() / "agxre" / "tools")))
sys.path.insert(0, str(TOOLS / "agxtest"))
from persistrun import PersistRunner  # noqa: E402


class PersistRunnerAS(PersistRunner):
    def __init__(self, source, function, fast_math, agxrun_persist,
                 accel=None, accel_kind="primitive", restart_hook=None):
        self.accel = accel
        self.accel_kind = accel_kind
        self.accel_status = None
        super().__init__(source, function, fast_math, agxrun_persist,
                         restart_hook=restart_hook)

    def _start(self):
        cmd = [self.exe, "--source", self.source, "--function", self.function]
        if not self.fast_math:
            cmd.append("--no-fast-math")
        if self.accel is not None:
            cmd += ["--accel", str(self.accel), "--accel-kind", self.accel_kind]
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        for _ in range(4):
            ln = self._read_line(timeout=90)
            if ln is None:
                raise RuntimeError("agxrun_persist_as did not print READY in time")
            if ln.startswith("ACCEL"):
                self.accel_status = ln.strip()
                continue
            if ln.startswith("READY"):
                self.device = ln.split(None, 1)[1].strip() if " " in ln else "?"
                if self.accel is not None and (
                        not self.accel_status or " OK " not in self.accel_status):
                    raise RuntimeError("acceleration structure not built: %r"
                                       % self.accel_status)
                return
        raise RuntimeError("agxrun_persist_as did not become READY")
