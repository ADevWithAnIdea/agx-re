#!/usr/bin/env python3
"""EXP-0139 sweep engine.

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified) so a whole field
sweep is ONE `agxrun_persist` process: the carrier MSL is compiled once with
`tools/shdump`, `_agc.main` is located once with `tools/shdump/agxparse.py`,
and each case then splices its own bytes into a copy of that archive and issues
one request.

Two carrier styles are supported, both used by this experiment:

  SYNTH   -- the whole `_agc.main` is replaced by a program we assembled from
             `tools/agx-isa`'s own field rules (`splice_at=0`, full program).
             Used where a prior experiment already HW-VALIDATED enough field
             rules to build the instruction from scratch (iadd2, ibitcount).
  NATURAL -- our own compiled MSL is left intact and exactly ONE instruction's
             bytes are overwritten in place. Used where the family's operand
             map is still `corpus-correlation` and a from-scratch build would
             conflate "field is inert" with "I guessed the operand map wrong"
             (ibfe, ibfins, imad, iminmax, isel*). The field is live on the
             output path by construction: the carrier's own `device_store`
             reads the instruction's result.

Records are appended to `<run_dir>/sweep.jsonl` and fflush+fsync'd IMMEDIATELY
(SUBAGENT_BRIEF: "assume the host will crash mid-run"). Exactly the key set
`experiments/FIELD-SWEEP-PROTOCOL.md` §4 mandates is emitted.

CLEAN-ROOM: pure process/file plumbing over our own tools; the only machine
code ever inspected or spliced is the compiled form of OUR OWN MSL
(kernels/*.metal). No Apple binary is disassembled or introspected.
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


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


agxparse = _load("agxparse", REPO / "tools" / "shdump" / "agxparse.py")
persistrun = _load("persistrun", REPO / "tools" / "agxtest" / "persistrun.py")

OUTCOMES = ("ok", "silent_zero", "wrong_value", "fault", "hang", "undecodable")


class Carrier:
    """One compiled carrier + one live persistent runner."""

    def __init__(self, source, function, workdir, timeout=8.0):
        self.source = Path(source)
        self.function = function
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.base_path = self.workdir / ("base_%s.bin" % function)
        r = subprocess.run([str(BIN / "shdump"), "-o", str(self.base_path),
                            "-f", function, "--no-fast-math", str(self.source)],
                           capture_output=True, text=True, timeout=180)
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
        self.spliced_path = self.workdir / ("spliced_%s.bin" % function)
        self.hangs = 0

    def run(self, splices, ins, out_slot, out_words, grid=1, tg=1):
        """splices: list of (offset_into_main, bytes). Returns
        (resp, int_words, float_words)."""
        spliced = bytearray(self.basebuf)
        for off, blob in splices:
            if off + len(blob) > self.region_len:
                raise ValueError("splice %d+%d exceeds region %d" % (off, len(blob), self.region_len))
            spliced[self.region_off + off:self.region_off + off + len(blob)] = blob
        self.spliced_path.write_bytes(bytes(spliced))
        resp = self.runner.request(archive=str(self.spliced_path), grid=grid, tg=tg,
                                   ins=ins or {}, outs={out_slot: out_words * 4},
                                   timeout=self.timeout)
        if resp["status"] == "HANG":
            self.hangs += 1
        raw = resp["outs"].get(out_slot, b"")
        iw = [struct.unpack_from("<I", raw, i)[0] for i in range(0, len(raw) - 3, 4)]
        fw = [struct.unpack_from("<f", raw, i)[0] for i in range(0, len(raw) - 3, 4)]
        return resp, iw, fw

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


def classify(status, observed, oracle):
    """FIELD-SWEEP-PROTOCOL §4 `outcome` for one case.

    `observed`/`oracle` are dicts {word_index: value}. A wrong result whose
    every mismatching word is 0 is a `silent_zero` (the Apple9 failure mode
    docs/evidence-classification.md §5 warns about); anything else wrong is
    `wrong_value`."""
    if status == "HANG":
        return "hang", False
    if status != "OK":
        return "fault", False
    if observed is None or any(v is None for v in observed.values()):
        return "undecodable", False
    if observed == oracle:
        return "ok", True
    bad = [k for k in oracle if observed.get(k) != oracle[k]]
    if all(observed.get(k) == 0 for k in bad):
        return "silent_zero", False
    return "wrong_value", False


def _compile_only(source, function, workdir):
    """Compile `function` from `source` with tools/shdump and return the raw
    `_agc.main` bytes -- no device, no dispatch. Used by casematrix/verify so
    the case list can be built and gated without a GPU."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / ("c_%s.bin" % function)
    r = subprocess.run([str(BIN / "shdump"), "-o", str(out), "-f", function,
                        "--no-fast-math", str(source)],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError("shdump failed for %s: %s" % (function, r.stderr[-600:]))
    _, pieces = agxparse.extract_agx(out.read_bytes())
    return pieces["_agc.main"]
