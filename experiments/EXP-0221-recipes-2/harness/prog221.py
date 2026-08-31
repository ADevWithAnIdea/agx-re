#!/usr/bin/env python3
"""EXP-0221 program builder + HOST ORACLE (fork of our own EXP-0220 prog220.py).

A `Prog` accumulates generated instructions AND, in lockstep, a host model of
(a) the architectural register file and (b) every BYTE the program will write to
the three bound buffers.  The oracle is therefore computed BEFORE the GPU is
touched and is completely independent of it (Gate C).

THE SKELETON every case shares:

    mov_imm      r15, 0                   index register, held at 0
    mov_imm      r12, 85                  integrity sentinel value
    device_store <fixed known-good config> sentinel -> out byte 16*SENT_OFF
    device_load  r16..r23 <- imem[..]      high-register seeds (stray-write detectors)
    ... case-specific seeds ...
    ... the instruction(s) under test ...
    device_store r0..r23 -> out            COMPLETE ARCHITECTURAL STATE DUMP (Gate B:
                                           complete relevant state, not only the
                                           presumed destination)
    stop
    <mov_imm padding to the carrier length, never reached>

Poisoned read-back (FIELD-SWEEP-PROTOCOL section 7): all three buffers are
re-uploaded before every dispatch and the out buffer is filled with 0xDEADBEEF,
so "wrote the right value" / "wrote a wrong value" / "never ran at all" are
three distinguishable outcomes.  mem and imem are read back too, so a store that
lands in the wrong buffer is caught rather than merely missed.

CLEAN ROOM: builds bytes with our own `synth220`/`isadb` over our own db.json.
No Apple binary is inspected.
"""

import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import synth221 as S  # noqa: E402

# ---------------------------------------------------------------------------
# fixed layout
# ---------------------------------------------------------------------------
OUT_BYTES = 32768                 # idx_off 0..2047 * 16 (+16) all land inside
MEM_BYTES = 4096                  # 1024 floats
IMEM_BYTES = 4096                 # 1024 ints

R_IDX = 15                        # index GPR, held at 0 for every case
R_SENT = 12                       # sentinel value register
SENT_OFF = 800                    # sentinel store idx_off -> out byte 12800
SENT_IMM = 85                     # 0x55 -- avoids the imm7 == 12 tokenization hole
DUMP_REGS = list(range(24))       # r0..r23 dumped every case
DUMP_BASE = 900                   # dump idx_off base -> out bytes 14400..14768
# mov_imm immediates that do NOT tokenize as a 2-byte instruction under the
# current length rule.  EXP-0140 found imm7 == 12; EXP-0220's own build-time
# framing check widens it to every imm7 == 6 (mod 16) as well, because byte+1's
# low nibble 6 makes the following pair look like a 4-byte low-nibble-0xc group.
# Recorded as a finding; here it is simply avoided.
UNSAFE_IMM7 = (6, 12, 22, 38, 54, 70, 86, 102, 118)
LOW_CODEWORD = [v for v in range(40, 80) if v not in UNSAFE_IMM7][:16]
HI_SEED = {16: 100, 17: 101, 18: 102, 19: 103,
           20: 104, 21: 105, 22: 106, 23: 107}   # rR <- imem[j] = j

# idx_off values a case may NOT use for a store under test: they would land on
# the sentinel or the state dump and hide the thing being measured.
RESERVED_OFFS = set([SENT_OFF]) | set(DUMP_BASE + R for R in DUMP_REGS)

# st_format -> (element bytes, number of consecutive source registers).
# db.json `device_store.st_format` enum + EXP-0141.  The MULTI-ELEMENT rows are
# a stated HYPOTHESIS of this experiment (that element n comes from register
# extmode/2 + n); they are pre-registered with a refuter, not assumed.
ST_FORMAT_SHAPE = {17: (4, 1), 1: (2, 1), 33: (1, 1),
                   25: (4, 2), 29: (4, 3), 23: (4, 4)}


