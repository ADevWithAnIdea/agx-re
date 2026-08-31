#!/usr/bin/env python3
"""EXP-0220 provenance-tracking instruction emitter (G17P / A18 Pro).

WHAT THIS FILE IS FOR.  `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` Gate D:

    "To call an instruction compiler-usable, construct every required byte from
     documented rules, run the exact generated program, and compare complete
     state with a host prediction.  The evidence record must identify every
     copied region and prove that no required instruction field came from a
     compiler-emitted donor."

So EVERY field value emitted here carries a machine-checked provenance tag, and
the experiment's gate is "zero fields tagged COPIED or CARRIER".

DIRECT ANCESTOR: our own `experiments/EXP-0167-g17p-synthesis-reconfirm/synth.py`
(committed, read-only; NOT modified).  EXP-0220 is a new experiment number with a
fresh pre-registration, per CODEX.  What is NEW here relative to EXP-0167:

  * `base_slot` is no longer `CARRIER`.  EXP-0167 re-derived it by
    DISASSEMBLING ITS OWN COMPILED CARRIER -- honest, but it reads a required
    instruction field off a compiler-emitted instruction, which is exactly what
    Gate D asks us to eliminate.  EXP-0220 determines the slot -> bound-buffer
    mapping by HARDWARE PROBE (arm S0: sweep base_slot in a generated store and
    see which buffer the write lands in), so the value is `RULE` with a
    hardware citation and the copied-region ledger for it is EMPTY.
  * `falu2.mod_hi` is no longer `PILOT`.  EXP-0167's own disclosed pilot
    measured its accepted set on G17P and froze it in that experiment's
    committed `frozen_pilot.py`; a later implementer reads it out of that
    committed result, so here it is `RULE` with that citation.
  * The programs carry a COMPLETE ARCHITECTURAL STATE DUMP (r0..r23 stored to
    distinct out words) rather than only the presumed destination, per Gate B.

PROVENANCE CLASSES (exactly four; every emitted field gets one):

  RULE    computed from a documented hardware rule or formula established by a
          committed experiment in this repository.  A rule-mandated constant is
          RULE, not COPIED: the emitter derives it.  Citation mandatory.
  FREE    the field has a documented accepted set / don't-care range; the value
          is picked by this module's own deterministic chooser, which prefers a
          value the compiler would NOT emit.  Citation mandatory.
  CARRIER a binding parameter re-derived from our own compiled carrier kernel.
          EXP-0220 emits ZERO of these -- the class is retained only so the
          ledger can PROVE it is empty.
  COPIED  lifted verbatim from a compiled shader.  EXP-0220 emits ZERO of these.

CLEAN ROOM: nothing here inspects an Apple binary.  Every cited rule was
established by this repository's own hardware sweeps over our own compiled or
spliced shaders.
"""

import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
# READ-ONLY use of a PINNED, hash-recorded snapshot of tools/agx-isa: the live
# tools/agx-isa/db.json is edited concurrently by the orchestrator, and a
# two-run byte-identity gate must not depend on a file that can move between
# run01 and run02.
PINNED = EXP / "work" / "frozen"
sys.path.insert(0, str(PINNED))
import isadb  # noqa: E402
assert Path(isadb._DB_JSON).resolve() == (PINNED / "db.json").resolve(), \
    "synth220 must load the PINNED db.json, got %s" % isadb._DB_JSON

RULE, FREE, CARRIER, COPIED = "RULE", "FREE", "CARRIER", "COPIED"

POISON_U32 = 0xDEADBEEF


# ---------------------------------------------------------------------------
# provenance ledger
# ---------------------------------------------------------------------------
class FV(object):
    __slots__ = ("value", "prov", "cite", "note")

    def __init__(self, value, prov, cite, note=""):
        self.value = int(value)
        self.prov = prov
        self.cite = cite
        self.note = note

    def __repr__(self):
        return "FV(%d,%s)" % (self.value, self.prov)


