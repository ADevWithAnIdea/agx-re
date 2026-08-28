#!/usr/bin/env python3
"""EXP-0146 sweep engine.

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified) so a whole field sweep is ONE
`agxrun_persist` process: the carrier MSL is compiled once with `tools/shdump`, `_agc.main` is
located once with `tools/shdump/agxparse.py`, and each case splices its own mutated instruction
bytes into a copy of that archive and issues one request.

Records are appended to `<run_dir>/sweep.jsonl` and flushed+fsynced IMMEDIATELY
(SUBAGENT_BRIEF: "assume the host will crash mid-run"). Exactly the key set
`experiments/FIELD-SWEEP-PROTOCOL.md` §4 mandates is emitted.

Structure adapted from `experiments/EXP-0139-m4-emit-ialu/harness/sweeprun.py` (same project,
same rules, cited); the mutation model here is instruction-level (decode -> set one field ->
re-assemble through `tools/agx-isa/isadb.py`) rather than whole-program synthesis.

CLEAN-ROOM: pure process/file plumbing over our own tools; the only machine code ever inspected
or spliced is the compiled form of OUR OWN MSL (`kernels/*.metal`). No Apple binary is
disassembled or introspected.
"""
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
REPO = EXP.parents[1]
BIN = EXP / "work" / "bin"

sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only: decode_one / assemble / disassemble)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


agxparse = _load("agxparse", REPO / "tools" / "shdump" / "agxparse.py")
persistrun = _load("persistrun", REPO / "tools" / "agxtest" / "persistrun.py")

OUTCOMES = ("ok", "silent_zero", "wrong_value", "fault", "hang", "undecodable")


def set_field_bits(raw, start, width, value):
    """Return `raw` (an instruction's bytes) with the bit-field [start,start+width)
    of its little-endian integer view replaced by `value`. Same bit convention as
    `tools/agx-isa/isadb.py` (bit 8*k+b == byte +k bit b)."""
    n = len(raw)
    v = int.from_bytes(raw, "little")
    mask = ((1 << width) - 1) << start
    v = (v & ~mask) | ((value & ((1 << width) - 1)) << start)
    return v.to_bytes(n, "little")


class Carrier:
    """One compiled own-MSL carrier + one live persistent GPU runner."""

    def __init__(self, name, source, ins, outs, grid, tg, run_dir, workdir,
                 timeout=8.0, function="k"):
        self.name = name
        self.source = Path(source)
        self.function = function
        self.ins_spec = ins            # {buffer_index: bytes}
        self.outs_spec = outs          # {buffer_index: nbytes}
        self.grid, self.tg = grid, tg
        self.run_dir = Path(run_dir)
        self.workdir = Path(workdir)
        self.timeout = timeout
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.workdir.mkdir(parents=True, exist_ok=True)

        self.base_path = self.workdir / (name + "_base.bin")
        r = subprocess.run([str(BIN / "shdump"), "-o", str(self.base_path), "-f", function,
                            "--no-fast-math", str(self.source)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not self.base_path.exists():
            raise RuntimeError("shdump failed for %s: %s" % (name, r.stderr[-800:]))
        self.basebuf = self.base_path.read_bytes()
        loc = agxparse.locate_region(self.basebuf, "_agc.main")
        if loc is None:
            raise RuntimeError("could not locate _agc.main in %s" % name)
        self.region_off, self.region_len = loc
        _, pieces = agxparse.extract_agx(self.basebuf)
        self.main_bytes = pieces["_agc.main"]

        # input files on disk (written once)
        self.in_files = {}
        for idx, blob in self.ins_spec.items():
            p = self.workdir / ("%s_in%d.bin" % (name, idx))
            p.write_bytes(blob)
            self.in_files[idx] = str(p)

        self.runner = persistrun.PersistRunner(
            source=str(self.source), function=function, fast_math=False,
            agxrun_persist=str(BIN / "agxrun_persist"))
        self.device = self.runner.device
        self.spliced_path = self.workdir / (name + "_spliced.bin")
        self.hangs = 0

    # -- instruction access -------------------------------------------------
    def instr_at(self, off):
        rec, length = isadb.decode_one(self.main_bytes, off)
        return rec, self.main_bytes[off:off + length]

    def run_main(self, main_bytes):
        """Execute a full replacement `_agc.main`. Returns (status, raw-out-dict)."""
        if len(main_bytes) != len(self.main_bytes):
            raise ValueError("main length changed (%d != %d)" %
                             (len(main_bytes), len(self.main_bytes)))
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + len(main_bytes)] = main_bytes
        self.spliced_path.write_bytes(bytes(spliced))
        resp = self.runner.request(archive=str(self.spliced_path), grid=self.grid, tg=self.tg,
                                   ins=self.in_files, outs=self.outs_spec,
                                   timeout=self.timeout)
        if resp["status"] == "HANG":
            self.hangs += 1
        return resp

    def run_with_instr(self, off, instr_bytes):
        mb = bytearray(self.main_bytes)
        mb[off:off + len(instr_bytes)] = instr_bytes
        return self.run_main(bytes(mb))

    def close(self):
        self.runner.close()


class Recorder:
    """Append-only JSONL sink, flushed+fsynced per record."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a", buffering=1)
        self.n = 0

    def record(self, rec):
        rec.setdefault("note", "")
        self.n += 1
        rec["seq"] = self.n
        rec["t"] = round(time.time(), 3)
        self.fh.write(json.dumps(rec, sort_keys=True) + "\n")
        self.fh.flush()
        os.fsync(self.fh.fileno())

    def close(self):
        self.fh.close()


def words32(blob):
    return [struct.unpack_from("<I", blob, i)[0] for i in range(0, len(blob) - 3, 4)]


def words64(blob):
    return [struct.unpack_from("<Q", blob, i)[0] for i in range(0, len(blob) - 7, 8)]


def floats32(blob):
    return [struct.unpack_from("<f", blob, i)[0] for i in range(0, len(blob) - 3, 4)]


def classify(status, observed, oracle, tol=None):
    """FIELD-SWEEP-PROTOCOL §4 outcome for one case."""
    if status == "HANG":
        return "hang", False
    if status != "OK":
        return "fault", False
    if observed is None:
        return "undecodable", False
    if tol is None:
        match = (observed == oracle)
    else:
        try:
            match = all(abs(a - b) <= tol * max(1.0, abs(b)) for a, b in zip(observed, oracle)) \
                    and len(observed) == len(oracle)
        except TypeError:
            match = False
    if match:
        return "ok", True
    if all((v == 0 or v == 0.0) for v in observed):
        return "silent_zero", False
    return "wrong_value", False
