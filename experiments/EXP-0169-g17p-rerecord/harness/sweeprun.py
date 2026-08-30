#!/usr/bin/env python3
"""EXP-0169 sweep engine (G17P).

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified) so a whole field
sweep is ONE `agxrun_persist` process per carrier: the carrier MSL is compiled
once with `tools/shdump`, `_agc.main` is located once with
`tools/shdump/agxparse.py`, and each case then splices its own program over the
region and issues one request.

Two splice styles:
  * SYNTH-WITH-LIFTED-BLOCK (EXP-0154) -- the whole `_agc.main` is replaced by a
    program we assembled from `tools/agx-isa`'s own field rules, containing a
    block lifted BYTE-FOR-BYTE from the compiled form of our own MSL;
  * NATIVE (EXP-0139) -- the probe kernel's own `_agc.main` with ONE instruction
    replaced in place, then run unmodified and read through its own output.
    Used only where the effect is unobservable in a straight-line program.

Records are appended to `<run_dir>/sweep.jsonl` and flushed+fsynced IMMEDIATELY.

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
    for cand in (EXP.parents[1] / "tools", Path.home() / "agxre" / "tools"):
        if (cand / "shdump" / "agxparse.py").exists():
            return cand
    raise RuntimeError("cannot locate tools/")


TOOLS = _find_tools()
agxparse = _load("agxparse", TOOLS / "shdump" / "agxparse.py")
persistrun = _load("persistrun", TOOLS / "agxtest" / "persistrun.py")
SHDUMP = TOOLS / "shdump" / "shdump"
AGXRUN_PERSIST = TOOLS / "agxtest" / "agxrun_persist"

OUTCOMES = ("ok", "silent_zero", "wrong_value", "fault", "hang", "undecodable")

# FIELD-SWEEP-PROTOCOL 7.2: an `...ErrorInnocentVictim`-class command-buffer
# failure is evidence about the MACHINE (a sibling GPU context's fault splashing
# into ours after a device reset), not about our encoding. Matched against the
# OS's own localizedDescription, printed verbatim by agxrun_persist.
# EXP-0158/EXP-0160 showed this is NOT a complete defence: contamination can
# arrive with no victim string at all, and a contaminated dispatch can report
# STATUS OK and write nothing. That is why the poison and the sentinels are
# adjudicated offline as well.
VICTIM_MARKERS = ("InnocentVictim", "innocent victim",
                  "Ignored (for causing prior", "IOAF code 4", "IOAF code 2",
                  "Discarded")


def is_victim(err):
    if not err:
        return False
    low = err.lower()
    return any(m.lower() in low for m in VICTIM_MARKERS)


# Word indices the synthesized program itself writes.
KNOWN_WORDS = set([H.W_REG0 + i * H.STORE_STRIDE_WORDS for i in range(H.N_REGS)]
                  + [H.W_PRE, H.W_POST])


class Carrier:
    """One compiled carrier + one live persistent runner."""

    def __init__(self, source, function, workdir, timeout=8.0, extra_ins=None):
        self.source = Path(source)
        self.function = function
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.extra_ins = dict(extra_ins or {})
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
        self.runner = persistrun.PersistRunner(
            source=str(self.source), function=function, fast_math=False,
            agxrun_persist=str(AGXRUN_PERSIST))
        self.device = self.runner.device
        self.spliced_path = self.workdir / ("spliced_%s_%d.bin"
                                            % (function, os.getpid()))
        self.hangs = 0
        self._poison = {}

    def poison_path(self, out_words):
        p = self._poison.get(out_words)
        if p is None:
            p = self.workdir / ("poison_%d_%d.bin" % (out_words, os.getpid()))
            p.write_bytes(struct.pack("<%dI" % out_words,
                                      *([H.POISON] * out_words)))
            p = str(p)
            self._poison[out_words] = p
        return p

    def run_program(self, prog, out_words=None, grid=1, tg=1, timeout=None):
        """Splice `prog` over the WHOLE `_agc.main` region and dispatch it."""
        out_words = out_words or H.OUT_WORDS
        if len(prog) != self.region_len:
            raise ValueError("program %d != region %d"
                             % (len(prog), self.region_len))
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + self.region_len] = prog
        self.spliced_path.write_bytes(bytes(spliced))
        ins = {0: self.poison_path(out_words)}
        ins.update(self.extra_ins)
        resp = self.runner.request(archive=str(self.spliced_path), grid=grid,
                                   tg=tg, ins=ins, outs={0: out_words * 4},
                                   timeout=timeout or self.timeout)
        if resp["status"] == "HANG":
            self.hangs += 1
        raw = resp["outs"].get(0, b"")
        words = [struct.unpack_from("<I", raw, i)[0]
                 for i in range(0, len(raw) - 3, 4)]
        return resp, words

    def run_native(self, patched_main, out_slot, out_words, grid=8, tg=8,
                   timeout=None):
        """NATIVE mode: run the probe kernel's own `_agc.main` with one
        instruction replaced in place, and read the kernel's OWN output
        buffer."""
        prog = patched_main
        if len(prog) < self.region_len:
            prog = prog + b"\x00" * (self.region_len - len(prog))
        if len(prog) != self.region_len:
            raise ValueError("native program %d != region %d"
                             % (len(prog), self.region_len))
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + self.region_len] = prog
        self.spliced_path.write_bytes(bytes(spliced))
        ins = {out_slot: self.poison_path(out_words)}
        ins.update({k: v for k, v in self.extra_ins.items() if k != out_slot})
        resp = self.runner.request(archive=str(self.spliced_path), grid=grid,
                                   tg=tg, ins=ins, outs={out_slot: out_words * 4},
                                   timeout=timeout or self.timeout)
        if resp["status"] == "HANG":
            self.hangs += 1
        raw = resp["outs"].get(out_slot, b"")
        words = [struct.unpack_from("<I", raw, i)[0]
                 for i in range(0, len(raw) - 3, 4)]
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
            source=str(self.source), function=self.function, fast_math=False,
            agxrun_persist=str(AGXRUN_PERSIST))

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass


def digest(words):
    """The architectural state this experiment interprets: r0..r15, the two
    sentinels, and every OTHER word that is no longer poison (which is how the
    device_store arm sees where its probe store landed)."""
    if len(words) <= H.W_POST:
        return None
    regs = [words[H.W_REG0 + i * H.STORE_STRIDE_WORDS] for i in range(H.N_REGS)]
    stray = [[i, words[i]] for i in range(len(words))
             if i not in KNOWN_WORDS and words[i] != H.POISON]
    return {"regs": regs, "pre": words[H.W_PRE], "post": words[H.W_POST],
            "stray": stray[:64], "n_stray": len(stray)}


def digest_hex(d):
    if d is None:
        return None
    return ("".join("%08x" % v for v in d["regs"])
            + "%08x%08x" % (d["pre"], d["post"])
            + "|" + ",".join("%d:%08x" % (i, v) for i, v in d["stray"]))


def native_digest(words):
    """NATIVE mode observation: the kernel's own output, verbatim."""
    return {"out": words[:32], "n_poison": sum(1 for w in words if w == H.POISON)}


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


def classify(status, obs, base):
    """FIELD-SWEEP-PROTOCOL section 4 `outcome` for one case.

    `ok` requires the FULL architectural state after the block to match the
    unmutated anchor's -- 16 registers, both sentinels, and the stray-word map.
    That is strictly stronger than a single output word, and it is what makes a
    field whose effect is *where* a result lands visible at all."""
    if status == "HANG":
        return "hang"
    if status != "OK":
        return "fault"
    if obs is None or base is None:
        return "undecodable"
    if "regs" not in obs or "regs" not in base:
        # NATIVE mode: the observation is the probe kernel's own output, which
        # has no register dump to decompose. Any difference is a difference.
        return "ok" if obs == base else "wrong_value"
    if obs["regs"] != base["regs"]:
        bad = [i for i in range(H.N_REGS) if obs["regs"][i] != base["regs"][i]]
        if all(obs["regs"][i] == 0 for i in bad):
            return "silent_zero"
        return "wrong_value"
    if obs["stray"] != base["stray"]:
        return "wrong_value"
    if obs["pre"] != base["pre"] or obs["post"] != base["post"]:
        return "wrong_value"
    return "ok"
