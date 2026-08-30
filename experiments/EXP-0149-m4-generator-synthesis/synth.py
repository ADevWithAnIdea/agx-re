#!/usr/bin/env python3
"""EXP-0149 provenance-tracking instruction emitter.

THE POINT OF THIS FILE.  EXP-0112 proved a generator can build correct AGX9
programs, but `work/DOC-02-LABELLING-REPORT.md` showed *how*: several field
values were lifted VERBATIM from a compiled shader because no rule for them
existed.  EXP-0141 / EXP-0139 / EXP-0140 / EXP-0128 have since established
those rules on hardware.  This module re-emits every instruction EXP-0112
emitted, but **every field value carries a machine-checked provenance tag**,
and the experiment's headline number is "how many programs pass with ZERO
`COPIED` fields".

PROVENANCE CLASSES (exactly four; every emitted field gets one):

  RULE    the value is COMPUTED from a documented hardware rule or formula.
          A rule-mandated constant (e.g. `device_load.dst_lo` must be 1) is
          RULE, not COPIED: the emitter derives it, it does not read it off a
          donor instruction.  Citation mandatory.
  FREE    the field has a documented DON'T-CARE range; the value is picked by
          this module's own deterministic chooser, which deliberately prefers
          a value the compiler would NOT emit.  Citation (the sweep that
          established the range) mandatory.
  CARRIER a binding parameter re-derived from OUR OWN compiled carrier kernel
          (`base_slot` only).  Not an instruction token copied from a donor,
          but it is not synthesised either, so it is tracked and reported
          separately.
  COPIED  no rule exists; the value is lifted verbatim from a compiled
          shader.  A case with any COPIED field is NOT fully synthesised.

Nothing here inspects an Apple binary.  Every cited rule was established by
this repository's own hardware sweeps over our own compiled/spliced shaders.
"""
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (READ-ONLY: assemble/disassemble/imm_encode/imm_decode)

RULE, FREE, CARRIER, COPIED = "RULE", "FREE", "CARRIER", "COPIED"


class FV(object):
    """One field value plus its provenance."""
    __slots__ = ("value", "prov", "cite", "note")

    def __init__(self, value, prov, cite, note=""):
        self.value = int(value)
        self.prov = prov
        self.cite = cite
        self.note = note

    def __repr__(self):
        return "FV(%d,%s,%s)" % (self.value, self.prov, self.cite)


# ---------------------------------------------------------------------------
# provenance ledger -- every emit() appends here; casematrix summarises it
# ---------------------------------------------------------------------------
class Ledger(object):
    def __init__(self):
        self.rows = []

    def add(self, mnemonic, name, fv):
        self.rows.append({"instr": mnemonic, "field": name, "value": fv.value,
                          "prov": fv.prov, "cite": fv.cite, "note": fv.note})

    def counts(self):
        c = {RULE: 0, FREE: 0, CARRIER: 0, COPIED: 0}
        for r in self.rows:
            c[r["prov"]] += 1
        return c

    def copied_fields(self):
        return sorted({"%s.%s" % (r["instr"], r["field"]) for r in self.rows
                       if r["prov"] == COPIED})

    def carrier_fields(self):
        return sorted({"%s.%s" % (r["instr"], r["field"]) for r in self.rows
                       if r["prov"] == CARRIER})

    def offnatural(self):
        return sorted({"%s.%s=%d" % (r["instr"], r["field"], r["value"])
                       for r in self.rows if r["prov"] == FREE and "offnat" in r["note"]})


def emit(led, mnemonic, fields):
    """fields: {name: FV}. Records provenance, then assembles via the
    READ-ONLY tools/agx-isa isadb."""
    vals = {}
    for k, fv in fields.items():
        if not isinstance(fv, FV):
            raise TypeError("%s.%s must be an FV, got %r" % (mnemonic, k, fv))
        led.add(mnemonic, k, fv)
        vals[k] = fv.value
    return isadb.assemble(mnemonic, vals)


