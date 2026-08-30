#!/usr/bin/env python3
"""EXP-0179 sweep engine: carrier, dispatch, observation, classification.

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified) so a whole sweep is
ONE `agxrun_persist` process. Structure reused and cited from
EXP-0168 -> EXP-0174/harness/sweeprun.py (same project, same rules): the
`SynthCarrier` shape, the poison file, the append-only `Log`, `validity_of`,
`is_victim`, `os_class` and the victim-marker list.

WHAT IS NEW HERE
----------------
`classify_call()` answers the question this experiment exists to ask, entirely
from the HOST-KNOWN seed table plus the fixed dump:

    callee_ran   -- the callee's memory breadcrumb is no longer POISON AND the
                    callee register holds CALLEE_CONST. The breadcrumb is written
                    INSIDE the callee, so "ran but never returned" survives even
                    when the caller-side dump never executes.
    returned     -- the post-call marker register holds POSTCALL.
    landing_rung -- the lowest landing-ladder rung that fired; None means control
                    entered at or after the callee entry. This localises a
                    mis-targeted branch to 2 bytes.

No GPU-measured baseline enters any of it (DEF-0169-1: a diff against a
periodically-refreshed baseline fabricates movement).

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
import saferunner       # noqa: E402  (DEF-0178-1 / FIELD-SWEEP-PROTOCOL 3d)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def find_tools():
    """FAIL-CLOSED, exactly one candidate. The shared ~/agxre/tools on the neo is
    stale and must never be silently used."""
    cand = EXP / "tools"
    if (cand / "shdump" / "agxparse.py").exists():
        return cand
    raise RuntimeError("PINNED TOOLS MISSING: %s (no path-search fallback)" % cand)


TOOLS = find_tools()
agxparse = _load("agxparse", TOOLS / "shdump" / "agxparse.py")
persistrun = _load("persistrun", TOOLS / "agxtest" / "persistrun.py")
SHDUMP = TOOLS / "shdump" / "shdump"
AGXRUN_PERSIST = TOOLS / "agxtest" / "agxrun_persist"

# DEF-0178-1 / FIELD-SWEEP-PROTOCOL 3(d): the shared PersistRunner abandons a
# reader thread on every watchdog timeout, so THE FIRST HANG CAN SILENTLY
# MANUFACTURE EVERY HANG AFTER IT. Arms G/T/M/B3/B5/B6/TL/R/L and arm S produced
# 0 hangs in 10,484 dispatches, so none of them can be an artefact of it -- but
# the tail (N, F, O) is expected to hang for real, and a false cascade after arm
# N's first genuine hang would corrupt F and O. Every runner this experiment
# constructs is therefore the leak-free subclass. The shared file is NOT
# modified: other experiments are running against it.
RUNNER = saferunner.make_safe_runner(persistrun.PersistRunner)

OUTCOMES = ("ok", "silent_zero", "wrong_value", "fault", "hang", "undecodable")
VALIDITIES = ("valid", "invalid_poison", "invalid_sentinel", "invalid_victim",
              "invalid_nodata", "invalid_malformed")

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
        self.runner = RUNNER(
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

    def write_input(self, name, words):
        p = self.workdir / ("in_%s_%d.bin" % (name, os.getpid()))
        p.write_bytes(struct.pack("<%dI" % len(words), *words))
        return str(p)

    def run_program(self, prog, grid=1, tg=1, timeout=None, extra_ins=None):
        if len(prog) != self.region_len:
            raise ValueError("program %d != region %d" % (len(prog), self.region_len))
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + self.region_len] = prog
        self.spliced_path.write_bytes(bytes(spliced))
        ins = {0: self.poison_path}
        if extra_ins:
            ins.update(extra_ins)
        resp = self.runner.request(archive=str(self.spliced_path), grid=grid,
                                   tg=tg, ins=ins,
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
        self.runner = RUNNER(
            source=str(self.source), function=self.function,
            fast_math=self.fast_math, agxrun_persist=str(AGXRUN_PERSIST))

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass


class SpliceCarrier(SynthCarrier):
    """Arm S: the REAL compiler-emitted call inside our own compiled program is
    mutated in place. Its bytes come from a compiled shader, so it is an
    INDEPENDENT SECOND METHOD and never counts toward the generated-result bar.
    """

    def find_call_sites(self):
        """Byte-scan `_agc.main` (and the whole region) for the descriptor's own
        byte-aligned `match` pins for `call`. Position-independent; does not
        depend on the length rule being right."""
        import isadb
        cons = None
        for i in isadb.DB:
            if i["mnemonic"] == "call":
                cons = [(s // 8, v) for (s, w, v) in i["match"]]
        buf = self.basebuf[self.region_off:self.region_off + self.region_len]
        span = max(o for o, _ in cons) + 1
        return [p for p in range(len(buf) - span + 1)
                if all(buf[p + o] == v for o, v in cons)]

    def run_mutated(self, site, byte_index, value, timeout=None):
        buf = bytearray(self.basebuf[self.region_off:
                                     self.region_off + self.region_len])
        buf[site + byte_index] = value
        return self.run_program(bytes(buf), timeout=timeout)


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------
def digest(words):
    if not words or len(words) < H.OUT_WORDS:
        return None
    regs = [words[H.W_REG0 + i * H.STORE_STRIDE_WORDS] for i in range(H.N_REGS)]
    tail = words[H.W_TAIL:H.W_TAIL + H.N_TAIL_WORDS]
    return {"regs": regs, "pre": words[H.W_PRE], "post": words[H.W_POST],
            "callee_word": words[H.W_CALLEE],
            "tail_ok": all(t == H.POISON for t in tail),
            "all_poison": all(w == H.POISON for w in words)}


def digest_hex(d):
    if not d:
        return None
    return ("".join("%08x" % v for v in d["regs"])
            + "%08x%08x%08x" % (d["pre"], d["post"], d["callee_word"]))


def validity_of(status, err, d):
    """Run integrity, kept strictly separate from the FIELD-SWEEP-PROTOCOL
    `outcome` enum.

    NOTE the POST sentinel is written AFTER the call returns, so a program in
    which the call legitimately never returns has no POST sentinel. That is a
    RESULT, not an invalid run, and it is distinguished from a broken dispatch by
    the PRE sentinel (written BEFORE the call) and by the tail poison.
    """
    if status == "MALFORMED":
        # DEF-0178-1: a truncated/unparseable response is a MEASUREMENT FAILURE,
        # not an observation. It is re-run, never scored -- a false `hang` and a
        # real inertness are indistinguishable in a summary.
        return "invalid_malformed"
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
    return "valid"


def landing_rung(regs):
    """Lowest landing-ladder rung whose register holds its rung value.

    None = control entered at or after the callee entry (the correct target).
    j    = control entered at ladder rung j, i.e. 2*(len-j) bytes EARLY.
    """
    fired = [j for j in range(len(H.LADDER_R))
             if regs[H.LADDER_R[j]] == H.LADDER_V[j]]
    return min(fired) if fired else None


def classify_call(status, d, plan, expect_called=True, expect_returned=True,
                  expect_rung=None, callee_extra=()):
    """The call oracle. Everything below is computed on the HOST from
    `H.SEED_I` and the fixed dump; no GPU baseline is consulted.

    Returns (outcome, facts) with facts:
      callee_ran, returned, landing, breadcrumb, collateral, match
    """
    if status == "HANG":
        return "hang", {"callee_ran": None, "returned": None, "landing": None,
                        "breadcrumb": None, "collateral": None, "match": False}
    if status == "MALFORMED":
        return "undecodable", {"callee_ran": None, "returned": None,
                               "landing": None, "breadcrumb": None,
                               "collateral": None, "match": False,
                               "kind": "malformed_response"}
    if status != "OK":
        return "fault", {"callee_ran": None, "returned": None, "landing": None,
                         "breadcrumb": None, "collateral": None, "match": False}
    if d is None:
        return "undecodable", {"callee_ran": None, "returned": None,
                               "landing": None, "breadcrumb": None,
                               "collateral": None, "match": False}
    regs = d["regs"]
    bc = d["callee_word"]
    callee_ran = (bc != H.POISON) or (regs[plan.callee] == H.CALLEE_CONST)
    returned = (regs[plan.post] == H.POSTCALL) and (d["post"] == H.SENT_POST)
    land = landing_rung(regs)
    exp = H.expected_dump(plan, called=expect_called, returned=expect_returned,
                          rungs_from=expect_rung, callee_extra=callee_extra)
    collateral = [i for i in range(H.N_REGS)
                  if i not in plan.blind and regs[i] != exp[i]]
    facts = {"callee_ran": bool(callee_ran), "returned": bool(returned),
             "landing": land, "breadcrumb": bc, "collateral": collateral,
             "match": (len(collateral) == 0)}
    if facts["match"] and callee_ran == expect_called \
       and returned == expect_returned and land == expect_rung:
        return "ok", facts
    if expect_called and not callee_ran and returned:
        facts["kind"] = "no_call"
        return "wrong_value", facts
    if callee_ran and expect_returned and not returned:
        facts["kind"] = "no_return"
        return "wrong_value", facts
    if callee_ran and land != expect_rung:
        facts["kind"] = "mis_target"
        return "wrong_value", facts
    if regs[plan.callee] == 0 and expect_called:
        facts["kind"] = "callee_zero"
        return "silent_zero", facts
    facts["kind"] = "other"
    return "wrong_value", facts


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
