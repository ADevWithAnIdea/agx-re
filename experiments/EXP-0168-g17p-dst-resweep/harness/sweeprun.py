#!/usr/bin/env python3
"""EXP-0168 sweep engine (G17P): carriers, dispatch, oracle, classification.

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified) so a whole field
sweep is ONE `agxrun_persist` process. Two carrier styles:

  STYLE-S  `SynthCarrier`   -- the whole `_agc.main` of a neutral carrier kernel
                               is replaced by a program we assembled from
                               `tools/agx-isa`'s own field rules, with the
                               instruction under test LIFTED verbatim out of the
                               compiled form of our own MSL. Observable: a
                               16-register dump + PRE/POST sentinels + a tail
                               poison region.
  STYLE-P  `InPlaceCarrier` -- one field is mutated where it already sits inside
                               the compiled form of our own probe kernel, and
                               THAT kernel is dispatched with real inputs.
                               Observable: the kernel's own POISONED output
                               buffer. Used for control-flow and memory
                               instructions, whose branch displacements and
                               buffer bindings do not survive being moved.

Structure reused, and cited, from EXP-0154 `harness/sweeprun.py` (same project,
same rules): the `Carrier` shape, the poison file, the append-only `Log`, and
the victim-marker list.

THE THREE THINGS THAT ARE DIFFERENT HERE, AND WHY
-------------------------------------------------
1. **The oracle is a host-computed register-slot PATTERN, not "equal to the
   baseline".** EXP-0154's `classify` scores a case `ok` when the full register
   state matches the unmutated anchor. That is right for a modifier field and
   exactly wrong for a destination-register field, where MOVEMENT IS THE
   PREDICTION. `classify_slots` reports WHICH slots changed; `Oracle` predicts
   which ones should.

2. **`validity`, separate from `outcome`.** FIELD-SWEEP-PROTOCOL fixes the
   `outcome` enum, so run-integrity lives in its own key. A case is `valid` only
   if the dispatch reported OK, the PRE sentinel survived, the POST sentinel is
   correct, the tail poison region is intact, and no `InnocentVictim`-class
   string appeared. A read-back that is still entirely poison is
   `invalid_poison` and is RE-RUN -- never recorded as a silent zero. EXP-0160
   saw 25 dispatches report STATUS OK and write nothing at all with no victim
   string; against a zero-initialised buffer those would have been 25 confident
   `silent_zero`s.

3. **Every case records the full instruction BYTES.** EXP-0144's committed raw
   can no longer be joined by `field` label, because db.json's label strings
   moved out from under it (byte 7 of `pack_convert` was `fmt_word`, is now
   `b7`). Bytes are stable; labels are not.

CLEAN-ROOM: pure process/file plumbing over our own tools; the only machine code
inspected or spliced is the compiled form of OUR OWN MSL.
"""
from __future__ import print_function

import importlib.util
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def find_tools():
    for cand in (EXP / "tools",                                # on the neo
                 EXP / "work" / "tools",
                 Path.home() / "agxre" / "EXP-0168" / "tools",
                 EXP.parents[1] / "tools",                      # on the repo host
                 Path.home() / "agxre" / "tools"):
        if (cand / "shdump" / "agxparse.py").exists():
            return cand
    raise RuntimeError("cannot locate tools/")


TOOLS = find_tools()
agxparse = _load("agxparse", TOOLS / "shdump" / "agxparse.py")
persistrun = _load("persistrun", TOOLS / "agxtest" / "persistrun.py")
SHDUMP = TOOLS / "shdump" / "shdump"
AGXRUN_PERSIST = TOOLS / "agxtest" / "agxrun_persist"

OUTCOMES = ("ok", "silent_zero", "wrong_value", "fault", "hang", "undecodable")
VALIDITIES = ("valid", "invalid_poison", "invalid_sentinel", "invalid_victim",
              "invalid_nodata")

# FIELD-SWEEP-PROTOCOL 7.3: an `...ErrorInnocentVictim`-class command-buffer
# failure is evidence about the MACHINE (a sibling GPU context's fault splashing
# into ours after a device reset), not about our encoding. Matched against the
# OS's own localizedDescription, printed verbatim by agxrun_persist.
VICTIM_MARKERS = ("InnocentVictim", "innocent victim",
                  "Ignored (for causing prior", "IOAF code 4", "IOAF code 2",
                  "Discarded")


