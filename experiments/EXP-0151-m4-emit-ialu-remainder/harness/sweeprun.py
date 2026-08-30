#!/usr/bin/env python3
"""EXP-0151 sweep engine.

Derived from EXP-0139/harness/sweeprun.py (our own prior tooling) with the
four FIELD-SWEEP-PROTOCOL §7 hardenings this dispatch makes binding:

  1. UNIQUE SPLICE-ARCHIVE PATH PER REQUEST.  EXP-0139 rewrote one fixed path
     (`spliced_<fn>.bin`) for every case; `newLibraryWithURL:` is handed a URL,
     so a same-path rewrite is a caching hazard.  Every request here gets its
     own path and the file is unlinked as soon as the response is read.
  2. POISONED READ-BACK BUFFER.  The output slot is supplied as an INPUT file
     full of 0xDEADBEEF, which `agxrun_persist.m` reuses as the output buffer
     (`if (!bufs[outIdx[i]])`).  An output word that reads 0xDEADBEEF was
     therefore NEVER WRITTEN, which on Apple9 is a different fact from a
     silent zero.
  3. INTEGRITY SENTINEL ON AN INDEPENDENT PATH.  out[1] is written by a second
     device_store using a different index register and a different data
     register (see seedcarrier.py).  A case whose out[1] != 111 is scored
     `void_integrity` and never contributes to a field verdict.
  4. OS FAULT CLASSIFICATION recorded per case, and majority-of-3 before any
     `fault`: a single contained failure is treated as a machine event
     (sibling GPU experiments are live) and re-run.

CLEAN-ROOM: pure process/file plumbing over our own tools; the only machine
code inspected or spliced is the compiled form of our own MSL.
"""
import importlib.util
import json
import os
import struct
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
BIN = EXP / "work" / "bin"

POISON = 0xDEADBEEF


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


agxparse = _load("agxparse", REPO / "tools" / "shdump" / "agxparse.py")
persistrun = _load("persistrun", REPO / "tools" / "agxtest" / "persistrun.py")

# FIELD-SWEEP-PROTOCOL §7.2 -- an `...ErrorInnocentVictim`-class command-buffer
# failure is evidence about the MACHINE, not about our encoding.
VICTIM_MARKERS = ("InnocentVictim", "innocent victim", "Ignored (for causing prior",
                  "IOAF code 4", "IOAF code 2", "Discarded")


def fault_class(err):
    """Coarse class of the OS's own command-buffer error string."""
    if not err:
        return ""
    e = err.lower()
    if any(m.lower() in e for m in VICTIM_MARKERS):
        return "innocent_victim"
    if "hang" in e:
        return "hang"
    if "pagefault" in e or "page fault" in e:
        return "page_fault"
    if "wedged" in e or "no response" in e:
        return "watchdog"
    return "other"


def is_victim(err):
    return fault_class(err) == "innocent_victim"


class Carrier:
    """One compiled carrier + one live persistent runner."""

    def __init__(self, source, function, workdir, timeout=8.0):
        self.source = Path(source)
        self.function = function
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.splicedir = self.workdir / "spl"
        self.splicedir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.base_path = self.workdir / ("base_%s.bin" % function)
        r = subprocess.run([str(BIN / "shdump"), "-o", str(self.base_path),
                            "-f", function, "--no-fast-math", str(self.source)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not self.base_path.exists():
            raise RuntimeError("shdump failed for %s: %s" % (function, r.stderr[-800:]))
        self.basebuf = self.base_path.read_bytes()
        loc = agxparse.locate_region(self.basebuf, "_agc.main")
        if loc is None:
            raise RuntimeError("could not locate _agc.main in %s" % function)
        self.region_off, self.region_len = loc
        _, pieces = agxparse.extract_agx(self.basebuf)
        self.main_bytes = pieces["_agc.main"]
        self.runner = persistrun.PersistRunner(
            source=str(self.source), function=function, fast_math=False,
            agxrun_persist=str(BIN / "agxrun_persist"))
        self.device = self.runner.device
        self.hangs = 0
        self._n = 0
        # the poisoned output slot, supplied as an INPUT so agxrun_persist
        # reuses it as the output buffer (see module docstring, item 2).
        self.poison_path = self.workdir / "poison.bin"
        self.poison_words = 8
        self.poison_path.write_bytes(struct.pack("<%dI" % self.poison_words,
                                                  *([POISON] * self.poison_words)))

    def run(self, program, ins, out_words=8, grid=1, tg=1):
        """`program` replaces the whole `_agc.main` region."""
        if len(program) > self.region_len:
            raise ValueError("program %d > region %d" % (len(program), self.region_len))
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + len(program)] = program
        self._n += 1
        path = self.splicedir / ("s%08d.bin" % self._n)
        path.write_bytes(bytes(spliced))
        allins = dict(ins)
        allins[0] = str(self.poison_path)          # poison the read-back slot
        try:
            resp = self.runner.request(archive=str(path), grid=grid, tg=tg,
                                       ins=allins, outs={0: out_words * 4},
                                       timeout=self.timeout)
        finally:
            try:
                path.unlink()
            except OSError:
                pass
        if resp["status"] == "HANG":
            self.hangs += 1
        raw = resp["outs"].get(0, b"")
        iw = [struct.unpack_from("<I", raw, i)[0] for i in range(0, len(raw) - 3, 4)]
        return resp, iw

    def restart(self):
        try:
            self.runner.close()
        except Exception:
            self.runner._kill()
        self.runner = persistrun.PersistRunner(
            source=str(self.source), function=self.function, fast_math=False,
            agxrun_persist=str(BIN / "agxrun_persist"))

    def write_input(self, name, words, kind="I"):
        p = self.workdir / name
        p.write_bytes(b"".join(struct.pack("<" + kind, v) for v in words))
        return str(p)

    def close(self):
        self.runner.close()


class Log:
    """Append-only JSONL case log, flushed+fsynced per record."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "a", buffering=1)
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


def classify(status, err, words, oracle, sentinel_word, sentinel_value):
    """FIELD-SWEEP-PROTOCOL §4 `outcome`, plus this experiment's two extra
    classes (`not_written` for the 0xDEADBEEF poison, `void_integrity` for a
    failed independent-path sentinel)."""
    if status == "HANG":
        return "hang", False
    if status != "OK":
        return ("victim" if is_victim(err) else "fault"), False
    if not words or len(words) <= sentinel_word:
        return "undecodable", False
    if words[sentinel_word] != sentinel_value:
        return "void_integrity", False
    got = words[0]
    if got == POISON:
        return "not_written", False
    if oracle is None:
        return "observed", False
    if got == (oracle & 0xFFFFFFFF):
        return "ok", True
    if got == 0:
        return "silent_zero", False
    return "wrong_value", False