class Ledger(object):
    """Every emit() appends here.  `counts()['COPIED'] == 0` and
    `counts()['CARRIER'] == 0` is the Gate D donor test for a program."""

    def __init__(self):
        self.rows = []

    def add(self, mnemonic, name, fv, offset):
        self.rows.append({"instr": mnemonic, "field": name, "value": fv.value,
                          "prov": fv.prov, "cite": fv.cite, "note": fv.note,
                          "offset": offset})

    def counts(self):
        c = {RULE: 0, FREE: 0, CARRIER: 0, COPIED: 0}
        for r in self.rows:
            c[r["prov"]] += 1
        return c

    def nonsynthesised(self):
        return sorted({"%s.%s" % (r["instr"], r["field"]) for r in self.rows
                       if r["prov"] in (COPIED, CARRIER)})

    def offnatural(self):
        return sorted({"%s.%s=%d" % (r["instr"], r["field"], r["value"])
                       for r in self.rows if "offnat" in r["note"]})


class Emitter(object):
    """Accumulates instructions and keeps the byte offset of each, so the Gate A
    ledger can name the offset of every field it claims."""

    def __init__(self):
        self.led = Ledger()
        self.parts = []          # list of (offset, mnemonic, requested_fields, bytes)
        self.off = 0

    def emit(self, mnemonic, fields):
        vals = {}
        for k, fv in fields.items():
            if not isinstance(fv, FV):
                raise TypeError("%s.%s must be an FV, got %r" % (mnemonic, k, fv))
            self.led.add(mnemonic, k, fv, self.off)
            vals[k] = fv.value
        b = isadb.assemble(mnemonic, vals)
        self.parts.append((self.off, mnemonic, dict(vals), b))
        self.off += len(b)
        return b

    def body(self):
        return b"".join(p[3] for p in self.parts)


# ---------------------------------------------------------------------------
# deterministic OFF-NATURAL chooser
# ---------------------------------------------------------------------------
def choose(key, accepted, natural, salt):
    """Deterministically pick a value from `accepted`, PREFERRING one that is
    NOT `natural` (i.e. not the value a compiler emits).  Pure function of
    (key, salt): identical on every machine and every re-run, so run01 and
    run02 produce byte-identical programs for the same case."""
    acc = list(accepted)
    if not acc:
        raise ValueError("empty accepted set for " + key)
    alt = [v for v in acc if v != natural]
    pool = alt if alt else acc
    h = zlib.crc32((key + "|" + str(salt)).encode()) & 0xFFFFFFFF
    return pool[h % len(pool)]


# ---------------------------------------------------------------------------
# float helpers
# ---------------------------------------------------------------------------
def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def bits_f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# HARDWARE RULE TABLES -- every entry cites the committed experiment that
# established it.  Nothing below is read off a compiled shader.
# ---------------------------------------------------------------------------
# device_load / device_store accepted sets (EXP-0141 field_verdicts.json, exact
# mask rules; re-confirmed on G17P by EXP-0167's own committed pilot tables in
# experiments/EXP-0167-g17p-synthesis-reconfirm/frozen_pilot.py).
DL_SPACE_OK = [v for v in range(256) if v & 0x03 == 0x00]
DL_ADDRMODE_OK = [0, 0xA5, 0xFF, 0x44]
DL_ACCESSDESC_OK = [0, 0x5A, 0xFF, 0x20]
DL_RESERVED_OK = [0, 0x5A, 0xFF]
DL_DSTEXT9_OK = [v for v in range(128) if v & 0x01 == 0x01]
DL_LDFORMHI_OK = [v for v in range(64) if v & 0x07 == 0x00]
DL_LDFORMAT_ONE_REGISTER = [17, 49]       # EXP-0167 frozen_pilot (G17P): the ONLY
                                          # codes that write the target and NOTHING else
DL_ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}          # EXP-0082

DS_SPACE_OK = [v for v in range(256) if v & 0x02 == 0x00]
DS_ADDRMODE_ALU = 0x54                    # EXP-0141: bit1 clear = ALU-computed data
DS_ADDRMODE_LOADFWD = 0x56                # EXP-0141: bit1 set   = live load-result
DS_ACCESSDESC_OK = [0, 0x5A, 0xFF, 0x21]
DS_RESERVED_OK = [0, 0x5A, 0xFF]
DS_STFMTEXT_OK = [v for v in range(128) if v & 0x60 == 0x00]
DS_DESCHI_OK = [v for v in range(64) if v & 0x11 == 0x00]
DS_ELEM_OK = [17, 23, 39, 55]             # EXP-0167 frozen_pilot G17P `ok` set
# st_format codes.  db.json enum + EXP-0141: 17 = 32-bit scalar.
ST_FORMAT_SCALAR32 = 17