HALF_PAIRS = [(1.5, 8.0), (2.5, -3.0), (0.5, 16.0), (-4.5, 2.0),
              (3.0, -1.0), (6.0, 0.5), (-0.5, 4.0), (12.0, -8.0),
              (0.25, 1.0), (-2.0, 3.5), (5.0, -6.0), (7.5, 2.5),
              (-1.25, 9.0), (10.0, -0.25), (0.75, 5.5), (-3.5, 11.0)]


def mem_words():
    """Buffer 1.  mem[j] = (j+1)/4 for j < 512 -- every value a multiple of 1/4
    with at most 10 significant mantissa bits, so sums AND products of any two
    are EXACTLY representable in binary32 and the host oracle needs no rounding
    model.  512..1023 carry IEEE boundary values for the asymmetric arm."""
    w = [S.f32((j + 1) * 0.25) for j in range(512)]
    special = [0.0, -0.0, 1.0, -1.0, 2.0, -2.0, 0.5, -0.5,
               float("inf"), float("-inf"), float("nan"),
               1.1754943508222875e-38,       # smallest normal
               1.401298464324817e-45,        # smallest denormal
               3.4028234663852886e+38,       # FLT_MAX
               -3.4028234663852886e+38, 16777216.0]
    for j in range(512, 1024):
        w.append(S.f32(special[(j - 512) % len(special)]))
    # 528..543: two binary16 codewords PACKED into one 32-bit word, low half
    # first.  The b16 operand arm needs the LOW HALF to be non-zero and distinct:
    # every mem[j] = (j+1)/4 has an all-zero low half, so a b16 arm built on
    # those reads 0.0 for both operands and is EXACT BY CONSTRUCTION -- the
    # section 5a detection-power pitfall.  These sixteen words fix that.
    for n, (lo, hi) in enumerate(HALF_PAIRS):
        w[528 + n] = struct.unpack("<f", struct.pack("<e", lo)
                                   + struct.pack("<e", hi))[0]
    return w


# EXP-0221: the CODEWORD BLOCK.  imem[900..1023] carries 124 distinct 32-bit
# codewords with no small-integer, no poison and no float-codeword collisions, so
# a threadgroup round trip can be recognised by the VALUE that comes back.  A
# threadgroup tile is UNINITIALISED at dispatch: without a value that cannot
# plausibly be there already, "the load returned something" and "the load
# returned OUR store" are indistinguishable -- section 5a's detection-power
# pitfall in its memory form.
CODEWORD_BASE = 900
CODEWORD_SEED = 0x5A17C0DE


def codeword(n):
    return (CODEWORD_SEED ^ (n * 0x01010101)) & 0xFFFFFFFF


def imem_words():
    """Buffer 2.  imem[j] = j for j < 900, so a device_load of imem[j] seeds a
    register with the integer j (index registers, high-register seeds); and
    imem[900 + n] = codeword(n), the distinctive 32-bit values arm T needs."""
    w = list(range(CODEWORD_BASE))
    w += [codeword(n) for n in range(1024 - CODEWORD_BASE)]
    return w


MEM = mem_words()
IMEM = imem_words()


def mem_bytes():
    return b"".join(struct.pack("<f", v) for v in MEM)


def imem_bytes():
    return b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in IMEM)


