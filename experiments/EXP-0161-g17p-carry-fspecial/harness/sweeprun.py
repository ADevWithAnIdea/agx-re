#!/usr/bin/env python3
"""EXP-0161 sweep engine (G17P).

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified -- and specifically
the version carrying the DEF-0153-2 fix, whose sha256 is frozen in
CAPTURE_CONTRACT.json) so a whole field sweep is ONE `agxrun_persist` process.

Two carrier styles, both used by this experiment:

  SYNTH+LIFTED  the whole `_agc.main` is replaced by a program assembled from
                `tools/agx-isa`'s own field rules, whose seeds come from an
                authored SEED buffer via device_load, and whose BLOCK is
                lifted byte-for-byte from the compiled form of our own MSL.
                Oracle: the full 16-register architectural dump.

  INPLACE       the naturally compiled `_agc.main` of one of our own probe
                kernels, with ONE instruction's bytes mutated in place and
                everything else left as the compiler produced it. Oracle: a
                HOST-COMPUTED functional result over an authored input vector.
                This is the independent second method for `carry_gen` and
                `fspecial`.

Records are appended to `<run>/sweep.jsonl` and flushed+fsynced IMMEDIATELY.

CLEAN-ROOM: pure process/file plumbing over our own tools; the only machine
code inspected or spliced is the compiled form of OUR OWN MSL.
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


def _find_tools():
    env = os.environ.get("AGX_TOOLS")
    cands = [Path(env)] if env else []
    cands += [EXP.parents[1] / "tools", Path.home() / "agxre" / "tools"]
    for c in cands:
        if (c / "shdump" / "agxparse.py").exists():
            return c
    raise RuntimeError("cannot locate tools/")


TOOLS = _find_tools()
agxparse = _load("agxparse", TOOLS / "shdump" / "agxparse.py")
persistrun = _load("persistrun", TOOLS / "agxtest" / "persistrun.py")
SHDUMP = TOOLS / "shdump" / "shdump"
AGXRUN_PERSIST = TOOLS / "agxtest" / "agxrun_persist"

# FIELD-SWEEP-PROTOCOL 7.2: an `...ErrorInnocentVictim`-class command-buffer
# failure is evidence about the MACHINE (a sibling GPU context's fault landing
# in ours after a device reset), not about our encoding.
VICTIM_MARKERS = ("InnocentVictim", "innocent victim",
                  "Ignored (for causing prior", "IOAF code 4", "IOAF code 2",
                  "Discarded")


def is_victim(err):
    if not err:
        return False
    low = err.lower()
    return any(m.lower() in low for m in VICTIM_MARKERS)


class Carrier:
    """One compiled carrier MSL + one live persistent runner."""

    def __init__(self, source, function, workdir, timeout=8.0, fast_math=False,
                 inputs=None, outs=None):
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
        self.spliced_path = self.workdir / ("spliced_%s_%d.bin"
                                            % (function, os.getpid()))
        self.hangs = 0
        # authored input files, written once
        self.inputs = {}
        for idx, (name, blob) in (inputs or {}).items():
            p = self.workdir / ("in_%d_%s" % (os.getpid(), name))
            p.write_bytes(blob)
            self.inputs[idx] = str(p)
        self.outs = dict(outs or {})

    # -- SYNTH: replace the whole region -----------------------------------
    def run_program(self, prog, grid=1, tg=1, timeout=None):
        if len(prog) != self.region_len:
            raise ValueError("program %d != region %d"
                             % (len(prog), self.region_len))
        return self._dispatch(prog, grid, tg, timeout)

    # -- INPLACE: mutate `nbytes` at `off` inside the natural main ---------
    def run_inplace(self, off, newbytes, grid=1, tg=1, timeout=None):
        m = bytearray(self.main_bytes)
        m[off:off + len(newbytes)] = newbytes
        prog = bytes(m) + b"\x00" * (self.region_len - len(m))
        return self._dispatch(prog, grid, tg, timeout)

    def _dispatch(self, prog, grid, tg, timeout):
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + self.region_len] = prog
        self.spliced_path.write_bytes(bytes(spliced))
        resp = self.runner.request(archive=str(self.spliced_path), grid=grid,
                                   tg=tg, ins=self.inputs, outs=self.outs,
                                   timeout=timeout or self.timeout)
        if resp["status"] == "HANG":
            self.hangs += 1
        return resp, resp["outs"]

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


def words_u32(raw):
    return [struct.unpack_from("<I", raw, i)[0]
            for i in range(0, len(raw) - 3, 4)]


def digest(words):
    """The 18 words this experiment interprets: r0..r15, PRE, POST."""
    if not words or len(words) < H.OUT_WORDS:
        return None
    regs = [words[H.W_REG0 + i * H.STORE_STRIDE_WORDS] for i in range(H.N_REGS)]
    return {"regs": regs, "pre": words[H.W_PRE], "post": words[H.W_POST]}


def digest_hex(d):
    return "".join("%08x" % v for v in d["regs"]) + \
           "%08x%08x" % (d["pre"], d["post"])


class Log:
    """Append-only JSONL case log, flushed+fsynced per record."""

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


def classify_synth(status, obs, base):
    """FIELD-SWEEP-PROTOCOL section 4 outcome for a SYNTH case.

    `ok` requires the FULL 16-register architectural state after the block to
    match the unmutated anchor's -- strictly stronger than a single output
    word, because a value that computes the right answer but disturbs another
    register is not interchangeable for an emitter."""
    if status == "HANG":
        return "hang"
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


def classify_inplace(status, got, oracle, poison):
    """Outcome for an INPLACE case against a HOST-COMPUTED oracle.

    `poison` is the list of poison words the read-back buffer was pre-filled
    with; a word that still holds its own poison was NEVER WRITTEN, which
    FIELD-SWEEP-PROTOCOL 7A calls out as the cheap offline adjudicator for a
    suspect fault."""
    if status == "HANG":
        return "hang", None
    if status != "OK":
        return "fault", None
    if got is None:
        return "undecodable", None
    npois = sum(1 for i, v in enumerate(got) if i < len(poison) and v == poison[i])
    if got == oracle:
        return "ok", npois
    if npois == len(got):
        return "silent_zero", npois        # nothing was written at all
    if all(v == 0 for v in got):
        return "silent_zero", npois
    return "wrong_value", npois
