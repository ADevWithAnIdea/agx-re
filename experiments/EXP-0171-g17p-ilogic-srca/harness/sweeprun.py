#!/usr/bin/env python3
"""EXP-0171 sweep engine (G17P) -- the two carrier styles and the host oracle.

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified) so a whole field
sweep is ONE `agxrun_persist` process per (probe, style).

  NatCarrier   -- the probe kernel's OWN compiled archive with ONE byte spliced
                  IN PLACE. Operands are LOADED from device buffers and the
                  result is consumed by the COMPILER'S OWN `device_store`. The
                  observable is `out[]` in device memory. Host oracle available
                  for the integer kernels (KERNELS[...]["op"]).
  SynthCarrier -- the whole `_agc.main` of `kernels/carrier_dag.metal` replaced
                  by a program assembled from tools/agx-isa's own field rules,
                  with the instruction under test lifted BYTE-FOR-BYTE into it.
                  The observable is the REGISTER FILE (16 registers dumped).
                  `suffix=True` adds the framing probe (style FRAME).

Both read back a POISONED buffer (0xDEADBEEF), which is what distinguishes
"the op produced 0" from "the program never ran" (FIELD-SWEEP-PROTOCOL sect 7,
instrument 1). NAT additionally carries its integrity sentinels in a SEPARATE
device buffer (index 4) written through a different base slot from `out`, so no
register the descriptor under test can name is the sentinel's only home
(instrument 2; EXP-0138 lost six sweeps by seeding its sentinel in r11).

Records are appended to `<run_dir>/sweep.jsonl` and flushed+fsynced IMMEDIATELY.

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
import isa_helpers as H      # noqa: E402
import casematrix as CM      # noqa: E402


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

POISON = H.POISON
GRID = 8
TG = 8
NAT_OUT_BYTES = 64          # 16 words of buffer 0
NAT_SENT_BYTES = 8          # 2 words of buffer 4
SENT_A = 0x5A5A5A5A
SENT_B = 0x0BADF00D

# FIELD-SWEEP-PROTOCOL 7.2: an `...ErrorInnocentVictim`-class command-buffer
# failure is evidence about the MACHINE (a sibling GPU context's fault
# splashing into ours after a device reset), not about our encoding.
VICTIM_MARKERS = ("InnocentVictim", "innocent victim",
                  "Ignored (for causing prior", "IOAF code 4", "IOAF code 2",
                  "Discarded")


def is_victim(err):
    if not err:
        return False
    low = err.lower()
    return any(m.lower() in low for m in VICTIM_MARKERS)


# --------------------------------------------------------------------------
# INPUT VECTORS -- asymmetric on purpose. a[i] != b[i] for every i, so an
# operand SWAP is observable (that is how DEF-0154-5 was found), and no lane is
# a fixed point of and/or/xor/andn/nand simultaneously.
# --------------------------------------------------------------------------
UA = [0xAAAAAAAA, 0xCCCCCCCC, 0x0000FFFF, 0xF0F0F0F0,
      0x00000001, 0xFFFFFFFF, 0x12345678, 0x80000001]
UB = [0xCCCCCCCC, 0xAAAAAAAA, 0xFFFF0000, 0x0F0F0F0F,
      0x00000000, 0x7FFFFFFF, 0x9ABCDEF0, 0x00000003]
UC = [0x0000000F, 0x000000F0, 0x00000F00, 0x0000F000,
      0x000F0000, 0x00F00000, 0x0F000000, 0xF0000000]
FA = [1.0, 4.0, 0.25, 2.0, 100.0, 0.5, 16.0, 9.0]
FB = [3.0, 0.5, 2.0, 7.0, 1.5, 0.25, 5.0, 11.0]
FC = [0.5, 1.0, 2.0, 4.0, 8.0, 0.25, 0.125, 3.0]


def _pad64(b):
    return b + bytes([0]) * (64 - len(b)) if len(b) < 64 else b[:64]


def _uintbuf(vals):
    return _pad64(struct.pack("<8I", *vals))


def _floatbuf(vals):
    return _pad64(struct.pack("<8f", *[float(v) for v in vals]))


def _bf16(x):
    return struct.pack("<f", float(x))[2:4]


def _bfbuf(vals):
    # 32 bfloat lanes; lanes 8..31 repeat the pattern so a packed-lane form
    # still reads defined data.
    out = b"".join(_bf16(vals[i % 8]) for i in range(32))
    return out[:64]


def _half16(x):
    """IEEE-754 binary16, round-to-nearest-even, computed here so the harness
    has no numpy dependency on the device host."""
    f = struct.unpack("<I", struct.pack("<f", float(x)))[0]
    s = (f >> 16) & 0x8000
    e = ((f >> 23) & 0xFF) - 127 + 15
    m = f & 0x7FFFFF
    if e <= 0:
        return struct.pack("<H", s)
    if e >= 31:
        return struct.pack("<H", s | 0x7C00)
    h = s | (e << 10) | (m >> 13)
    if (m & 0x1FFF) > 0x1000:
        h += 1
    return struct.pack("<H", h & 0xFFFF)


def _halfbuf2(vals):
    out = b"".join(_half16(vals[i % 8]) for i in range(32))
    return out[:64]


INPUT_SETS = {
    "uint":   (_uintbuf(UA), _uintbuf(UB), _uintbuf(UC)),
    "float":  (_floatbuf(FA), _floatbuf(FB), _floatbuf(FC)),
    "bfloat": (_bfbuf(FA), _bfbuf(FB), _bfbuf(FC)),
    "half":   (_halfbuf2(FA), _halfbuf2(FB), _halfbuf2(FC)),
}


def _clz32(x):
    if x == 0:
        return 32
    n = 0
    while not (x & 0x80000000):
        x = (x << 1) & 0xFFFFFFFF
        n += 1
    return n


def _bfe(x, off, cnt, signed):
    v = (x >> off) & ((1 << cnt) - 1)
    if signed and (v >> (cnt - 1)) & 1:
        v -= (1 << cnt)
    return v & 0xFFFFFFFF


HOST_OPS = {
    "and":     lambda a, b, c: a & b,
    "or":      lambda a, b, c: a | b,
    "xor":     lambda a, b, c: a ^ b,
    "andn":    lambda a, b, c: a & (~b & 0xFFFFFFFF),
    "nand":    lambda a, b, c: (~(a & b)) & 0xFFFFFFFF,
    "and_sel": lambda a, b, c: 7 if (a & b) else 9,
    "popcnt":  lambda a, b, c: bin(a).count("1"),
    "clz":     lambda a, b, c: _clz32(a),
    "bfe_u":   lambda a, b, c: _bfe(a, 4, 6, False),
    "bfe_s":   lambda a, b, c: _bfe(a, 4, 6, True),
    "add":     lambda a, b, c: (a + b) & 0xFFFFFFFF,
}


def host_oracle_nat(probe):
    """The 18-word expected NAT observable, computed on the HOST with no GPU
    involvement, or None where the semantics are not exactly host-computable
    (estimates and float/half/bfloat rounding) -- those arms are declared
    BASELINE-COMPARATOR arms in PRE_REGISTRATION.md sect 5."""
    spec = CM.KERNELS[probe]
    op = spec["op"]
    if op is None or spec["t"] != "uint":
        return None
    f = HOST_OPS[op]
    words = [f(UA[i], UB[i], UC[i]) & 0xFFFFFFFF for i in range(8)]
    words += [POISON] * 8                       # never written at grid=8
    words += [SENT_A, SENT_B]
    return words


# --------------------------------------------------------------------------
# Carriers
# --------------------------------------------------------------------------
class _Base(object):
    def __init__(self, workdir, timeout):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.hangs = 0
        self.requests = 0

    def _tmp(self, name, data):
        p = self.workdir / ("%s_%d.bin" % (name, os.getpid()))
        p.write_bytes(data)
        return str(p)


class NatCarrier(_Base):
    """The probe kernel's own archive, ONE byte spliced in place."""
    style = "NAT"

    def __init__(self, source, probe, workdir, timeout=8.0):
        _Base.__init__(self, workdir, timeout)
        self.source = Path(source)
        self.probe = probe
        self.spec = CM.KERNELS[probe]
        self.arch_path = self.workdir / ("arch_%s.bin" % probe)
        r = subprocess.run([str(SHDUMP), "-o", str(self.arch_path), "-f", probe,
                            "--no-fast-math", str(self.source)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=300)
        if r.returncode != 0 or not self.arch_path.exists():
            raise RuntimeError("shdump failed for %s: %s"
                               % (probe, r.stderr.decode()[-800:]))
        self.basebuf = self.arch_path.read_bytes()
        loc = agxparse.locate_region(self.basebuf, "_agc.main")
        if loc is None:
            raise RuntimeError("cannot locate _agc.main in %s" % probe)
        self.region_off, self.region_len = loc
        _, pieces = agxparse.extract_agx(self.basebuf)
        self.main_bytes = pieces["_agc.main"]
        if self.basebuf[self.region_off:self.region_off + self.region_len] \
                != self.main_bytes:
            raise RuntimeError("region/_agc.main mismatch for %s" % probe)
        t = self.spec["t"]
        a, b, c = INPUT_SETS[t]
        self.ins_fixed = {1: self._tmp("in_a_%s" % t, a),
                          2: self._tmp("in_b_%s" % t, b),
                          3: self._tmp("in_c_%s" % t, c)}
        self.poison_out = self._tmp("poison_out",
                                    struct.pack("<16I", *([POISON] * 16)))
        self.poison_sent = self._tmp("poison_sent",
                                     struct.pack("<2I", *([POISON] * 2)))
        self.spliced_path = self.workdir / ("spliced_%s_%d.bin"
                                            % (probe, os.getpid()))
        self.runner = persistrun.PersistRunner(
            source=str(self.source), function=probe, fast_math=False,
            agxrun_persist=str(AGXRUN_PERSIST))
        self.device = self.runner.device
        self.oracle = host_oracle_nat(probe)

    def run_mut(self, instr_off, mut, timeout=None):
        """mut = [[byte_index_within_instruction, value], ...]"""
        spliced = bytearray(self.basebuf)
        for bi, v in mut:
            spliced[self.region_off + instr_off + bi] = v
        self.spliced_path.write_bytes(bytes(spliced))
        ins = dict(self.ins_fixed)
        ins[0] = self.poison_out
        ins[4] = self.poison_sent
        resp = self.runner.request(archive=str(self.spliced_path),
                                   grid=GRID, tg=TG, ins=ins,
                                   outs={0: NAT_OUT_BYTES, 4: NAT_SENT_BYTES},
                                   timeout=timeout or self.timeout)
        self.requests += 1
        if resp["status"] == "HANG":
            self.hangs += 1
        words = None
        if resp["status"] == "OK":
            o = resp["outs"].get(0, b"")
            s = resp["outs"].get(4, b"")
            if len(o) == NAT_OUT_BYTES and len(s) == NAT_SENT_BYTES:
                words = list(struct.unpack("<16I", o)) + list(struct.unpack("<2I", s))
        return resp, words

    def run_base(self, timeout=None):
        return self.run_mut(0, [], timeout=timeout)

    def restart(self):
        try:
            self.runner.close()
        except Exception:
            try:
                self.runner._kill()
            except Exception:
                pass
        self.runner = persistrun.PersistRunner(
            source=str(self.source), function=self.probe, fast_math=False,
            agxrun_persist=str(AGXRUN_PERSIST))

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass


class SynthCarrier(_Base):
    """`carrier_dag.metal` with the whole body replaced by our own program."""

    def __init__(self, source, workdir, suffix=False, timeout=8.0):
        _Base.__init__(self, workdir, timeout)
        self.style = "FRAME" if suffix else "SYNTH"
        self.suffix = suffix
        self.source = Path(source)
        self.arch_path = self.workdir / "arch_carrier_dag.bin"
        r = subprocess.run([str(SHDUMP), "-o", str(self.arch_path), "-f", "k",
                            "--no-fast-math", str(self.source)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=300)
        if r.returncode != 0 or not self.arch_path.exists():
            raise RuntimeError("shdump failed for carrier_dag: %s"
                               % r.stderr.decode()[-800:])
        self.basebuf = self.arch_path.read_bytes()
        loc = agxparse.locate_region(self.basebuf, "_agc.main")
        if loc is None:
            raise RuntimeError("cannot locate _agc.main in carrier_dag")
        self.region_off, self.region_len = loc
        self.poison_out = self._tmp(
            "poison_synth", struct.pack("<%dI" % H.OUT_WORDS,
                                        *([POISON] * H.OUT_WORDS)))
        self.spliced_path = self.workdir / ("spliced_synth_%s_%d.bin"
                                            % (self.style, os.getpid()))
        self.runner = persistrun.PersistRunner(
            source=str(self.source), function="k", fast_math=False,
            agxrun_persist=str(AGXRUN_PERSIST))
        self.device = self.runner.device
        self.oracle = None            # register-file observable: baseline only

    def run_block(self, kind, block, timeout=None):
        prog = H.synth_program(kind, block, self.region_len, suffix=self.suffix)
        spliced = bytearray(self.basebuf)
        spliced[self.region_off:self.region_off + self.region_len] = prog
        self.spliced_path.write_bytes(bytes(spliced))
        resp = self.runner.request(archive=str(self.spliced_path), grid=1, tg=1,
                                   ins={0: self.poison_out},
                                   outs={0: H.OUT_WORDS * 4},
                                   timeout=timeout or self.timeout)
        self.requests += 1
        if resp["status"] == "HANG":
            self.hangs += 1
        words = None
        if resp["status"] == "OK":
            raw = resp["outs"].get(0, b"")
            if len(raw) == H.OUT_WORDS * 4:
                w = list(struct.unpack("<%dI" % H.OUT_WORDS, raw))
                regs = [w[H.W_REG0 + i * H.STORE_STRIDE_WORDS]
                        for i in range(H.N_REGS)]
                words = regs + [w[H.W_PRE], w[H.W_POST]]
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
            source=str(self.source), function="k", fast_math=False,
            agxrun_persist=str(AGXRUN_PERSIST))

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Outcome classification
# --------------------------------------------------------------------------
def digest_hex(words):
    return "".join("%08x" % (w & 0xFFFFFFFF) for w in words) if words else None


def classify(status, obs, cmpv, n_expect, sent_idx):
    """FIELD-SWEEP-PROTOCOL sect 4 `outcome` for one case, plus the three
    instrument readings the outcome vocabulary cannot express.

    `cmpv` is the comparator: the HOST ORACLE where one exists, else the
    measured baseline (EXP-0166 amendment A3 -- the comparator is named in
    every record so the adjudication can be redone offline either way).
    `n_expect` is how many leading words the program is expected to write.
    `sent_idx` are the indices of the integrity sentinels."""
    info = {"poison_out": 0, "sentinel_bad": False, "invalid_run": False}
    if status == "HANG":
        return "hang", info
    if status != "OK":
        return "fault", info
    if obs is None or cmpv is None:
        return "undecodable", info
    info["poison_out"] = sum(1 for i in range(n_expect) if obs[i] == POISON)
    sent_poison = all(obs[i] == POISON for i in sent_idx) if sent_idx else False
    if sent_idx:
        info["sentinel_bad"] = any(obs[i] != cmpv[i] for i in sent_idx)
    # EXP-0160: a contaminated dispatch can report STATUS OK and write NOTHING.
    # Everything still poisoned is an invalid_run, never a silent_zero.
    if sent_poison and info["poison_out"] == n_expect:
        info["invalid_run"] = True
        return "undecodable", info
    if obs == cmpv:
        return "ok", info
    diff = [i for i in range(len(cmpv)) if obs[i] != cmpv[i]]
    if diff and all(obs[i] == 0 for i in diff):
        return "silent_zero", info
    return "wrong_value", info


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