# falu2 mod_hi, by OPERAND PROVENANCE (EXP-0167 frozen_pilot.py, measured on
# G17P: FALU2_MODHI_OK_ALU = the eight even values, FALU2_MODHI_OK_LOAD = [12]).
FALU2_MODHI_OK_ALU = [0, 2, 4, 6, 8, 10, 12, 14]
FALU2_MODHI_OK_LOAD = [12]
# operand source classes (EXP-0138 model, carried by db.json as named fields)
SRCA_CLASS_GPR = 0
SRCB_CLASS_GPR = 0
SRCB_CLASS_NONGPR = 1                     # 0..63 uniform file, 64..127 inline minifloat
SRCB_CLASS_ZERO = 2                       # reads 0.0 (bit2 dominates bit1)
FALU2_OPSEL = {"fadd": 4, "fmul": 5, "fma": 6, "fmul_interp": 7}
# THE SIGN OF AN INLINE IMMEDIATE (EXP-0220 pre-freeze diagnostic D7, G17P).
#
# EXP-0167's committed frozen_pilot records `INLINE_NEG0_SIGN = -1` -- with
# srcB_neg == 0 the inline immediate reads NEGATIVE.  EXP-0220's diagnostic D1,
# D3 and D6 measured the opposite sign at the same `srcB_neg`, and D7 resolves
# it: EXP-0167's generator ALWAYS set `opflags` bit1, and
#
#     effective sign = (-1) ** (srcB_neg XOR opflags_bit1)
#
# D7, one program, four instructions differing only in those two bits, srcA a
# loaded 10.25 and |imm| = 4.0:
#     opflags bit1 = 0, srcB_neg = 0  ->  14.25   (+4.0)
#     opflags bit1 = 0, srcB_neg = 1  ->   6.25   (-4.0)
#     opflags bit1 = 1, srcB_neg = 0  ->   6.25   (-4.0)
#     opflags bit1 = 1, srcB_neg = 1  ->  14.25   (+4.0)
# D8 is the paired control with a GPR srcB: there bit1 has NO sign effect and is
# the documented release-src1 lifetime bit (the released register reads 0 after).
# So bit1's meaning is OPERAND-CLASS DEPENDENT, and EXP-0167's -1 is that
# experiment's bit1 folded into the constant.
INLINE_NEG0_SIGN = +1


def inline_sign_flip(srcB_neg, opflags):
    """True when the inline immediate is negated (EXP-0220 D7)."""
    return bool((srcB_neg & 1) ^ ((opflags >> 1) & 1))


def inline_imm_value(k):
    """Exact value of inline-immediate code k (0..63) -- EXP-0138 SS3 codec.
    Pure host arithmetic; the oracle never needs a rounding model."""
    if not (0 <= k <= 63):
        raise ValueError("inline immediate code out of range: %r" % (k,))
    e, m = k >> 3, k & 7
    return f32(m * (2.0 ** -5) if e == 0 else (8 + m) * (2.0 ** (e - 6)))


def inline_srcB_value(k, srcB_neg=0, opflags=0):
    v = inline_imm_value(k) * INLINE_NEG0_SIGN
    return f32(-v if inline_sign_flip(srcB_neg, opflags) else v)


INLINE_IMM_TABLE = {}
for _k in range(64):
    INLINE_IMM_TABLE.setdefault(inline_imm_value(_k), _k)


def inline_imm_encode(x):
    xv = f32(x)
    if xv not in INLINE_IMM_TABLE:
        raise ValueError("%r is not exactly representable as a falu2 inline immediate" % (x,))
    return INLINE_IMM_TABLE[xv]


