#!/usr/bin/env python3
"""EXP-0219 sweep engine for the `imad` arms (G17P).

Engine reused from EXP-0160's `harness/sweeprun.py` (same project, same rules,
cited) with ONE substantive change:

  THE RUNNER IS THE LEAK-FREE ONE.  `tools/agxtest/persistrun.py` still carries
  DEF-0178-1 -- a fresh reader thread per line, abandoned on timeout, which
  re-resolves `self.proc` at execution time and can attach to the REPLACEMENT
  child.  FIELD-SWEEP-PROTOCOL 3(d) is explicit that a mere WATCHDOG TIMEOUT is
  enough to start a cascade of FALSE hangs.  This module therefore drives a
  SafePersistRunner (one pump thread per child, tagged by owner; a malformed
  response recorded as MEASUREMENT FAILURE with the raw lines kept, never as a
  hang), whose shape is EXP-0178's `harness/saferunner.py`, reproduced here so
  neither the shared tool nor EXP-0178's committed harness is executed or
  edited.

Carrier style: SYNTH-WITH-LIFTED-BLOCK.  The whole `_agc.main` is replaced by a
program we assembled from tools/agx-isa's own field rules (seeds -> PRE
sentinel -> BLOCK -> 16-register dump -> POST sentinel -> stop); the BLOCK is a
contiguous run of instructions lifted BYTE-FOR-BYTE from the compiled form of
our own MSL, with the one byte this case sweeps replaced.

CLEAN-ROOM: pure process/file plumbing over our own tools; the only machine code
inspected or spliced is the compiled form of OUR OWN MSL.
"""
from __future__ import print_function

import importlib.util
import json
import os
import queue
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import imad_helpers as H  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _find_tools():
    for cand in (Path.home() / "agxre" / "tools", EXP.parents[1] / "tools"):
        if (cand / "shdump" / "agxparse.py").exists():
            return cand
    raise RuntimeError("cannot locate tools/")


TOOLS = _find_tools()
agxparse = _load("agxparse", TOOLS / "shdump" / "agxparse.py")
# PINNED copy -- a sibling editing ~/agxre/tools mid-run cannot change what we ran.
PERSISTRUN_PATH = EXP / "work" / "frozen" / "persistrun.py"
persistrun = _load("persistrun", PERSISTRUN_PATH)
SHDUMP = TOOLS / "shdump" / "shdump"
AGXRUN_PERSIST = TOOLS / "agxtest" / "agxrun_persist"

VICTIM_MARKERS = ("InnocentVictim", "innocent victim", "Ignored (for causing prior",
                  "IOAF code 4", "IOAF code 2", "Discarded")


def is_victim(err):
    if not err:
        return False
    low = err.lower()
    return any(m.lower() in low for m in VICTIM_MARKERS)