# ---------------------------------------------------------------------------
# deterministic OFF-NATURAL chooser
# ---------------------------------------------------------------------------
def choose(key, accepted, natural, salt):
    """Deterministically pick a value from `accepted`, PREFERRING one that is
    not `natural` (i.e. not the value a compiler emits).  Pure function of
    (key, salt) -- identical on every machine and every re-run."""
    acc = list(accepted)
    if not acc:
        raise ValueError("empty accepted set for " + key)
    alt = [v for v in acc if v != natural]
    pool = alt if alt else acc
    h = zlib.crc32((key + "|" + str(salt)).encode()) & 0xFFFFFFFF
    return pool[h % len(pool)]


# ---------------------------------------------------------------------------
# HARDWARE RULE TABLES -- every entry cites the experiment that established it
# ---------------------------------------------------------------------------
# device_load  (EXP-0141 RESULTS.md H1 + analysis/field_verdicts.json)
DL_SPACE_OK = [v for v in range(256) if v & 0x03 == 0x00]          # exact mask rule
DL_ADDRMODE_OK = list(range(256))                                   # INERT, 256/256
DL_ACCESSDESC_OK = list(range(256))                                 # INERT, 256/256
DL_RESERVED_OK = list(range(256))                                   # INERT, 256/256
# ld_format: 21 of 64 codes deliver the 32-bit scalar.  Restricted here to the
# six explicitly enumerated in EXP-0141's own accepted_values string that also
# belong to the 16 formats under which dst_ext9 bits 1..6 are ALL free.
DL_LDFORMAT_OK = [17, 19, 21, 23, 25, 27]
DL_DSTEXT9_OK = [v for v in range(128) if v & 0x01 == 0x01]         # bit0 must be 1
DL_LDFORMHI_OK = [v for v in range(64) if v & 0x07 == 0x00]         # low 3 bits must be 0
DL_ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}                     # EXP-0082

# device_store (EXP-0141 analysis/field_verdicts.json)
DS_SPACE_OK = [v for v in range(256) if v & 0x02 == 0x00]
DS_ADDRMODE_OK = list(range(256))          # INERT for an ALU-computed source
DS_STFORMAT_OK = [17, 19, 21, 23, 25, 27]  # subset of the 84 accepted, enumerated
DS_STFMTEXT_OK = [v for v in range(128) if v & 0x60 == 0x00]
DS_DESCHI_OK = [v for v in range(64) if v & 0x11 == 0x00]
DS_ELEM_OK = list(range(16, 24)) + list(range(32, 40)) + list(range(48, 56))

# iadd2 register mode (EXP-0128 SS1.2/SS1.4 + EXP-0139 SS1.3 field sweeps)
IA_LENBIT = 1                                       # only working value
IA_SRCBREGHI_OK = list(range(128))                   # INERT, 128/128
IA_B2BIT0_OK = [0, 1]                                # INERT
IA_STOREEN_OK = [0, 1]                               # INERT
IA_B2FMT_OK = list(range(64))                        # INERT
IA_OPMODE_OK = [v for v in range(256) if v & 0x02]   # bit1 decides
IA_SRCBEXT_OK = [0, 1, 2, 3]                         # only 4 of 128 work (semantics UNKNOWN)
IA_SRCA_OK = [v for v in range(256) if v & 0x03 == 0x00]      # bits 0,1 must be 0
IA_OPCTAIL_OK = [v for v in range(256) if v & 0x11 == 0x11]   # bits 0,4 must be set
IA_OPCTAIL2_OK = [v for v in range(256) if v & 0x05 == 0x05]  # bits 0,2 must be set

# falu2 modifier bytes: no published rule at dispatch time; measured by THIS
# experiment's own disclosed pilot (PRE_REGISTRATION.md SS6) and then frozen.
FALU2_MODHI_OK = None    # filled in by freeze_pilot()
FALU2_MODLO_OK = None
FALU2_MOD_CITE = "EXP-0149-pilot"


def freeze_pilot(mod_hi_ok, mod_lo_ok):
    global FALU2_MODHI_OK, FALU2_MODLO_OK
    FALU2_MODHI_OK = sorted(mod_hi_ok)
    FALU2_MODLO_OK = sorted(mod_lo_ok)


# ---------------------------------------------------------------------------
# float / immediate helpers (unchanged semantics from EXP-0112; RULE-grade)
# ---------------------------------------------------------------------------
def imm_value(k):
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def bits_f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