def load_byte_offset(idx, idx_off, code):
    """EXP-0082 HW-VALIDATED device_load address formula."""
    idx_off &= 0x7FF
    scale = DL_ELEM_SCALE[code]
    index_term = idx * scale
    if code in (1, 2):
        index_term = (index_term // 4) * 4
    return (index_term + idx_off * 4) & 0xFFFFFFFF


def store_byte_offset(idx, idx_off):
    """EXP-0082 HW-VALIDATED device_store address formula (16-byte idx_off unit)."""
    return (idx * 4 + (idx_off & 0x7FF) * 16) & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# instruction builders -- every field RULE or FREE
# ---------------------------------------------------------------------------
def mov_imm(E, dst, imm7, salt="m"):
    """2B mov_imm.  imm7 is SEVEN bits (EXP-0140: imm_top = 1 does not extend
    the immediate -- the instruction then does not write at all and, unpadded,
    consumes the following 2-byte instruction).  imm7 == 12 is excluded: it does
    not tokenize under the current length rule (EXP-0140 db_defects)."""
    if not (0 <= imm7 <= 127):
        raise ValueError("mov_imm imm7 out of the 7-bit range: %r" % imm7)
    if imm7 == 12:
        raise ValueError("mov_imm imm7 == 12 does not tokenize (EXP-0140)")
    return E.emit("mov_imm", {
        "dst": FV(dst & 0xF, RULE, "EXP-0031/EXP-0140 mov_imm.dst 0..15 dense"),
        "imm7": FV(imm7, RULE, "EXP-0031/EXP-0140 imm7 0..127 load-bearing"),
        "imm_top": FV(0, RULE, "EXP-0140 imm_top=1 suppresses the write"),
    })


def stop(E, offnatural=True, salt="s"):
    """4B stop.  Body = 0 is the driver rule.  EXP-0206 CORRECTED the older
    'any body is a no-op': the final word is fetched and executed, and a
    CONTROL-FLOW LEADER in body byte 0 (0x0f / 0x8f) faults.  The off-natural
    value below is chosen to avoid those."""
    v = choose("stop.reserved", [0x5A5A5A, 0x000001], 0, salt) if offnatural else 0
    return E.emit("stop", {
        "reserved": FV(v, FREE,
                       "EXP-0003/EXP-0010 E4 inert 24-bit pad; EXP-0206 G17P: inert over "
                       "73 sampled values on three carriers, control-flow leaders excluded",
                       "offnat" if v else ""),
    })


def device_load(E, index_reg, idx_off, elem_code, base_slot, R, salt,
                offnatural=True, ld_format=None):
    """14B device_load whose destination register is R (0..63).

    Every field RULE or FREE.  `dst_lo` / `dst_ext9` -- the pair EXP-0112 copied
    verbatim -- are computed from EXP-0141's exact mask rules."""
    lsb = (zlib.crc32(("extlsb|%s" % salt).encode()) & 1) if offnatural else 0
    ldf = ld_format if ld_format is not None else DL_LDFORMAT_ONE_REGISTER[0]
    d9 = choose("dl.dst_ext9", [1, 3, 65, 127], 1, salt) if offnatural else 1
    return E.emit("device_load", {
        "space": FV(choose("dl.space", [0, 20, 252], 0x10, salt) if offnatural else 0x10,
                    FREE, "EXP-0141 exact rule v&0x03==0 (G17P-confirmed set, "
                          "EXP-0167 frozen_pilot DL_FIELD_OK)", "offnat" if offnatural else ""),
        "addr_mode": FV(choose("dl.addr_mode", DL_ADDRMODE_OK, 0x44, salt) if offnatural else 0x44,
                        FREE, "EXP-0141 inert 256/256 on this shape; G17P-confirmed at "
                              "0,0xA5,0xFF (EXP-0167 frozen_pilot)", "offnat" if offnatural else ""),
        "extmode": FV(((R << 1) | lsb) & 0xFF, RULE,
                      "EXP-0101 H1 + EXP-0141: extmode = 2*R, bit0 don't-care",
                      "offnat" if lsb else ""),
        "base_slot": FV(base_slot & 0xFF, RULE,
                        "EXP-0220 arm S0: slot->bound-buffer mapping determined by HARDWARE "
                        "PROBE in this experiment, not read off a compiled instruction"),
        "index_reg": FV(index_reg & 0xFF, RULE, "EXP-0141 index GPR selector, r0..r95 valid"),
        "access_desc": FV(choose("dl.access_desc", DL_ACCESSDESC_OK, 0x20, salt) if offnatural else 0x20,
                          FREE, "EXP-0141 inert 256/256; G17P-confirmed at 0,0x5A,0xFF",
                          "offnat" if offnatural else ""),
        "reserved7": FV(choose("dl.reserved7", DL_RESERVED_OK, 0, salt) if offnatural else 0,
                        FREE, "EXP-0141 inert 256/256; G17P-confirmed at 0x5A,0xFF",
                        "offnat" if offnatural else ""),
        "ld_format": FV(ldf, RULE,
                        "EXP-0167 frozen_pilot DL_LDFORMAT_ONE_REGISTER (G17P): 17 and 49 "
                        "deliver the addressed word to the extmode target and write no "
                        "other register"),
        "dst_lo": FV(1, RULE, "EXP-0141 EXACT rule dst_lo & 0x03 == 0x01"),
        "dst_ext9": FV(d9, RULE, "EXP-0141 EXACT rule dst_ext9 & 0x01 == 0x01",
                       "offnat" if d9 != 1 else ""),
        "idx_off": FV(idx_off & 0x7FF, RULE, "EXP-0082 load address formula"),
        "ldform_hi11": FV(choose("dl.ldform_hi11", [0, 24, 56], 0x10, salt) if offnatural else 0x10,
                          FREE, "EXP-0141 exact rule v&0x07==0; G17P-confirmed at 0,24,56",
                          "offnat" if offnatural else ""),
        "elem_size": FV(0x40 | ((elem_code & 0x7) << 1), RULE,
                        "EXP-0082 elem_size = 0x40 | (code<<1)"),
        "reserved13": FV(choose("dl.reserved13", DL_RESERVED_OK, 0, salt) if offnatural else 0,
                         FREE, "EXP-0141 inert 256/256; G17P-confirmed at 0x5A,0xFF",
                         "offnat" if offnatural else ""),
    })


def device_store(E, index_reg, idx_off, base_slot, data_reg, salt,
                 offnatural=True, load_forwarded=False,
                 space=None, addr_mode=None, access_desc=None, reserved7=None,
                 st_format=None, st_format_ext=None, st_desc_hi=None,
                 elem_size=None, reserved13=None, extmode=None):
    """14B device_store.  Every field RULE or FREE; every one of the thirteen is
    overridable so the canonical matrix can drive each operand class explicitly.

    The DATA REGISTER is not a field of its own: `extmode = 2*R` (EXP-0090
    finding_5 / EXP-0141 H10).  `addr_mode` bit1 is the DATA-SOURCE selector
    (EXP-0141): clear = ALU-computed data, set = direct live load-result."""
    am_nat = DS_ADDRMODE_LOADFWD if load_forwarded else DS_ADDRMODE_ALU
    if addr_mode is None:
        if load_forwarded:
            # bit1 REQUIRED when the source is a forwarded load (EXP-0141);
            # the other bits are inert, so the chooser still goes off-natural.
            pool = [v for v in (0x56, 0x02, 0xFE, 0xA6) if v & 0x02]
            addr_mode = choose("ds.addr_mode.fwd", pool, am_nat, salt) if offnatural else am_nat
        else:
            addr_mode = choose("ds.addr_mode", [0, 0xA5, 0xFF, 0x54], am_nat, salt) \
                if offnatural else am_nat
    return E.emit("device_store", {
        "space": FV(space if space is not None else
                    (choose("ds.space", [0, 20, 252], 0, salt) if offnatural else 0),
                    FREE, "EXP-0141 exact rule v&0x02==0 (device space); G17P-confirmed "
                          "at 0,20,252 (EXP-0167 frozen_pilot DS_FIELD_OK)",
                    "offnat" if offnatural and space is None else ""),
        "addr_mode": FV(addr_mode, RULE if load_forwarded else FREE,
                        "EXP-0141: byte+2 bit1 is the DATA-SOURCE selector -- clear = "
                        "ALU-computed (inert 256/256), set = REQUIRED for a live "
                        "load-result forward",
                        "offnat" if addr_mode != am_nat else ""),
        "extmode": FV((extmode if extmode is not None else (data_reg << 1)) & 0xFF, RULE,
                      "EXP-0090 finding_5 / EXP-0141 H10: extmode>>1 = source register"),
        "base_slot": FV(base_slot & 0xFF, RULE,
                        "EXP-0220 arm S0: slot->bound-buffer mapping determined by HARDWARE "
                        "PROBE in this experiment, not read off a compiled instruction"),
        "index_reg": FV(index_reg & 0xFF, RULE, "EXP-0092/EXP-0141 index GPR 0..95"),
        "access_desc": FV(access_desc if access_desc is not None else
                          (choose("ds.access_desc", DS_ACCESSDESC_OK, 0x21, salt)
                           if offnatural else 0x21),
                          FREE, "EXP-0141 inert 256/256; G17P-confirmed at 0,0x5A,0xFF",
                          "offnat" if offnatural and access_desc is None else ""),
        "reserved7": FV(reserved7 if reserved7 is not None else
                        (choose("ds.reserved7", DS_RESERVED_OK, 0, salt) if offnatural else 0),
                        FREE, "EXP-0141 inert 256/256; G17P-confirmed at 0x5A,0xFF",
                        "offnat" if offnatural and reserved7 is None else ""),
        "st_format": FV(st_format if st_format is not None else ST_FORMAT_SCALAR32, RULE,
                        "db.json st_format enum + EXP-0141: 17 = 32-bit scalar"),
        "st_format_ext": FV(st_format_ext if st_format_ext is not None else
                            (choose("ds.st_format_ext", [0, 31], 0, salt) if offnatural else 0),
                            FREE, "EXP-0141 exact rule v&0x60==0; G17P-confirmed at 0,31",
                            "offnat" if offnatural and st_format_ext is None else ""),
        "idx_off": FV(idx_off & 0x7FF, RULE, "EXP-0082 store address formula (16-byte unit)"),
        "st_desc_hi": FV(st_desc_hi if st_desc_hi is not None else
                         (choose("ds.st_desc_hi", DS_DESCHI_OK, 0x24, salt) if offnatural else 0x24),
                         FREE, "EXP-0141 exact rule v&0x11==0; G17P-confirmed at 0,10,46",
                         "offnat" if offnatural and st_desc_hi is None else ""),
        "elem_size": FV(elem_size if elem_size is not None else
                        (choose("ds.elem_size", DS_ELEM_OK, 0x11, salt) if offnatural else 0x11),
                        FREE, "EXP-0141: 96 of 256 store correctly; G17P-confirmed set "
                              "{17,23,39,55} (EXP-0167 frozen_pilot DS_FIELD_OK)",
                        "offnat" if offnatural and elem_size is None else ""),
        "reserved13": FV(reserved13 if reserved13 is not None else
                         (choose("ds.reserved13", DS_RESERVED_OK, 0, salt) if offnatural else 0),
                         FREE, "EXP-0141 inert 256/256; G17P-confirmed at 0x5A,0xFF",
                         "offnat" if offnatural and reserved13 is None else ""),
    })


def falu2(E, dst, op, srcA_reg, salt,
          srcB_reg=None, srcB_class=SRCB_CLASS_GPR, srcB_neg=0,
          inline_k=None, srcA_size=1, srcB_size=1,
          release_srcA=False, release_srcB=False, publish=True,
          load_sourced=False, mod_hi=None, ctrl=0, opflags=None,
          srcA_reg_top=None, srcB_reg_top=None, opsel=None, offnatural=True):
    """6B falu2, fully synthesised.

    Operand classes this builder can select, all from documented rules:
      * srcB GPR                     (srcB_class = 0, srcB_reg = R)
      * srcB inline float immediate  (srcB_class = 1, srcB_reg index 64..127,
                                      k = index - 64; EXP-0138 SS3 codec)
      * srcB uniform file            (srcB_class = 1, index 0..63)
      * srcB constant 0.0            (srcB_class = 2 or 3; bit2 dominates)
    `mod_hi` depends on OPERAND PROVENANCE.  EXP-0220's A13 arm measures it as a
    provenance x value x distance matrix rather than assuming either earlier
    reading:  bit0 (instr bit 44) set  ->  THE DESTINATION IS NOT WRITTEN AT ALL
    (diagnostic D9);  bits 2 and 3 must BOTH be set when an operand is a LIVE
    device_load result, i.e. the load has not yet landed (A13 load_both gap 0:
    only 0xC of {0,4,8,C,E} is exact; gap >= 1: all five are exact).  0xC is
    therefore the canonical emitter value: it is correct in both contexts.
    `opflags` bit0 = release src0, bit1 = release src1, bit2 = destination
    publication (EXP-0086/0089/0099/0119); bits 3/4 are silent corruptors
    (EXP-0105) and are always emitted 0."""
    o = FALU2_OPSEL[op] if opsel is None else opsel
    if inline_k is not None:
        if srcB_class != SRCB_CLASS_NONGPR:
            raise ValueError("inline immediate requires srcB_class = 1")
        idx7 = 64 + (inline_k & 0x3F)
        b_reg, b_top = idx7 & 0x3F, 1
    else:
        b_reg = (srcB_reg or 0) & 0x3F
        b_top = 0
    if srcB_reg_top is not None:
        b_top = srcB_reg_top
    a_top = ((srcA_reg >> 6) & 1) if srcA_reg_top is None else srcA_reg_top
    if mod_hi is None:
        if load_sourced:
            mod_hi = FALU2_MODHI_OK_LOAD[0]
        else:
            mod_hi = choose("f2.mod_hi", FALU2_MODHI_OK_ALU, 0xC, salt) if offnatural else 0xC
    if opflags is None:
        opflags = ((1 if release_srcA else 0)
                   | ((1 if release_srcB else 0) << 1)
                   | ((1 if publish else 0) << 2))
    return E.emit("falu2", {
        "dst": FV(dst & 0xF, RULE, "EXP-0090/EXP-0112 dst nibble r0..r15"),
        "srcA_size": FV(srcA_size & 1, RULE, "db.json enum: 1 = b32, 0 = b16 low half "
                                             "(EXP-0006 HW-validated)"),
        "srcA_reg": FV(srcA_reg & 0x3F, RULE, "EXP-0099/EXP-0105: 6-bit source register"),
        "opsel": FV(o & 7, RULE, "EXP-0003/EXP-0005 opsel enum (4=fadd, 5=fmul)"),
        "opflags": FV(opflags & 0x1F, RULE,
                      "EXP-0086/0089/0099/0119 lifetime bits: bit0 release src0, bit2 "
                      "destination publication; bits 3/4 are silent corruptors "
                      "(EXP-0105).  BIT1 IS OPERAND-CLASS DEPENDENT (EXP-0220 D7/D8, "
                      "G17P): with a GPR srcB it releases that register (the register "
                      "then reads 0); with a non-GPR/inline srcB it NEGATES the "
                      "immediate, XORing with srcB_neg"),
        "srcB_size": FV(srcB_size & 1, RULE, "db.json enum: 1 = b32, 0 = b16 low half"),
        "srcB_reg": FV(b_reg, RULE,
                       "EXP-0099/EXP-0119 6-bit source register; in srcB_class 1 the "
                       "index 64..127 is EXP-0138's inline 8-bit minifloat"),
        "ctrl": FV(ctrl & 0x7F, RULE,
                   "EXP-0119: ctrl bits 0/1 are the INSTRUCTION-LENGTH selector -- 0 "
                   "selects the 6-byte form; bits 5/6 corrupt (EXP-0113)"),
        "srcB_imm": FV(0, RULE,
                       "db.json bit39 = 0: not the falu2i packed-immediate overload"),
        "srcA_class": FV(SRCA_CLASS_GPR, RULE,
                         "EXP-0138 source-class model: 0 = srcA reads the GPR file"),
        "srcB_class": FV(srcB_class & 3, RULE,
                         "EXP-0138 source-class model: 0 = GPR, 1 = non-GPR file / inline "
                         "immediate, 2 and 3 read 0.0 (bit2 dominates bit1)",
                         "offnat" if srcB_class != 0 else ""),
        "srcB_neg": FV(srcB_neg & 1, RULE, "EXP-M4-10 / EXP-0006: srcB negate bit"),
        "mod_hi": FV(mod_hi & 0xF, RULE,
                     "EXP-0167 frozen_pilot (G17P): ALU-sourced operand -> the eight EVEN "
                     "values deliver the correct result (bit0 must be 0); LOAD-sourced "
                     "operand -> 0xC is the only working value (EXP-0101 H1)",
                     "offnat" if mod_hi != 0xC else ""),
        "srcA_reg_top": FV(a_top & 1, RULE,
                           "EXP-0099/0105/0113/0119 HW-TESTED INERT top bit (six families)",
                           "offnat" if a_top else ""),
        "srcB_reg_top": FV(b_top & 1, RULE,
                           "EXP-0099 inert in GPR mode; EXP-0138 SS3: LIVE in srcB_class 1, "
                           "where it selects the inline-immediate half of the file"),
    })


# ---------------------------------------------------------------------------
# whole-program assembly
# ---------------------------------------------------------------------------
def build_program(E, carrier_len, pad_dst=13):
    """Pad the generated body out to the carrier's `_agc.main` length with
    2-byte `mov_imm` words that run strictly AFTER `stop` and are never
    reached.  imm7 = 0 keeps imm_top clear (EXP-0140) and avoids the imm7 == 12
    tokenization hole."""
    body = E.body()
    if len(body) > carrier_len:
        raise ValueError("program body %d bytes exceeds carrier length %d"
                         % (len(body), carrier_len))
    remainder = carrier_len - len(body)
    if remainder % 2:
        raise ValueError("odd padding remainder %d" % remainder)
    pad_e = Emitter()
    pad_e.led = E.led                       # padding is ledgered too
    pad_e.off = E.off
    pad = b""
    for _ in range(remainder // 2):
        pad += mov_imm(pad_e, pad_dst, 0, salt="pad")
    E.parts.extend(pad_e.parts)
    E.off = pad_e.off
    out = body + pad
    assert len(out) == carrier_len
    return out


def decode_fields_as(mnemonic, raw):
    """Independently extract a descriptor's field values from RAW BYTES.

    This is the Gate A decode path and it is deliberately NOT `assemble`'s
    inverse-by-construction: it reads bits OUT of the byte string that will be
    dispatched, and checks the descriptor's own match bits are satisfied.  It
    does not consult the length rule, because the caller already knows the
    instruction's length -- it generated it.  (Section 3z: `decode_one` answers
    "do these bytes match a descriptor", never "does an instruction start
    here"; here the boundary is known by construction, so the length rule is
    not the right instrument.)"""
    desc = isadb._BY_MNEM[mnemonic]
    if len(raw) != desc["length"]:
        raise ValueError("%s: length %d != descriptor %d"
                         % (mnemonic, len(raw), desc["length"]))
    v = int.from_bytes(raw, "little")
    match_ok = True
    for (start, width, value) in desc["match"]:
        if ((v >> start) & ((1 << width) - 1)) != (value & ((1 << width) - 1)):
            match_ok = False
    fields = {f["name"]: (v >> f["start"]) & ((1 << f["width"]) - 1)
              for f in desc["fields"]}
    return fields, match_ok


def gate_a_ledger(prog_bytes, parts):
    """Gate A: decode the ACTUAL bytes and compare with what the caller asked for.

    Returns (rows, disagreements).  Each row names the offset, the requested
    field values, and the values independently decoded from the bytes that will
    be dispatched.  A symmetric assemble/disassemble round trip is NOT this
    gate: the comparison is against the CALLER'S ledger, not against the
    disassembler's own output re-encoded."""
    rows, bad, alias = [], [], []
    # -- (i) the whole-program framing walk (a FINDING, not the gate) --------
    walk_boundaries, walk_leftover = set(), 0
    try:
        recs, leftover = isadb.disassemble(prog_bytes)
        walk_leftover = len(leftover)
        o = 0
        walk_by_off = {}
        for r in recs:
            walk_boundaries.add(o)
            walk_by_off[o] = r
            o += r["length"]
    except Exception:                                  # noqa: BLE001
        walk_by_off = {}
    # -- (ii) THE GATE: per-instruction, at the offset we generated ----------
    for (o, mnem, req, b) in parts:
        actual = prog_bytes[o:o + len(b)]
        if actual != b:
            # a requested bit the assembler could not set or clear (DEF-0166)
            bad.append({"kind": "bytes", "offset": o, "mnemonic": mnem,
                        "requested": b.hex(), "actual": actual.hex()})
            continue
        try:
            got, match_ok = decode_fields_as(mnem, actual)
        except Exception as e:                          # noqa: BLE001
            bad.append({"kind": "decode_error", "offset": o, "mnemonic": mnem,
                        "error": str(e)[:120]})
            continue
        if not match_ok:
            bad.append({"kind": "match_bits", "offset": o, "mnemonic": mnem,
                        "bytes": actual.hex()})
        diffs = {k: [v, got.get(k)] for k, v in req.items() if got.get(k) != v}
        if diffs:
            bad.append({"kind": "field", "offset": o, "mnemonic": mnem,
                        "diffs": diffs})
        w = walk_by_off.get(o)
        if w is None:
            alias.append({"kind": "not_a_walk_boundary", "offset": o,
                          "mnemonic": mnem, "bytes": actual.hex()})
        elif w["mnemonic"] != mnem:
            alias.append({"kind": "descriptor_ambiguity", "offset": o,
                          "requested": mnem, "decoded": w["mnemonic"],
                          "bytes": actual.hex()})
        rows.append({"offset": o, "mnemonic": mnem, "requested": req,
                     "decoded_actual": got, "bytes": b.hex(),
                     "actual_bytes": actual.hex()})
    if walk_leftover:
        alias.append({"kind": "walk_leftover_bytes", "n": walk_leftover})
    return rows, bad, alias