def is_victim(err):
    if not err:
        return False
    low = err.lower()
    return any(m.lower() in low for m in VICTIM_MARKERS)


def os_class(err):
    """The OS fault-classification string, recorded verbatim on every non-ok
    case per the dispatch's requirement."""
    if not err:
        return None
    for k in ("InnocentVictim", "ErrorHang", "ErrorTimeout", "ErrorPageFault",
              "ErrorOutOfMemory", "ErrorInvalidResource", "ErrorMakeCurrent",
              "ErrorRestart", "ErrorRecovery", "ErrorAccessRevoked"):
        if k in err:
            return k
    return "unclassified"


# ---------------------------------------------------------------------------
# Carriers
# ---------------------------------------------------------------------------
class _Base(object):
    def __init__(self, source, function, workdir, timeout=8.0, fast_math=False):
        self.source = Path(source)
        self.function = function
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.fast_math = fast_math
        self.base_path = self.workdir / ("base_%s.bin" % function)
        cmd = [str(SHDUMP), "-o", str(self.base_path), "-f", function]
        if not fast_math:
            cmd.append("--no-fast-math")
        cmd.append(str(self.source))
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=300)
        if r.returncode != 0 or not self.base_path.exists():
            raise RuntimeError("shdump failed for %s: %s"
                               % (function, r.stderr.decode()[-800:]))
        self.basebuf = self.base_path.read_bytes()
        loc = agxparse.locate_region(self.basebuf, "_agc.main")
        if loc is None:
            raise RuntimeError("could not locate _agc.main in %s" % function)
        self.region_off, self.region_len = loc
        _, pieces = agxparse.extract_agx(self.basebuf)
        self.main_bytes = pieces["_agc.main"]
        self.runner = persistrun.PersistRunner(
            source=str(self.source), function=function, fast_math=fast_math,
            agxrun_persist=str(AGXRUN_PERSIST))
        self.device = self.runner.device
        self.spliced_path = self.workdir / ("spl_%s_%d.bin" % (function, os.getpid()))
        self.hangs = 0

    def _dispatch(self, prog_region, grid, tg, ins, outs, timeout=None):
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + self.region_len] = prog_region
        self.spliced_path.write_bytes(bytes(spliced))
        resp = self.runner.request(archive=str(self.spliced_path), grid=grid,
                                   tg=tg, ins=ins, outs=outs,
                                   timeout=timeout or self.timeout)
        if resp["status"] == "HANG":
            self.hangs += 1
        return resp

    def restart(self):
        try:
            self.runner.close()
        except Exception:
            try:
                self.runner._kill()
            except Exception:
                pass
        self.runner = persistrun.PersistRunner(
            source=str(self.source), function=self.function,
            fast_math=self.fast_math, agxrun_persist=str(AGXRUN_PERSIST))

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass


class SynthCarrier(_Base):
    """STYLE-S. Buffer 0 = the 104-word poisoned read-back."""

    def __init__(self, *a, **kw):
        _Base.__init__(self, *a, **kw)
        self.poison_path = self._write_poison()

    def _write_poison(self):
        p = self.workdir / ("poison_%d.bin" % os.getpid())
        p.write_bytes(struct.pack("<%dI" % H.OUT_WORDS,
                                  *([H.POISON] * H.OUT_WORDS)))
        return str(p)

    def run_program(self, prog, grid=1, tg=1, timeout=None):
        if len(prog) != self.region_len:
            raise ValueError("program %d != region %d"
                             % (len(prog), self.region_len))
        resp = self._dispatch(prog, grid, tg, {0: self.poison_path},
                              {0: H.OUT_WORDS * 4}, timeout)
        raw = resp["outs"].get(0, b"")
        words = [struct.unpack_from("<I", raw, i)[0]
                 for i in range(0, len(raw) - 3, 4)]
        return resp, words