def poison_bytes():
    return struct.pack("<I", S.POISON_U32) * (OUT_BYTES // 4)


def fbits(x):
    return struct.unpack("<I", struct.pack("<f", S.f32(x)))[0]


# ---------------------------------------------------------------------------
class Prog(object):
    """One generated program plus its host oracle."""

    def __init__(self, slots, salt, offnatural=True):
        self.E = S.Emitter()
        self.slots = slots                      # {"out":n, "mem":n, "imem":n}
        self.salt = salt
        self.offnatural = offnatural
        self.reg = {}                           # R -> u32 bits, or None (unknown)
        self.writes = []                        # (base, byte_off, payload|None, tag)
        self.hazards = []
        self.notes = []
        self.body_start = 0                     # first byte after the prologue
        self.body_end = None                    # first byte of the state dump
        # IN-FLIGHT LOAD TRACKER (EXP-0220 diagnostics D11/D12 (re-measured here), G17P).
        # A device_load's result is NOT yet architecturally visible to the very
        # next instruction: a device_store whose index_reg is the load's
        # destination addresses with the STALE register value, and one
        # intervening instruction is enough to make the loaded value visible.
        # (falu2 has an explicit control for the same hazard -- mod_hi bits 2+3.)
        self._pending = None                    # (R, value_before_the_load)
        self.tripwire_off = None                # arm S post-stop tripwire

    # -- host register model -------------------------------------------------
    def set_reg(self, R, bits):
        self.reg[R] = None if bits is None else (bits & 0xFFFFFFFF)

    def rbits(self, R):
        return self.reg.get(R, None)

    # -- generated instructions ---------------------------------------------
    def movi(self, R, v):
        S.mov_imm(self.E, R, v, salt=self.salt)
        self._pending = None
        self.set_reg(R, v)

    def load_f(self, R, j, salt=None, ld_format=None, elem_code=3, base="mem",
               index_reg=None, predict=True, slot=None, **fields):
        """One generated device_load plus the host prediction of its effect.

        EXP-0221: every descriptor field is passed straight through to
        `synth221.device_load`, and `predict=False` marks a case whose result the
        host deliberately does not claim (a swept value outside the documented
        accepted set).  The register then goes to None, which the oracle reports
        as `unpredicted` -- never silently scored ok."""
        ir = R_IDX if index_reg is None else index_reg
        sl = self.slots[base] if slot is None else slot
        S.device_load(self.E, ir, j, elem_code, sl, R,
                      salt=salt or ("%s.lf%d" % (self.salt, j)),
                      offnatural=self.offnatural, ld_format=ld_format, **fields)
        idx = self.rbits(ir)
        prev = self.rbits(R)
        if (not predict) or idx is None or ld_format not in (None, 17, 49) \
                or fields.get("extmode") is not None:
            self.set_reg(R, None)
            self._pending = (R, prev)
            return
        off = S.load_byte_offset(idx, j, elem_code)
        src = mem_bytes() if base == "mem" else imem_bytes()
        if off + 4 <= len(src):
            self.set_reg(R, struct.unpack("<I", src[off:off + 4])[0])
        else:
            self.set_reg(R, None)
        self._pending = (R, prev)

    def load_i(self, R, j, **kw):
        return self.load_f(R, j, base="imem", **kw)

    # -- threadgroup address space (EXP-0221 arm T) --------------------------
    def tg_store(self, data_reg, idx_off, cfg, index_reg=None, tag="tg_store"):
        """A GENERATED store whose `space` selects the THREADGROUP tile.

        Nothing is predicted about the device buffers: a correct threadgroup
        store must leave all three of them untouched, so the oracle records NO
        write and any change shows up as a stray.  Whether the datum arrived is
        answered by `tg_load`, not by this call."""
        ir = R_IDX if index_reg is None else index_reg
        S.device_store(self.E, ir, idx_off, cfg.get("base_slot", 0), data_reg,
                       salt="%s.tgs%d" % (self.salt, idx_off), offnatural=False,
                       space=cfg["space"], access_desc=cfg["access_desc"],
                       elem_size=cfg["elem_size"], st_format=cfg["st_format"],
                       addr_mode=cfg.get("addr_mode"),
                       st_format_ext=cfg.get("st_format_ext", 0),
                       st_desc_hi=cfg.get("st_desc_hi", 0),
                       reserved7=cfg.get("reserved7", 0),
                       reserved13=cfg.get("reserved13", 0))
        self._pending = None
        self.set_reg(ir, 0)
        self.notes.append("%s cfg=%r" % (tag, cfg))

    def tg_load(self, R, idx_off, cfg, index_reg=None, tag="tg_load"):
        """A GENERATED load whose `space` selects the THREADGROUP tile.

        The destination register is UNPREDICTED by construction -- what it
        contains is the measurement."""
        ir = R_IDX if index_reg is None else index_reg
        S.device_load(self.E, ir, idx_off, 3, cfg.get("base_slot", 0), R,
                      salt="%s.tgl%d.%d" % (self.salt, R, idx_off), offnatural=False,
                      ld_format=cfg["ld_format"], space=cfg["space"],
                      access_desc=cfg["access_desc"], elem_size=cfg["elem_size"],
                      addr_mode=cfg.get("addr_mode"),
                      reserved7=cfg.get("reserved7", 0),
                      reserved13=cfg.get("reserved13", 0),
                      ldform_hi11=cfg.get("ldform_hi11", 0))
        prev = self.rbits(R)
        self.set_reg(R, None)
        self._pending = (R, prev)
        self.notes.append("%s r%d cfg=%r" % (tag, R, cfg))

    # -- stores --------------------------------------------------------------
    def _payload(self, data_reg, st_format):
        """Predicted bytes for one store, as a list whose entries may be None.

        A None entry means "this byte is TOUCHED but the host cannot predict its
        value" -- it is reported as `unpredicted`, never scored ok and never
        counted as a stray write.  Marking only the first byte (an earlier bug)
        manufactured three phantom strays for every unpredictable register."""
        shape = ST_FORMAT_SHAPE.get(st_format)
        if shape is None:
            return None
        width, nregs = shape
        out = []
        for n in range(nregs):
            b = self.rbits(data_reg + n)
            if b is None:
                out += [None] * (width if nregs == 1 else 4)
            elif nregs == 1:
                out += list(struct.pack("<I", b)[:width])
            else:
                out += list(struct.pack("<I", b))
        return out

    def store(self, data_reg, idx_off, index_reg=R_IDX, base="out", tag="",
              st_format=S.ST_FORMAT_SCALAR32, predict=True, extmode=None,
              slot=None, **kw):
        """One generated device_store plus its predicted memory effect."""
        _am = kw.get("addr_mode")
        _fwd = kw.get("_load_forwarded", False)
        kw.pop("_load_forwarded", None)
        S.device_store(self.E, index_reg, idx_off,
                       self.slots[base] if slot is None else slot, data_reg,
                       salt=kw.pop("salt", None) or ("%s.st%d" % (self.salt, idx_off)),
                       offnatural=kw.pop("offnatural", False),
                       st_format=st_format, extmode=extmode, **kw)
        eff_reg = data_reg if extmode is None else ((extmode >> 1) & 0x3F)
        idxval = self.rbits(index_reg)
        pend = self._pending
        # IN-FLIGHT LOAD RESULT CONSUMED AS THE STORE'S DATA (EXP-0220 p07,
        # arm B2).  `addr_mode` bit1 is the ACCEPT/FORWARD control: with it SET
        # the store writes the loaded value and the register keeps it; with it
        # CLEAR the store writes the STALE register value AND THE LOAD IS
        # DROPPED -- the destination register never receives it.  This is the
        # store-side twin of falu2's `mod_hi` bits 2/3.
        am = _am if _am is not None else (S.DS_ADDRMODE_LOADFWD if _fwd
                                          else S.DS_ADDRMODE_ALU)
        if pend and pend[0] == eff_reg and not (am & 0x02):
            self.set_reg(eff_reg, pend[1])
        if pend and pend[0] == index_reg:
            idxval = pend[1]                    # STALE index (D12)
        self._pending = None
        if idxval is None:
            self.hazards.append("store with unmodelled index register r%d" % index_reg)
            self.writes.append((base, None, None, tag or "unmodelled"))
            return
        off = S.store_byte_offset(idxval, idx_off)
        payload = self._payload(eff_reg, st_format) if predict else None
        self.writes.append((base, off, payload, tag or ("r%d" % eff_reg)))
        # D10/D11: the store RELEASES its index register -- it reads 0 after,
        # and a SECOND store reusing that register addresses with index 0.
        self.set_reg(index_reg, 0)

    def store_predicted(self, data_reg, idx_off, payload, **kw):
        """A store whose predicted payload is supplied explicitly (used where the
        documented rule says the store does NOT deliver the register, e.g. an
        addr_mode with the data-source selector clear over a forwarded load)."""
        tag = kw.pop("tag", "explicit")
        base = kw.pop("base", "out")
        index_reg = kw.pop("index_reg", R_IDX)
        S.device_store(self.E, index_reg, idx_off, self.slots[base], data_reg,
                       salt=kw.pop("salt", None) or ("%s.sp%d" % (self.salt, idx_off)),
                       offnatural=kw.pop("offnatural", False), **kw)
        idxval = self.rbits(index_reg)
        if self._pending and self._pending[0] == index_reg:
            idxval = self._pending[1]
        self._pending = None
        off = None if idxval is None else S.store_byte_offset(idxval, idx_off)
        if isinstance(payload, (bytes, bytearray)):
            payload = list(payload)
        self.writes.append((base, off, payload, tag))
        self.set_reg(index_reg, 0)

    # -- falu2 ---------------------------------------------------------------
    def falu2(self, dst, op, srcA, **kw):
        """One generated falu2 plus the host prediction of its FULL effect.

        The effect is not only the destination.  `opflags` bit0 releases src0 and
        bit1 releases src1 (EXP-0086/0089/0099/0119), and a released register is
        GENUINELY GONE -- a later read returns zero, deterministically and
        without a fault.  The oracle models that, so a program whose sources are
        released predicts ZERO for them in the state dump rather than their
        seeded codeword.  EXP-0220 arm A5 swept all 32 `opflags` values against
        exactly this model, so it is a tested prediction and not an assumption.
        (It also CORRECTS EXP-0090 finding_1's reading of bit1 as `both real`:
        the pilot capture work/pilot/p01 shows bit1 set at a GPR srcB leaves that
        register reading 0 while the result is still correct.)"""
        predict = kw.pop("predict", True)
        pred = self._falu2_predict(op, srcA, kw) if predict else None
        opflags = kw.get("opflags")
        if opflags is None:
            opflags = ((1 if kw.get("release_srcA") else 0)
                       | ((1 if kw.get("release_srcB") else 0) << 1)
                       | ((1 if kw.get("publish", True) else 0) << 2))
        S.falu2(self.E, dst, op, srcA, salt=kw.pop("salt", None) or self.salt,
                offnatural=kw.pop("offnatural", self.offnatural), **kw)
        self._pending = None
        if opflags & 0b001:
            self.set_reg(srcA, 0)
        if (opflags & 0b010) and kw.get("inline_k") is None \
                and kw.get("srcB_class", S.SRCB_CLASS_GPR) == S.SRCB_CLASS_GPR \
                and kw.get("srcB_reg") is not None:
            self.set_reg(kw["srcB_reg"], 0)
        self.set_reg(dst, pred)
        return pred

    def _falu2_predict(self, op, srcA, kw):
        a_bits = self.rbits(srcA)
        if a_bits is None:
            return None
        if kw.get("srcA_size", 1) == 0:
            a = struct.unpack("<e", struct.pack("<I", a_bits)[:2])[0]
        else:
            a = S.bits_f32(a_bits)
        cls = kw.get("srcB_class", S.SRCB_CLASS_GPR)
        neg = kw.get("srcB_neg", 0)
        of = kw.get("opflags") or 0
        if kw.get("inline_k") is not None:
            b = S.inline_srcB_value(kw["inline_k"], neg, of)
        elif cls == S.SRCB_CLASS_GPR:
            bb = self.rbits(kw.get("srcB_reg"))
            if bb is None:
                return None
            if kw.get("srcB_size", 1) == 0:
                b = struct.unpack("<e", struct.pack("<I", bb)[:2])[0]
            else:
                b = S.bits_f32(bb)
            b = -b if neg else b
        elif cls in (2, 3):
            # EXP-0220 p05: for the constant-zero classes only `srcB_neg`
            # signs the operand -- opflags bit1 does NOT (unlike the inline
            # immediate class).  Visible only through fmul, where the sign of
            # the zero survives into the product.
            b = -0.0 if neg else 0.0
        else:
            return None                       # uniform file: deliberately not modelled
        o = kw.get("opsel")
        name = op if o is None else {4: "fadd", 5: "fmul"}.get(o, op)
        try:
            if name == "fadd":
                r = S.f32(S.f32(a) + S.f32(b))
            elif name == "fmul":
                r = S.f32(S.f32(a) * S.f32(b))
            else:
                return None
        except (OverflowError, ValueError):
            return None
        return struct.unpack("<I", struct.pack("<f", r))[0]

    # -- the fixed scaffolding ----------------------------------------------
    def prologue(self, seed_high=True):
        """Seed EVERY dumped register with a UNIQUE codeword before anything
        else runs (section 5 Phase 3: "seed every source register/lane with a
        unique codeword so register, lane, width, swizzle, sign, absolute and
        immediate interpretations cannot alias").  This also removes the need to
        ASSUME what an unwritten register reads: r0..r15 are written here, and
        r16..r23 are loaded from imem, so the host oracle predicts all 24
        without relying on EXP-0087's unwritten-reads-zero rule."""
        for R in range(16):
            if R == R_IDX:
                self.movi(R, 0)
            elif R == R_SENT:
                self.movi(R, SENT_IMM)
            else:
                self.movi(R, LOW_CODEWORD[R])
        self.store(R_SENT, SENT_OFF, tag="sentinel")
        if seed_high:
            for R, j in sorted(HI_SEED.items()):
                self.load_i(R, j, salt="hiseed%d" % R)
        self.body_start = self.E.off

    def dump(self):
        self.body_end = self.E.off
        for R in DUMP_REGS:
            self.store(R, DUMP_BASE + R, tag="dump_r%d" % R)

    def finish(self, carrier_len, stop_reserved=None, tripwire_off=None,
               tripwire_before_stop=False):
        """Terminate the program.

        EXP-0221 arm S needs a POST-STOP TRIPWIRE: `stop` is only observable if
        something after it would be observable had the program NOT halted.  With
        `tripwire_off` set, a `device_store` of the sentinel register is emitted
        AFTER the `stop` (or, for the Gate B detection-power control,
        immediately BEFORE it).  Nothing is predicted for the post-stop store --
        the scorer reads that out word directly and records
        `tripwire_written`."""
        if tripwire_off is not None and tripwire_before_stop:
            self.store(R_SENT, tripwire_off, tag="tripwire_prestop")
        S.stop(self.E, offnatural=self.offnatural, salt=self.salt,
               reserved=stop_reserved)
        if tripwire_off is not None and not tripwire_before_stop:
            self.store_predicted(R_SENT, tripwire_off, [], tag="tripwire_poststop")
        self.tripwire_off = tripwire_off
        return S.build_program(self.E, carrier_len)

    # -- the oracle ----------------------------------------------------------
    def oracle(self):
        """Simulate every predicted write, in program order, over a poisoned
        model of each buffer.  Returns {base: {byte_index: value|None}} for the
        bytes this program is predicted to TOUCH; every other byte must still
        read its pre-dispatch content.  `None` marks a touched byte whose value
        the host cannot predict -- reported, never silently scored `ok`."""
        model = {"out": {}, "mem": {}, "imem": {}}
        for (base, off, payload, tag) in self.writes:
            if off is None:
                continue
            if payload is None:
                model[base][off] = None       # extent unknown: mark the first byte
                continue
            # payload == [] means "predicted: NO memory effect" -- nothing is
            # recorded, so any change at all shows up as a stray write.
            for k, byte in enumerate(payload):
                model[base][off + k] = byte
        return model

    def sentinel_byte(self):
        return S.store_byte_offset(0, SENT_OFF)

    def dump_byte(self, R):
        return S.store_byte_offset(0, DUMP_BASE + R)
