#!/usr/bin/env python3
"""EXP-0205 runner factory: the SHARED leak-free wrapper over a PINNED base.

`tools/agxtest/persistrun.py` starts a fresh reader thread per line and abandons
it on timeout, and that thread re-resolves `self.proc` at execution time -- so
after the FIRST WATCHDOG TIMEOUT an abandoned thread can wake on the replacement
child's stdout and race the foreground reader (DEF-0178-1).  Responses come back
truncated, the shared parser raises, and every later case is poisoned: in
EXP-0178's pilot one benign case manufactured three consecutive false `hang`s
with restarts=99, on an encoding the hardware handles without complaint.

A false hang and real inertness are indistinguishable in a summary, and this
experiment's whole difficulty is telling those apart, so it does not run on the
defective path.  `tools/agxtest/saferunner.py` (upstreamed by EXP-0185) gives
one reader thread per child tagged by owner, and turns a malformed response into
the `MALFORMED` status with the raw lines kept.  A MALFORMED case is scored as
`measurement_failure`, is excluded from agreement and from values_dispatched,
and is NEVER an observation.

Both files are used from `pinned/`, not from `tools/`, so a mid-run edit to the
shared tool cannot change what this experiment measured.

CLEAN-ROOM: process/protocol plumbing over our own OWN-SHADER runner.
"""
import importlib.util
import sys
from pathlib import Path


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def make_classes(pinned_dir):
    pinned = Path(pinned_dir)
    pr = _load(pinned / "persistrun.py", "exp205_persistrun")
    sr = _load(pinned / "saferunner.py", "exp205_saferunner")
    return sr.make_safe_runner(pr.PersistRunner)
