#!/usr/bin/env python3
"""EXP-0187 leak-free persistent-runner wrappers, built on the UPSTREAMED tool.

FIELD-SWEEP-PROTOCOL section 3(d): a mere WATCHDOG TIMEOUT -- not a real hang --
starts a false-hang cascade on the shared `persistrun.py`, because it starts a
fresh reader thread per line and abandons it on timeout, and that thread
re-resolves `self.proc` at execution time. EXP-0178's pilot recorded three
consecutive false `hang`s with `restarts=99` from ONE benign case, and a false
hang is indistinguishable from real inertness in a summary.

This experiment has NO ABORT PATH (protocol 3c), so hangs are expected and the
defect would be maximally damaging here.

The fix is NOT re-derived: `tools/agxtest/saferunner.py` was upstreamed by
EXP-0185 and is used through the PINNED copy (`pinned/saferunner.py`), resolved
by ABSOLUTE path with a HARD EXIT if absent, over the PINNED `persistrun.py`.
Only the acceleration-structure subclass is added here, because the shared tool
does not know about the `ACCEL` banner line; its interface is taken from
EXP-0157 harness/runner_as.py and EXP-0184 harness/saferunner184.py (cited).

CLEAN-ROOM: pure process/protocol plumbing over our own OWN-SHADER runners.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path


def _load(pinned_dir, name):
    p = Path(pinned_dir) / (name + ".py")
    if not p.exists():
        sys.stderr.write("FATAL: pinned %s.py absent at %s\n" % (name, p))
        raise SystemExit(2)
    spec = importlib.util.spec_from_file_location("pinned_" + name, str(p))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pinned_" + name] = mod
    spec.loader.exec_module(mod)
    if Path(mod.__file__).resolve() != p.resolve():
        sys.stderr.write("FATAL: %s resolved to %s, not the pinned %s\n"
                         % (name, mod.__file__, p))
        raise SystemExit(2)
    return mod


def make_classes(pinned_dir):
    pr = _load(pinned_dir, "persistrun")
    sr = _load(pinned_dir, "saferunner")
    Safe = sr.make_safe_runner(pr.PersistRunner)

    class SafePersistRunnerAS(Safe):
        """Adds --accel/--accel-kind and the extra `ACCEL` banner line."""

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
                stderr=subprocess.PIPE, text=True, bufsize=1,
                start_new_session=True)
            self._install_pump()
            self.restarts = getattr(self, "restarts", 0)
            self.malformed = getattr(self, "malformed", 0)
            for _ in range(6):
                ln = self._read_line(timeout=180)
                if ln is None:
                    raise RuntimeError("agxrun_persist_as did not print READY in time")
                if ln.startswith("ACCEL"):
                    self.accel_status = ln.strip()
                    continue
                if ln.startswith("READY"):
                    self.device = (ln.split(None, 1)[1].strip()
                                   if " " in ln else "?")
                    if self.accel is not None and (
                            not self.accel_status or " OK " not in self.accel_status):
                        raise RuntimeError("acceleration structure not built: %r"
                                           % self.accel_status)
                    return
            raise RuntimeError("agxrun_persist_as did not become READY")

    return Safe, SafePersistRunnerAS