POOL = list(range(14))     # r0..r13 -- falu2/falu2i dst is a hard 4-bit nibble
R_UNWRITTEN = 14           # never written; reads 0.0 (EXP-0087 MOVE-04)
R_IDX = 15                 # index GPR, held at 0


def load_byte_offset(idx, idx_off, code):
    """EXP-0082 HW-VALIDATED device_load address formula."""
    idx_off = idx_off & 0x7FF
    scale = DL_ELEM_SCALE[code]
    index_term = idx * scale
    if code in (1, 2):
        index_term = (index_term // 4) * 4
    return (index_term + idx_off * 4) & 0xFFFFFFFF


def store_byte_offset(idx, idx_off):
    """EXP-0082 HW-VALIDATED device_store address formula."""
    return (idx * 4 + idx_off * 16) & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# instruction builders -- SYNTHESISED
# ---------------------------------------------------------------------------
def mov_imm(led, dst, imm7, salt="m"):
    """2B mov_imm.  imm7 is 7 bits (EXP-0140: imm_top=1 does NOT extend the
    immediate -- the instruction then does not write at all and unpadded eats
    the next 2-byte instruction).  imm7 == 12 is excluded: it does not
    tokenize under the current length rule (EXP-0140 db_defects)."""
    if not (0 <= imm7 <= 127):
        raise ValueError("mov_imm imm7 out of the 7-bit range: %r" % imm7)
    if imm7 == 12:
        raise ValueError("mov_imm imm7 == 12 does not tokenize (EXP-0140)")
    return emit(led, "mov_imm", {
        "dst": FV(dst & 0xF, RULE, "EXP-0140 mov_imm.dst 0..15 dense"),
        "imm7": FV(imm7, RULE, "EXP-0140/EXP-0031 imm7 0..127 load-bearing"),
        "imm_top": FV(0, RULE, "EXP-0140 imm_top=1 suppresses the write"),
    })


def stop(led, offnatural=True):
    v = choose("stop.reserved", [0, 1, 0x5A5A5A], 0, "s") if offnatural else 0
    return emit(led, "stop", {
        "reserved": FV(v, FREE, "EXP-0003/EXP-0010 full 24-bit body corrupted, no-op",
                       "offnat" if v else ""),
    })


def device_load(led, index_reg, idx_off, elem_code, base_slot, R, salt,
                offnatural=True, dst_lo_override=None, dst_ext9_override=None,
                extmode_override=None):
    """14B device_load whose destination register is R (0..63).

    EVERY field below is RULE or FREE.  In particular `dst_lo` and `dst_ext9`
    -- the pair EXP-0112 copied verbatim and DOC-02 named "the single biggest
    synthesis blocker in the ISA" -- are now computed from EXP-0141's exact
    mask rules (`dst_lo & 3 == 1`; `dst_ext9 & 1 == 1`)."""
    if extmode_override is not None:
        ext = FV(extmode_override & 0xFF, RULE,
                 "EXP-0141 extmode: R = extmode>>1, bit7 must be 0", "explicit override")
    else:
        # bit 0 of extmode is a documented DON'T CARE -- deliberately set it on
        # half the cases, which no compiler ever does.
        lsb = (zlib.crc32(("extlsb|%s" % salt).encode()) & 1) if offnatural else 0
        ext = FV(((R << 1) | lsb) & 0xFF, RULE,
                 "EXP-0101 H1 + EXP-0141 (extmode = 2*R, bit0 don't-care)",
                 "offnat" if lsb else "")
    ldf_nat = 17
    ldf = choose("dl.ld_format", DL_LDFORMAT_OK, ldf_nat, salt) if offnatural else ldf_nat
    d9 = dst_ext9_override
    if d9 is None:
        d9 = choose("dl.dst_ext9", DL_DSTEXT9_OK, 1, salt) if offnatural else 1
    dl = dst_lo_override if dst_lo_override is not None else 1
    return emit(led, "device_load", {
        "space": FV(choose("dl.space", DL_SPACE_OK, 0x10, salt) if offnatural else 0x10,
                    FREE, "EXP-0141 exact rule v&0x03==0", "offnat"),
        "addr_mode": FV(choose("dl.addr_mode", DL_ADDRMODE_OK, 0x44, salt) if offnatural else 0x44,
                        FREE, "EXP-0141 INERT 256/256 on this shape", "offnat"),
        "extmode": ext,
        "base_slot": FV(base_slot & 0xFF, CARRIER,
                        "re-derived from our own compiled carrier by baseline.py"),
        "index_reg": FV(index_reg & 0xFF, RULE,
                        "EXP-0141 index GPR selector, r0..r95 valid"),
        "access_desc": FV(choose("dl.access_desc", DL_ACCESSDESC_OK, 0x20, salt) if offnatural else 0x20,
                          FREE, "EXP-0141 INERT 256/256", "offnat"),
        "reserved7": FV(choose("dl.reserved7", DL_RESERVED_OK, 0x00, salt) if offnatural else 0,
                        FREE, "EXP-0141 INERT 256/256", "offnat"),
        "ld_format": FV(ldf, RULE,
                        "EXP-0141: 21 of 64 codes deliver the 32-bit scalar; "
                        "this subset also leaves dst_ext9 bits 1..6 free",
                        "offnat" if ldf != ldf_nat else ""),
        "dst_lo": FV(dl, RULE, "EXP-0141 EXACT rule dst_lo & 0x03 == 0x01"),
        "dst_ext9": FV(d9, RULE, "EXP-0141 EXACT rule dst_ext9 & 0x01 == 0x01",
                       "offnat" if d9 != 1 else ""),
        "idx_off": FV(idx_off & 0x7FF, RULE, "EXP-0082 address formula"),
        "ldform_hi11": FV(choose("dl.ldform_hi11", DL_LDFORMHI_OK, 0x10, salt) if offnatural else 0x10,
                          FREE, "EXP-0141 exact rule v&0x07==0", "offnat"),
        "elem_size": FV(0x40 | ((elem_code & 0x7) << 1), RULE,
                        "EXP-0082 elem_size = 0x40 | (code<<1)"),
        "reserved13": FV(choose("dl.reserved13", DL_RESERVED_OK, 0x00, salt) if offnatural else 0,
                         FREE, "EXP-0141 INERT 256/256", "offnat"),
    })


def device_store(led, index_reg, idx_off, base_slot, data_reg, salt, offnatural=True,
                 addr_mode_override=None):
    """14B device_store.  extmode = 2*data_reg is EXP-0090 finding_5, now
    dense over three registers in EXP-0141 (addendum H10)."""
    am_nat = 0x54
    am = addr_mode_override if addr_mode_override is not None else (
        choose("ds.addr_mode", DS_ADDRMODE_OK, am_nat, salt) if offnatural else am_nat)
    return emit(led, "device_store", {
        "space": FV(choose("ds.space", DS_SPACE_OK, 0x00, salt) if offnatural else 0,
                    FREE, "EXP-0141 exact rule v&0x02==0", "offnat"),
        "addr_mode": FV(am, FREE,
                        "EXP-0141: INERT 256/256 when the stored data is ALU-computed "
                        "(bit1 only matters for a live load-result forward)",
                        "offnat" if am != am_nat else ""),
        "extmode": FV((data_reg << 1) & 0xFF, RULE,
                      "EXP-0090 finding_5 / EXP-0141 H10: extmode>>1 = source register"),
        "base_slot": FV(base_slot & 0xFF, CARRIER,
                        "re-derived from our own compiled carrier by baseline.py"),
        "index_reg": FV(index_reg & 0xFF, RULE, "EXP-0092 index GPR 0..95"),
        "access_desc": FV(choose("ds.access_desc", DL_ACCESSDESC_OK, 0x21, salt) if offnatural else 0x21,
                          FREE, "EXP-0141 INERT 256/256", "offnat"),
        "reserved7": FV(choose("ds.reserved7", DL_RESERVED_OK, 0x00, salt) if offnatural else 0,
                        FREE, "EXP-0141 INERT 256/256", "offnat"),
        "st_format": FV(choose("ds.st_format", DS_STFORMAT_OK, 17, salt) if offnatural else 17,
                        RULE, "EXP-0141: 84 of 256 store the 32-bit scalar", "offnat"),
        "st_format_ext": FV(choose("ds.st_format_ext", DS_STFMTEXT_OK, 0, salt) if offnatural else 0,
                            FREE, "EXP-0141 exact rule v&0x60==0", "offnat"),
        "idx_off": FV(idx_off & 0x7FF, RULE, "EXP-0082 store address formula"),
        "st_desc_hi": FV(choose("ds.st_desc_hi", DS_DESCHI_OK, 0x24, salt) if offnatural else 0x24,
                         FREE, "EXP-0141 exact rule v&0x11==0", "offnat"),
        "elem_size": FV(choose("ds.elem_size", DS_ELEM_OK, 0x11, salt) if offnatural else 0x11,
                        FREE, "EXP-0141: 96 of 256 store correctly", "offnat"),
        "reserved13": FV(choose("ds.reserved13", DL_RESERVED_OK, 0x00, salt) if offnatural else 0,
                         FREE, "EXP-0141 INERT 256/256", "offnat"),
    })


def falu2i(led, dst, op, srcA_reg, k, last_use_srcA, load_sourced, salt="f"):
    """6B falu2i.  `mods` = 0xC0 exactly when srcA is a bridged device_load
    target (EXP-0101 H1); liveness bit is opflags bit0 (EXP-0086/0090)."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    b1, sign = isadb.imm_encode(k)
    return emit(led, "falu2i", {
        "dst": FV(dst & 0xF, RULE, "EXP-0090/0112 dst nibble r0..r15"),
        "imm_flag": FV(b1 & 1, RULE, "EXP-0006 minifloat codec"),
        "imm_mant": FV((b1 >> 1) & 0x7, RULE, "EXP-0006 minifloat codec"),
        "imm_exp": FV((b1 >> 4) & 0xF, RULE, "EXP-0006 minifloat codec"),
        "opsel": FV(opsel, RULE, "EXP-0005/0006 opsel enum"),
        "imm_sign": FV(sign & 1, RULE, "EXP-0006 minifloat codec"),
        "opflags": FV((1 if last_use_srcA else 0) & 0xF, RULE,
                      "EXP-0086/0089/0099/0119 opflags bit0 = release srcA"),
        "srcA_size": FV(1, RULE, "b32 operand (db.json enum)"),
        "srcA_reg": FV(srcA_reg & 0x3F, RULE,
                       "EXP-0099/0105: the source register field is 6 bits"),
        "ctrl_lo": FV(0, RULE, "EXP-0119: ctrl bits 0/1 are the length selector; "
                               "0 selects the 6-byte form"),
        "mods": FV(0xC0 if load_sourced else 0x00, RULE,
                   "EXP-0101 H1: bits 6+7 together, required iff load-sourced"),
        "srcA_reg_top": FV((srcA_reg >> 6) & 1, RULE,
                           "EXP-0099/0119: HW-TESTED INERT top bit"),
    })


def falu2(led, dst, op, srcA_reg, srcB_reg, last_use_srcA, salt="g", offnatural=True):
    """6B falu2 (register-register).  opflags bit1 ('both real') set per
    EXP-0090 finding_1.  mod_hi/mod_lo come from THIS experiment's own pilot
    sweep (see PRE_REGISTRATION.md SS6) -- they were EXP-0112's other copied
    tokens."""
    if FALU2_MODHI_OK is None:
        raise RuntimeError("synth.freeze_pilot() must run before falu2 emission")
    opsel = {"fadd": 4, "fmul": 5}[op]
    mh = choose("f2.mod_hi", FALU2_MODHI_OK, 0xC, salt) if offnatural else 0xC
    ml = choose("f2.mod_lo", FALU2_MODLO_OK, 0x0, salt) if offnatural else 0
    return emit(led, "falu2", {
        "dst": FV(dst & 0xF, RULE, "EXP-0090/0112 dst nibble r0..r15"),
        "srcA_size": FV(1, RULE, "b32 operand"),
        "srcA_reg": FV(srcA_reg & 0x3F, RULE, "EXP-0099/0105 6-bit source register"),
        "opsel": FV(opsel, RULE, "EXP-0005/0006 opsel enum"),
        "opflags": FV(((1 if last_use_srcA else 0) | (1 << 1)) & 0x1F, RULE,
                      "EXP-0090 finding_1 (bit1) + EXP-0086 liveness (bit0)"),
        "srcB_size": FV(1, RULE, "b32 operand"),
        "srcB_reg": FV(srcB_reg & 0x3F, RULE, "EXP-0099/0119 6-bit source register"),
        "ctrl": FV(0, RULE, "EXP-0119: ctrl bits 0/1 select the 6-byte form"),
        "srcB_imm": FV(0, RULE, "db.json enum: 0 = srcB is a register"),
        "mod_lo": FV(ml, FREE, FALU2_MOD_CITE, "offnat" if ml != 0 else ""),
        "srcB_neg": FV(0, RULE, "EXP-M4-10: srcB negate bit; 0 = no negate"),
        "mod_hi": FV(mh, FREE, FALU2_MOD_CITE, "offnat" if mh != 0xC else ""),
        "srcA_reg_top": FV((srcA_reg >> 6) & 1, RULE, "EXP-0099 inert top bit"),
        "srcB_reg_top": FV((srcB_reg >> 6) & 1, RULE, "EXP-0099 inert top bit"),
    })


def iadd2_regmode(led, dst_reg, N, addsub, salt, offnatural=True):
    """10B iadd2 in REGISTER mode -- fully synthesised.

    EXP-0128 SS1.2/SS1.4 (HW-VALIDATED): srcA is a format-only byte whose
    register role is a constant read of r0; `srcB_imm = 4*N` selects r_N;
    `addsub=1` gives r0 + r_N and `addsub=0` gives r_N - r0 (NOT r0 - r_N).
    EXP-0139 SS1.3 swept every other field densely: `dst = (reg<<1)|size`
    with reg < 96, `lenbit` must be 1, `srcB_imm_hi` must be 0, `opmode`
    bit 1 must be set, `srcA & 3 == 0`, `opc_tail & 0x11 == 0x11`,
    `opc_tail2 & 0x05 == 0x05`, `srcB_ext` in 0..3, and
    `srcB_reg_hi`/`b2_bit0`/`store_en`/`b2_fmt` are INERT.

    This replaces EXP-0112's `iadd2_anchor`, whose entire byte pattern was
    copied verbatim.  NOTHING here is copied."""
    if not (0 <= dst_reg < 96):
        raise ValueError("iadd2 dst register %d >= 96 faults reproducibly (EXP-0139)" % dst_reg)
    if not (0 <= N <= 15):
        raise ValueError("iadd2 srcB_imm = 4*N validated only for N in 0..15 (EXP-0128)")
    def pick(key, ok, nat):
        return choose(key, ok, nat, salt) if offnatural else nat
    return emit(led, "iadd2", {
        "addsub": FV(addsub & 1, RULE, "EXP-0128 SS1.4 polarity (1=add, 0=rN-r0)"),
        "lenbit": FV(IA_LENBIT, RULE, "EXP-0139: only value 1 works"),
        "srcB_reg_hi": FV(pick("ia.srcB_reg_hi", IA_SRCBREGHI_OK, 0), FREE,
                          "EXP-0139 INERT 128/128", "offnat"),
        "b2_bit0": FV(pick("ia.b2_bit0", IA_B2BIT0_OK, 0), FREE, "EXP-0139 INERT", "offnat"),
        "store_en": FV(pick("ia.store_en", IA_STOREEN_OK, 1), FREE, "EXP-0139 INERT", "offnat"),
        "b2_fmt": FV(pick("ia.b2_fmt", IA_B2FMT_OK, 0x15), FREE, "EXP-0139 INERT 64/64", "offnat"),
        "dst": FV(((dst_reg << 1) | 1) & 0xFF, RULE,
                  "EXP-0139: dst = (reg<<1)|size; reg>=96 faults"),
        "opmode": FV(pick("ia.opmode", IA_OPMODE_OK, 2), FREE,
                     "EXP-0139: only bit1 decides", "offnat"),
        "srcB_imm": FV((4 * N) & 0xFF, RULE, "EXP-0128/0139: srcB_imm = 4*N selects r_N"),
        "srcB_imm_hi": FV(0, RULE, "EXP-0139: only 0 works"),
        "srcB_ext": FV(pick("ia.srcB_ext", IA_SRCBEXT_OK, 0), FREE,
                       "EXP-0139: 4 of 128 values work (0..3); semantics UNKNOWN", "offnat"),
        "srcA": FV(pick("ia.srcA", IA_SRCA_OK, 0xA8), FREE,
                   "EXP-0139: only bits 0,1 decide (must be 0); the byte does not "
                   "select a register -- the first operand is always r0 (EXP-0128)", "offnat"),
        "opc_tail": FV(pick("ia.opc_tail", IA_OPCTAIL_OK, 0x17), FREE,
                       "EXP-0139: only bits 0,4 decide", "offnat"),
        "opc_tail2": FV(pick("ia.opc_tail2", IA_OPCTAIL2_OK, 0x05), FREE,
                        "EXP-0139: only bits 0,2 decide", "offnat"),
    })


def iadd2_immediate_anchor_COPIED(led, srcB_imm_raw, dst=0):
    """10B iadd2 in IMMEDIATE mode -- the EXP-0090/EXP-0112 verbatim anchor,
    RETAINED DELIBERATELY and tagged COPIED.

    EXP-0139's dense field sweeps were run on the REGISTER-mode carrier, and
    its masks do not describe this shape (this anchor's `opc_tail2 = 4` fails
    EXP-0139's `v & 0x05 == 0x05` rule yet demonstrably executes), so no rule
    is available for the immediate-mode tail.  Keeping this family is how this
    experiment reports an HONEST count of what still needs a donor."""
    return emit(led, "iadd2", {
        "addsub": FV(1, COPIED, "EXP-0090 anchor"),
        "lenbit": FV(1, COPIED, "EXP-0090 anchor"),
        "srcB_reg_hi": FV(0, COPIED, "EXP-0090 anchor"),
        "b2_bit0": FV(0, COPIED, "EXP-0090 anchor"),
        "store_en": FV(1, COPIED, "EXP-0090 anchor"),
        "b2_fmt": FV(0x15, COPIED, "EXP-0090 anchor"),
        "dst": FV(dst & 0xFF, COPIED, "EXP-0090 anchor"),
        "opmode": FV(2, COPIED, "EXP-0090 anchor"),
        "srcB_imm": FV(srcB_imm_raw & 0xFF, RULE, "effective addend = srcB_imm>>1"),
        "srcB_imm_hi": FV(0, COPIED, "EXP-0090 anchor"),
        "srcB_ext": FV(0, COPIED, "EXP-0090 anchor"),
        "srcA": FV(0x88, COPIED, "EXP-0090 anchor (immediate-mode tail shape)"),
        "opc_tail": FV(0x15, COPIED, "EXP-0090 anchor"),
        "opc_tail2": FV(4, COPIED, "EXP-0090 anchor"),
    })


# ---------------------------------------------------------------------------
# whole-program assembly
# ---------------------------------------------------------------------------
def build_program(led, instrs, carrier_len, pad_dst=13):
    body = b"".join(instrs)
    if len(body) > carrier_len:
        raise ValueError("program body %d bytes exceeds carrier length %d"
                         % (len(body), carrier_len))
    remainder = carrier_len - len(body)
    if remainder % 2:
        raise ValueError("odd padding remainder %d" % remainder)
    # padding runs strictly AFTER stop() and is never reached.  imm7=0 keeps
    # imm_top clear (EXP-0140) and avoids the imm7==12 tokenization hole.
    pad = mov_imm(led, pad_dst, 0, salt="pad") * (remainder // 2)
    out = body + pad
    assert len(out) == carrier_len
    return out


def assert_round_trip(hexbytes):
    recs, leftover = isadb.disassemble(hexbytes)
    if leftover:
        raise AssertionError("round-trip: %d leftover bytes: %s" % (len(leftover), leftover.hex()))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])
        want = hexbytes[off:off + r["length"]]
        if got != want:
            raise AssertionError("round-trip mismatch at +0x%x (%s): %s != %s"
                                 % (off, r["mnemonic"], got.hex(), want.hex()))
        off += r["length"]
    return recs
