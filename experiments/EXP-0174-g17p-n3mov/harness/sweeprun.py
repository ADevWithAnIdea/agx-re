#!/usr/bin/env python3
"""EXP-0174 sweep engine: carrier, dispatch, observation, classification.

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified) so a whole sweep is
ONE `agxrun_persist` process. Structure reused, and cited, from
EXP-0168/harness/sweeprun.py (same project, same rules): the `SynthCarrier`
shape, the poison file, the append-only `Log`, `validity_of`, `is_victim`,
`os_class` and the victim-marker list.

WHAT IS DIFFERENT HERE
----------------------
* the observable is the FULL 16-register dump for BOTH carriers, and the
  per-carrier BLIND slot (the read-back index register) and PAD-MASKED slot are
  recorded on every case so no verdict can silently rest on a slot the carrier
  cannot see;
* `classify_move` answers the question this experiment exists to ask -- "did the
  value in r[src] appear in r[dst]?" -- from the HOST-KNOWN seed table, with no
  reference to any GPU measurement.

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
    """FAIL-CLOSED, like isa_helpers._find_isadb(): exactly one candidate. The
    shared ~/agxre/tools on the neo is stale and must never be silently used."""
    cand = EXP / "tools"
    if (cand / "shdump" / "agxparse.py").exists():
        return cand
    raise RuntimeError("PINNED TOOLS MISSING: %s (no path-search fallback)" % cand)


TOOLS = find_tools()
agxparse = _load("agxparse", TOOLS / "shdump" / "agxparse.py")
persistrun = _load("persistrun", TOOLS / "agxtest" / "persistrun.py")
SHDUMP = TOOLS / "shdump" / "shdump"
AGXRUN_PERSIST = TOOLS / "agxtest" / "agxrun_persist"

OUTCOMES = ("ok", "silent_zero", "wrong_value", "fault", "hang", "undecodable")
VALIDITIES = ("valid", "invalid_poison", "invalid_sentinel", "invalid_victim",
              "invalid_nodata")

VICTIM_MARKERS = ("InnocentVictim", "innocent victim",
                  "Ignored (for causing prior", "IOAF code 4", "IOAF code 2",
                  "Discarded")


def is_victim(err):
    if not err:
        return False
    low = err.lower()
    return any(m.lower() in low for m in VICTIM_MARKERS)


def os_class(err):
    if not err:
        return None
    for k in ("InnocentVictim", "ErrorHang", "ErrorTimeout", "ErrorPageFault",
              "ErrorOutOfMemory", "ErrorInvalidResource", "ErrorMakeCurrent",
              "ErrorRestart", "ErrorRecovery", "ErrorAccessRevoked"):
        if k in err:
            return k
    return "unclassified"


class SynthCarrier(object):
    """The whole `_agc.main` of our own carrier kernel is replaced by a program
    we assembled. Buffer 0 = the 104-word poisoned read-back."""

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
        self.poison_path = self._write_poison()
        self.hangs = 0
        self.dispatches = 0

    def _write_poison(self):
        p = self.workdir / ("poison_%d.bin" % os.getpid())
        p.write_bytes(struct.pack("<%dI" % H.OUT_WORDS,
                                  *([H.POISON] * H.OUT_WORDS)))
        return str(p)

    def run_program(self, prog, grid=1, tg=1, timeout=None):
        if len(prog) != self.region_len:
            raise ValueError("program %d != region %d" % (len(prog), self.region_len))
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + self.region_len] = prog
        self.spliced_path.write_bytes(bytes(spliced))
        resp = self.runner.request(archive=str(self.spliced_path), grid=grid,
                                   tg=tg, ins={0: self.poison_path},
                                   outs={0: H.OUT_WORDS * 4},
                                   timeout=timeout or self.timeout)
        if resp["status"] == "HANG":
            self.hangs += 1
        raw = resp["outs"].get(0, b"")
        words = [struct.unpack_from("<I", raw, i)[0]
                 for i in range(0, len(raw) - 3, 4)]
        self.dispatches += 1
        return resp, words

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


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------
def digest(words):
    if not words or len(words) < H.OUT_WORDS:
        return None
    regs = [words[H.W_REG0 + i * H.STORE_STRIDE_WORDS] for i in range(H.N_REGS)]
    tail = words[H.W_TAIL:H.W_TAIL + H.N_TAIL_WORDS]
    return {"regs": regs, "pre": words[H.W_PRE], "post": words[H.W_POST],
            "tail_ok": all(t == H.POISON for t in tail),
            "all_poison": all(w == H.POISON for w in words)}


def digest_hex(d):
    if not d:
        return None
    return "".join("%08x" % v for v in d["regs"]) + "%08x%08x" % (d["pre"], d["post"])


def validity_of(status, err, d):
    """Run integrity, kept strictly separate from the FIELD-SWEEP-PROTOCOL
    `outcome` enum (EXP-0168's point 2)."""
    if is_victim(err):
        return "invalid_victim"
    if status != "OK":
        return "valid"          # a genuine fault/hang IS a measurement
    if d is None:
        return "invalid_nodata"
    if not d["tail_ok"]:
        return "invalid_sentinel"
    if d["all_poison"]:
        return "invalid_poison"
    if d["pre"] != H.SENT_PRE:
        return "invalid_sentinel"
    if d["post"] != H.SENT_POST:
        return "invalid_sentinel"
    return "valid"


def moved_slots(obs, ref, blind=()):
    """Indices whose value differs from the host-known reference state, with the
    carrier's blind slot(s) excluded because they are unobservable BY
    CONSTRUCTION -- never because the answer there is inconvenient."""
    if obs is None:
        return None
    return [i for i in range(H.N_REGS)
            if i not in blind and obs["regs"][i] != ref[i]]


def classify_move(status, obs, ref, dst, src, blind=()):
    """The move oracle. `ref` is the HOST-KNOWN seed state; nothing here reads a
    GPU baseline.

    Returns (outcome, move_kind) where move_kind is one of:
      copy32        r[dst] == ref[src]  and dst != src              <-- THE RESULT
      copy_self     dst == src, r[dst] unchanged (indistinguishable from no-op)
      narrow16      r[dst] == ref[src] & 0xFFFF, differs from ref[src]
      zero          r[dst] == 0
      unchanged     r[dst] == ref[dst]
      other         r[dst] is something else
    """
    if status == "HANG":
        return "hang", None
    if status != "OK":
        return "fault", None
    if obs is None:
        return "undecodable", None
    if dst in blind:
        return "undecodable", "blind_dst"
    got = obs["regs"][dst]
    want_src = ref[src]
    if dst != src and got == want_src:
        kind = "copy32"
    elif dst == src and got == ref[dst]:
        kind = "copy_self"
    elif got == (want_src & 0xFFFF) and got != want_src:
        kind = "narrow16"
    elif got == 0:
        kind = "zero"
    elif got == ref[dst]:
        kind = "unchanged"
    else:
        kind = "other"
    if kind in ("copy32", "copy_self"):
        outcome = "ok"
    elif kind == "zero":
        outcome = "silent_zero"
    elif kind == "unchanged":
        outcome = "wrong_value"      # the prediction was a MOVE; nothing moved
    else:
        outcome = "wrong_value"
    return outcome, kind


class Log:
    """Append-only JSONL case log, flushed AND fsynced per record."""

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