class InPlaceCarrier(_Base):
    """STYLE-P. The probe kernel's own bindings; caller supplies ins/outs."""

    def __init__(self, source, function, workdir, in_files, out_specs,
                 grid, tg, timeout=8.0, fast_math=False):
        _Base.__init__(self, source, function, workdir, timeout, fast_math)
        self.in_files = dict(in_files)
        self.out_specs = dict(out_specs)
        self.grid = grid
        self.tg = tg

    def run_patched(self, patched_main, timeout=None):
        """`patched_main` is the whole `_agc.main` with ONE field mutated."""
        if len(patched_main) != self.region_len:
            raise ValueError("patched main %d != region %d"
                             % (len(patched_main), self.region_len))
        resp = self._dispatch(patched_main, self.grid, self.tg,
                              self.in_files, self.out_specs, timeout)
        outs = {}
        for idx, raw in resp["outs"].items():
            outs[idx] = [struct.unpack_from("<I", raw, i)[0]
                         for i in range(0, len(raw) - 3, 4)]
        return resp, outs


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------
def digest(words):
    """The interpreted view of the 104-word read-back."""
    if not words or len(words) < H.OUT_WORDS:
        return None
    regs = [words[H.W_REG0 + i * H.STORE_STRIDE_WORDS] for i in range(H.N_REGS)]
    tail = words[H.W_TAIL:H.W_TAIL + H.N_TAIL_WORDS]
    return {"regs": regs, "pre": words[H.W_PRE], "post": words[H.W_POST],
            "probe": words[H.W_PROBE], "tail_ok": all(t == H.POISON for t in tail),
            "all_poison": all(w == H.POISON for w in words)}


def digest_hex(d):
    if not d:
        return None
    return ("".join("%08x" % v for v in d["regs"])
            + "%08x%08x%08x" % (d["pre"], d["post"], d["probe"]))


def validity_of(status, err, d, expect_probe=False):
    """Run integrity, kept strictly separate from the FIELD-SWEEP-PROTOCOL
    `outcome` enum. See the module docstring, point 2."""
    if is_victim(err):
        return "invalid_victim"
    if status != "OK":
        return "valid"          # a genuine fault/hang IS a measurement
    if d is None:
        return "invalid_nodata"
    if d["all_poison"]:
        return "invalid_poison"
    if d["pre"] != H.expected_pre():
        return "invalid_sentinel"
    if d["post"] != H.SENT_POST:
        return "invalid_sentinel"
    if not d["tail_ok"]:
        return "invalid_sentinel"
    return "valid"


def moved_slots(obs, base):
    """Indices of the registers whose value differs from the reference state."""
    if obs is None or base is None:
        return None
    return [i for i in range(H.N_REGS) if obs["regs"][i] != base["regs"][i]]


def classify_slots(status, obs, base, expect):
    """FIELD-SWEEP-PROTOCOL section 4 `outcome` for one case, against a
    HOST-COMPUTED expectation rather than against the unmutated baseline.

    `expect` is either None (no prediction: the case is exploratory and is
    scored structurally against the baseline, as EXP-0154 did) or a dict
    {"regs": [...16 expected words...]} produced by the arm's oracle.
    """
    if status == "HANG":
        return "hang"
    if status != "OK":
        return "fault"
    if obs is None:
        return "undecodable"
    ref = expect["regs"] if expect else (base["regs"] if base else None)
    if ref is None:
        return "undecodable"
    if obs["regs"] == ref:
        return "ok"
    bad = [i for i in range(H.N_REGS) if obs["regs"][i] != ref[i]]
    if all(obs["regs"][i] == 0 for i in bad):
        return "silent_zero"
    return "wrong_value"


class Log:
    """Append-only JSONL case log, flushed AND fsynced per record.

    Never buffer to write at the end: assume the process is killed mid-run
    (SUBAGENT_BRIEF; it has happened repeatedly on this project)."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(str(self.path), "a", buffering=1)
        self.n = 0

    def write(self, rec):
        self.n += 1
        rec = dict(rec)
        rec.setdefault("note", "")
        rec["seq"] = self.n
        rec["t"] = round(time.time(), 3)
        self.f.write(json.dumps(rec, sort_keys=True) + "\n")
        self.f.flush()
        os.fsync(self.f.fileno())

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass
