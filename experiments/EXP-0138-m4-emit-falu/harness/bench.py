#!/usr/bin/env python3
"""EXP-0138 hardware bench: one persistent M4 device, many spliced programs.

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified) so a dense field
sweep is ONE process launch instead of one per case, per
`experiments/FIELD-SWEEP-PROTOCOL.md` section 2.

It implements every contamination mitigation FIELD-SWEEP-PROTOCOL.md section 7
now makes binding, plus EXP-0140's poisoned-buffer correction:

  M1  UNIQUE splice-archive path per request. Reusing one path produced ~8%
      phantom `CMDBUF_ERROR` in a sibling experiment (and in this one's own
      pilot, PROGRESS.md M1).
  M2  POISONED output buffer. `agxrun_persist` only allocates an output
      buffer if that index was not also given as an INPUT -- so the harness
      passes the output index as an input file full of 0xDEADBEEF. "Nothing
      was written" is then distinguishable from "zero was written", which is
      the exact mistake EXP-0140 had to retract.
  M3  MAJORITY-OF-3 before any `fault` verdict. A single non-OK observation
      is never a property of the field (section 7.1).
  M4  The OS fault-classification string is recorded verbatim, and
      `InnocentVictim` / `Discarded` classes are segregated as machine
      evidence, not encoding evidence (section 7.2).
  M5  Periodic BASELINE re-validation. If the unmutated program starts
      failing we are in a GPU error cascade: the child is restarted and the
      event recorded (section 7.3).
  M6  INTEGRITY SENTINEL. Every MODE-A program writes a control register,
      seeded by an instruction independent of the one under test, to its own
      output word; and every case checks that the poison is gone from the
      words the program should have written. A case whose sentinel fails is
      `invalid_run`, never a field observation.

CLEAN-ROOM: pure process/file plumbing over our own tools. No Apple binary is
disassembled or introspected.
"""
import importlib.util
import os
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "shdump"))
import agxparse  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


PersistRunner = _load("persistrun", str(REPO / "tools" / "agxtest" / "persistrun.py")).PersistRunner

POISON = 0xDEADBEEF
POISON_F = struct.unpack("<f", struct.pack("<I", POISON))[0]

# Fault-classification substrings that mean "another process on this GPU
# faulted and our command buffer was collateral" -- machine evidence, not
# encoding evidence (FIELD-SWEEP-PROTOCOL section 7.2).
VICTIM_MARKERS = ("Discarded", "victim of GPU error", "InnocentVictim")


class Bench:
    def __init__(self, source, function, bin_dir, workdir, fast_math=False,
                 timeout=12.0):
        self.source = str(source)
        self.function = function
        self.bin_dir = Path(bin_dir)
        self.work = Path(workdir)
        self.work.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.fast_math = fast_math
        self.hangs = 0
        self.victim_retries = 0
        self.repeats = 0
        self.restarts = 0
        self.cascades = []
        base = self.work / ("base_%s.bin" % function)
        cmd = [str(self.bin_dir / "shdump"), "-o", str(base), "-f", function]
        if not fast_math:
            cmd.append("--no-fast-math")
        cmd.append(self.source)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not base.exists():
            raise RuntimeError("shdump failed for %s: %s" % (function, r.stderr))
        self.basebuf = base.read_bytes()
        loc = agxparse.locate_region(self.basebuf, "_agc.main")
        if loc is None:
            raise RuntimeError("could not locate _agc.main in %s" % base)
        self.region_off, self.region_len = loc
        _, pieces = agxparse.extract_agx(self.basebuf)
        self.main_bytes = pieces["_agc.main"]
        assert len(self.main_bytes) == self.region_len
        self._n = 0
        self._start()

    def _start(self):
        self.runner = PersistRunner(source=self.source, function=self.function,
                                    fast_math=self.fast_math,
                                    agxrun_persist=str(self.bin_dir / "agxrun_persist"))
        self.device = self.runner.device

    def restart(self, why):
        """M5: leave a GPU error cascade behind by starting a fresh child."""
        self.restarts += 1
        self.cascades.append(why)
        try:
            self.runner.close()
        except Exception:
            pass
        self._start()

    # -- input/output plumbing -------------------------------------------
    def write_in(self, idx, values, fmt="<f"):
        p = self.work / ("in%d.bin" % idx)
        p.write_bytes(b"".join(struct.pack(fmt, v) for v in values))
        return str(p)

    def poison_file(self, nbytes):
        """M2: the file bound at the OUTPUT index, pre-filled with 0xDEADBEEF."""
        p = self.work / ("poison_%d.bin" % nbytes)
        if not p.exists():
            p.write_bytes(struct.pack("<I", POISON) * (nbytes // 4))
        return str(p)

    def _splice(self, pairs):
        """M1: a UNIQUE archive path per request."""
        buf = bytearray(self.basebuf)
        for off, data in pairs:
            if off + len(data) > self.region_len:
                raise ValueError("splice %d+%d exceeds region %d" % (off, len(data), self.region_len))
            buf[self.region_off + off: self.region_off + off + len(data)] = data
        self._n += 1
        p = self.work / ("sp_%08d.bin" % self._n)
        p.write_bytes(bytes(buf))
        return p

    def _once(self, pairs, ins, outs, grid, tg):
        p = self._splice(pairs)
        try:
            resp = self.runner.request(archive=str(p), grid=grid, tg=tg, ins=ins,
                                       outs=outs, timeout=self.timeout)
        finally:
            try:
                p.unlink()
            except OSError:
                pass
        if resp["status"] == "HANG":
            self.hangs += 1
        return resp

    def run(self, pairs, ins, outs, grid=1, tg=1, max_victim=6, majority=3):
        """One case. Returns the winning response plus `attempts` (the list of
        (status, error) actually observed) and `victim_retries`.

        M3/M4: a non-OK result is repeated until either it is confirmed
        (`majority` observations agreeing on the same status class) or an OK
        appears. `InnocentVictim`/`Discarded` failures do not count towards
        the majority at all -- they carry no information about our bytes."""
        attempts = []
        victims = 0
        agree = {}
        while True:
            resp = self._once(pairs, ins, outs, grid, tg)
            err = resp.get("error") or ""
            klass = self._klass(resp["status"], err)
            attempts.append({"status": resp["status"], "class": klass, "error": err[:160]})
            if klass == "victim":
                victims += 1
                self.victim_retries += 1
                if victims <= max_victim:
                    continue
                resp["outcome_class"] = "victim"
                break
            if resp["status"] == "OK":
                resp["outcome_class"] = "ok"
                break
            agree[klass] = agree.get(klass, 0) + 1
            if agree[klass] >= majority:
                resp["outcome_class"] = klass
                break
            self.repeats += 1
            if len(attempts) > majority + max_victim + 2:
                resp["outcome_class"] = "unstable"
                break
        resp["attempts"] = attempts
        resp["victim_retries"] = victims
        return resp

    @staticmethod
    def _klass(status, err):
        if status == "OK":
            return "ok"
        if any(m in err for m in VICTIM_MARKERS):
            return "victim"
        if status == "HANG":
            return "hang"
        return status.lower()

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass


def words_f32(raw, n):
    return [struct.unpack_from("<f", raw, 4 * i)[0] for i in range(min(n, len(raw) // 4))]


def words_u32(raw, n):
    return [struct.unpack_from("<I", raw, 4 * i)[0] for i in range(min(n, len(raw) // 4))]


def halfs(raw, n):
    return [struct.unpack_from("<e", raw, 2 * i)[0] for i in range(min(n, len(raw) // 2))]