class SafePersistRunner(persistrun.PersistRunner):
    """One pump thread per child, tagged by owner (EXP-0178 saferunner shape).

    A malformed response is a MEASUREMENT FAILURE with the raw lines kept.
    """

    def _install_pump(self):
        self._q = queue.Queue()
        p = self.proc

        def pump():
            try:
                for ln in iter(p.stdout.readline, ""):
                    self._q.put((p, ln))
            except Exception:
                pass
            self._q.put((p, None))
        t = threading.Thread(target=pump, daemon=True)
        t.start()
        self._pump = t

    def _read_line(self, timeout):
        deadline = time.time() + timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                return None
            try:
                owner, ln = self._q.get(timeout=min(left, 0.5))
            except queue.Empty:
                continue
            if owner is not self.proc:
                continue
            return ln

    def _start(self):
        cmd = [self.exe, "--source", self.source, "--function", self.function]
        if not self.fast_math:
            cmd.append("--no-fast-math")
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        self._install_pump()
        ready = self._read_line(timeout=60)
        if not ready or not ready.startswith("READY"):
            raise RuntimeError("agxrun_persist not READY: %r" % (ready,))
        self.device = ready.split(None, 1)[1].strip() if " " in ready else "?"

    def request(self, archive, grid, tg, ins, outs, timeout=8.0):
        self._reqno += 1
        rid = "r%d" % self._reqno
        parts = [rid, archive, str(grid), str(tg), str(len(ins))]
        parts += ["%d:%s" % (i, p) for i, p in ins.items()]
        parts.append(str(len(outs)))
        parts += ["%d:%d" % (i, n) for i, n in outs.items()]
        try:
            self.proc.stdin.write(" ".join(parts) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self._kill()
            self._start()
            return {"status": "HANG", "outs": {}, "gputime_ns": None,
                    "error": "child pipe broken", "restarted": True, "raw": []}
        resp = {"status": "UNKNOWN", "outs": {}, "gputime_ns": None,
                "error": None, "restarted": False, "raw": []}
        while True:
            ln = self._read_line(timeout)
            if ln is None:
                self._kill()
                self._start()
                resp.update(status="HANG", restarted=True,
                            error="no response within %ss" % timeout)
                return resp
            ln = ln.rstrip("\n")
            resp["raw"].append(ln[:32] + ("..%d" % len(ln) if len(ln) > 32 else ""))
            if ln.startswith("STATUS "):
                resp["status"] = ln.split(None, 1)[1]
            elif ln.startswith("GPUTIME_NS "):
                try:
                    resp["gputime_ns"] = int(ln.split(None, 1)[1])
                except ValueError:
                    pass
            elif ln.startswith("OUT "):
                bits = ln.split(None, 2)
                if len(bits) < 3:
                    resp["status"] = "MALFORMED"
                    resp["error"] = "truncated OUT line: %r" % ln[:80]
                    continue
                try:
                    resp["outs"][int(bits[1])] = bytes.fromhex(bits[2])
                except ValueError as e:
                    resp["status"] = "MALFORMED"
                    resp["error"] = "unparseable OUT payload (%s)" % e
            elif ln.startswith("ERROR "):
                resp["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                break
        return resp


class Carrier:
    """One compiled carrier + one live persistent runner."""

    def __init__(self, source, function, workdir, timeout=8.0):
        self.source = Path(source)
        self.function = function
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.base_path = self.workdir / ("base_%s.bin" % function)
        r = subprocess.run([str(SHDUMP), "-o", str(self.base_path),
                            "-f", function, "--no-fast-math", str(self.source)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
        self.runner = SafePersistRunner(
            source=str(self.source), function=function, fast_math=False,
            agxrun_persist=str(AGXRUN_PERSIST))
        self.device = self.runner.device
        self.spliced_path = self.workdir / ("spliced_%s_%d.bin" % (function, os.getpid()))
        self.hangs = 0
        self.poison_path = self._write_poison()

    def _write_poison(self):
        p = self.workdir / ("poison_%d.bin" % os.getpid())
        p.write_bytes(struct.pack("<%dI" % H.OUT_WORDS, *([H.POISON] * H.OUT_WORDS)))
        return str(p)

    def run_program(self, prog, grid=1, tg=1, timeout=None):
        """Splice `prog` over the WHOLE `_agc.main` region and dispatch it.

        GATE A: the spliced window is RE-READ FROM THE FILE handed to Metal and
        returned to the caller as `actual`, so requested-vs-actual is a
        filesystem round trip, not an in-memory assertion.
        """
        if len(prog) != self.region_len:
            raise ValueError("program %d != region %d" % (len(prog), self.region_len))
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + self.region_len] = prog
        self.spliced_path.write_bytes(bytes(spliced))
        back = self.spliced_path.read_bytes()
        actual = back[self.region_off:self.region_off + self.region_len]
        resp = self.runner.request(archive=str(self.spliced_path), grid=grid, tg=tg,
                                   ins={0: self.poison_path},
                                   outs={0: H.OUT_WORDS * 4},
                                   timeout=timeout or self.timeout)
        if resp["status"] == "HANG":
            self.hangs += 1
        raw = resp["outs"].get(0, b"")
        words = [struct.unpack_from("<I", raw, i)[0]
                 for i in range(0, len(raw) - 3, 4)]
        return resp, words, actual

    def restart(self):
        try:
            self.runner.close()
        except Exception:
            try:
                self.runner._kill()
            except Exception:
                pass
        self.runner = SafePersistRunner(
            source=str(self.source), function=self.function, fast_math=False,
            agxrun_persist=str(AGXRUN_PERSIST))

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass


def digest(words):
    regs = [words[H.W_REG0 + i * H.STORE_STRIDE_WORDS] for i in range(H.N_REGS)]
    return {"regs": regs, "pre": words[H.W_PRE], "post": words[H.W_POST]}


def digest_hex(d):
    return "".join("%08x" % v for v in d["regs"]) + "%08x%08x" % (d["pre"], d["post"])


def poison_count(obs):
    if obs is None:
        return None
    return sum(1 for v in obs["regs"] if v == H.POISON)


def classify(status, obs, base):
    if status == "HANG":
        return "hang"
    if status == "MALFORMED":
        return "measurement_failure"
    if status != "OK":
        return "fault"
    if obs is None:
        return "undecodable"
    if obs["regs"] == base["regs"]:
        return "ok"
    bad = [i for i in range(H.N_REGS) if obs["regs"][i] != base["regs"][i]]
    if all(obs["regs"][i] == 0 for i in bad):
        return "silent_zero"
    return "wrong_value"


class Log:
    """Append-only JSONL case log, flushed + fsynced per record."""

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
        self.f.close()
