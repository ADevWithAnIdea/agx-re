#!/usr/bin/env python3
"""EXP-0158 provenance-tracking instruction emitter (G17P / A18 Pro).

THE POINT OF THIS FILE.  EXP-0112 proved a generator can build correct AGX9
programs on the M4, but its DOC-02 labelling pass showed *how*: several field
values were lifted VERBATIM from a compiled shader because no rule for them
existed.  EXP-0138 / EXP-0139 / EXP-0140 / EXP-0141 / EXP-0128 have since
established those rules on hardware.  This module re-emits every instruction
EXP-0112 emitted, but **every field value carries a machine-checked
provenance tag**, and the experiment's headline number is "how many programs
pass with ZERO `COPIED` fields".

Direct ancestor: `experiments/EXP-0149-m4-generator-synthesis/synth.py` (our
own code, committed but never run -- that attempt was killed by local-M4 host
instability before its first capture).  EXP-0149 is NOT modified; this is a
fresh experiment number with a fresh pre-registration, per CODEX.  What is NEW
here relative to EXP-0149:

  * `falu2` `mod_hi` / `mod_lo` are RULE, not "measure it in a pilot": EXP-0138
    established `mod_lo` as an OPERAND-SOURCE-CLASS field (0..7 dense,
    hardware-run) and EXP-0105/EXP-0099 established `mod_hi` bit44 as the only
    live bit.  EXP-0149 planned to discover these; they are now documented.
  * `falu2_imm()` -- the **inline 8-bit float immediate** EXP-0138 found in
    `mod_lo` class 1 (`srcB_reg` 64..127).  This lets the generator materialise
    a float constant with NO `mov_imm` and NO separate `falu2i` seed step.
  * an integrity SENTINEL store and a POISONED read-back buffer, per
    FIELD-SWEEP-PROTOCOL.md section 7.

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
  PILOT   no PRIOR rule exists, but this experiment MEASURED the field's
          accepted set on THIS target (G17P) with its own disclosed pre-freeze
          pilot (PRE_REGISTRATION.md section 6), and the emitted value is
          chosen from that measured set.  This is still synthesis -- the value
          comes from hardware probing, not from a donor instruction -- but it
          is reported separately so a reader can see exactly which values rest
          on this experiment's own pilot rather than on published rules.
  COPIED  no rule exists; the value is lifted verbatim from a compiled
          shader.  A case with any COPIED field is NOT fully synthesised.

TARGET: G17P (Apple A18 Pro).  Every rule cited below was established on the
M4/G16G; re-running them here IS the point -- a divergence is a first-class
finding, not a bug.

Nothing here inspects an Apple binary.  Every cited rule was established by
this repository's own hardware sweeps over our own compiled/spliced shaders.
"""

import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
# READ-ONLY use of a PINNED, hash-recorded snapshot of tools/agx-isa (see
# work/isadb_pinned/README.txt): the live tools/agx-isa/db.json is edited
# concurrently by the orchestrator, and a two-run byte-identity gate must not
# depend on a file that can move between run01 and run02.
PINNED_ISA = HERE / "work" / "isadb_pinned"
sys.path.insert(0, str(PINNED_ISA))
import isadb  # noqa: E402  (READ-ONLY: assemble/disassemble/imm_encode/imm_decode)
assert Path(isadb._DB_JSON).resolve() == (PINNED_ISA / "db.json").resolve(), \
    "synth.py must load the PINNED db.json, got %s" % isadb._DB_JSON

RULE, FREE, PILOT, CARRIER, COPIED = "RULE", "FREE", "PILOT", "CARRIER", "COPIED"


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
        c = {RULE: 0, FREE: 0, PILOT: 0, CARRIER: 0, COPIED: 0}
        for r in self.rows:
            c[r["prov"]] += 1
        return c

    def copied_fields(self):
        return sorted({"%s.%s" % (r["instr"], r["field"]) for r in self.rows
                       if r["prov"] == COPIED})

    def carrier_fields(self):
        return sorted({"%s.%s" % (r["instr"], r["field"]) for r in self.rows
                       if r["prov"] == CARRIER})

    def pilot_fields(self):
        return sorted({"%s.%s" % (r["instr"], r["field"]) for r in self.rows
                       if r["prov"] == PILOT})

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
# ---------------------------------------------------------------------------
# DIAGNOSTIC KNOBS.  Empty in every gated run (asserted by verify.py); used only
# by work/diag/ to isolate WHICH off-natural choice a failure depends on, one
# variable at a time.  Adding them is cheaper and far more honest than guessing.
# ---------------------------------------------------------------------------
DISABLE_OFFNAT = set()          # any of: "dl", "ds", "modhi", "stop", "extlsb"


def choose_confirmed(key, field, accepted, natural, salt, table_name):
    """Like `choose`, but restricted to the values this experiment's own pilot
    CONFIRMED `ok` on G17P for that field.  The published accepted sets
    (EXP-0141) are M4 evidence; the gated corpus must not put an
    unconfirmed-on-target value into a field it then reports as correct.  If the
    pilot never touched the field, the published set stands and the citation
    says so."""
    import frozen_pilot as FP
    grp = "dl" if table_name == "DL_FIELD_OK" else "ds"
    if grp in DISABLE_OFFNAT or ("%s:%s" % (grp, field)) in DISABLE_OFFNAT:
        return natural
    tbl = (getattr(FP, table_name, None) or {}).get(field)
    if tbl:
        ok = [int(v) for v, o in tbl.items() if o == "ok"]
        if ok:
            accepted = sorted(ok)
    return choose(key, accepted, natural, salt)


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


# ---------------------------------------------------------------------------
# HARDWARE RULE TABLES -- every entry cites the experiment that established it
# ---------------------------------------------------------------------------
# device_load  (EXP-0141 RESULTS.md H1 + analysis/field_verdicts.json)
DL_SPACE_OK = [v for v in range(256) if v & 0x03 == 0x00]          # exact mask rule
DL_ADDRMODE_OK = list(range(256))                                   # INERT, 256/256
DL_ACCESSDESC_OK = list(range(256))                                 # INERT, 256/256
DL_RESERVED_OK = list(range(256))                                   # INERT, 256/256
# ld_format.  EXP-0141 recorded 21 of 64 codes as "delivering the 32-bit
# scalar", and EXP-0158's first gated capture (raw/g17p-20260830-run01) shows
# why that is not enough for an emitter: codes 19/21/23/25/27/29/31/51 DO
# deliver the addressed word to the extmode target AND ALSO WRITE 1-3 further
# CONSECUTIVE REGISTERS with the following memory words.  In a single-load
# probe nothing else is live and the extra writes are invisible; in a
# register-allocated program they silently corrupt unrelated values.
# `work/diag/diag_ldformat.jsonl` measures the width of every code tested;
# `frozen_pilot.DL_LDFORMAT_ONE_REGISTER` is the safe set (17 and 49).
DL_LDFORMAT_OK = [17, 19, 21, 23, 25, 27]      # historical: EXP-0141's reading


def ldformat_choices():
    import frozen_pilot as FP
    return FP.DL_LDFORMAT_ONE_REGISTER or [17]
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

# ---------------------------------------------------------------------------
# falu2 modifier bytes -- RULE as of EXP-0138 / EXP-0105 / EXP-0099.
#
# `mod_hi` (4 bits, instr bits 44..47).  validation.json, evidence EXP-0105 +
# EXP-0099: "bit44 at {0,1} (silent corrupt-to-zero ...); bits45-47 at all 8
# values (no observable effect)".  So bit0 of the field is load-bearing and
# must be 0; bits 1..3 are a documented DON'T CARE.  EXP-0138 independently
# reproduced exactly this shape on the sibling `falu2_ext`/`falu2_srcmod10`
# encodings ("ok: 0,2,4,6,8,10,12,14; wrong_value: the odd values"), which is
# why this is treated as a rule rather than a copied 0xC.  EXP-0112 copied
# mod_hi = 0xC verbatim; 0xC is simply one of the eight even values.
FALU2_MODHI_OK = [v for v in range(16) if (v & 1) == 0]   # the a-priori derivation


def pick_mod_hi(load_sourced, salt, offnatural):
    """Choose `falu2.mod_hi` from the set this experiment's own pilot MEASURED
    on G17P for the relevant operand provenance.  Falls back to the a-priori
    even-values derivation only while the pilot is unfrozen (import-time, in
    tools that never emit)."""
    import frozen_pilot as FP
    if load_sourced:
        ok = FP.FALU2_MODHI_OK_LOAD or [0xC]
        return 0xC if 0xC in ok else ok[0]
    if "modhi" in DISABLE_OFFNAT:
        return 0xC
    ok = FP.FALU2_MODHI_OK_ALU or FALU2_MODHI_OK
    return choose("f2.mod_hi", ok, 0xC, salt) if offnatural else 0xC

# `mod_lo` (3 bits, instr bits 40..42) -- EXP-0138's OPERAND-SOURCE-CLASS
# model (field_verdicts.json "falu2.mod_lo".semantics_model, hardware-run,
# 0..7 dense):
#     bit0     = 0 -> srcA reads GPR[srcA_reg]         (what we always want)
#     bits[2:1]= 0 -> srcB reads GPR[srcB_reg]
#                = 1 -> srcB reads the NON-GPR operand file at srcB_reg:
#                       0..63  = uniform registers
#                       64..127 = INLINE 8-BIT MINIFLOAT IMMEDIATE
#                = 2,3 -> read 0.0 (bit2 dominates bit1)
# The PINNED db.json already carries EXP-0138's model as two named fields:
#   srcA_class (bit 40, 1 bit)  and  srcB_class (bits 41..42, 2 bits).
SRCA_CLASS_GPR = 0       # srcA reads GPR[srcA_reg]
SRCB_CLASS_GPR = 0       # srcB reads GPR[srcB_reg]
SRCB_CLASS_NONGPR = 1    # srcB reads the non-GPR file: 0..63 uniform, 64..127 inline imm
FALU2_MOD_CITE = "EXP-0138 field_verdicts falu2.mod_lo (now db.json srcA_class/srcB_class) + EXP-0105/0099 mod_hi"


# ---------------------------------------------------------------------------
# falu2 INLINE 8-BIT FLOAT IMMEDIATE codec (EXP-0138 RESULTS.md SS3)
#   srcB 7-bit operand index 64..127, k = index - 64, e = k>>3, m = k&7:
#       value = m * 2**-5            (e == 0)
#       value = (8 + m) * 2**(e-6)   (e  > 0)
#   HW-confirmed on M4 at k = 0,2,3,31,32,48,56,61,62,63.
# ---------------------------------------------------------------------------
def inline_imm_value(k):
    """Exact value of inline-immediate code k (0..63).  Pure host arithmetic."""
    if not (0 <= k <= 63):
        raise ValueError("inline immediate code out of range: %r" % (k,))
    e, m = k >> 3, k & 7
    return f32(m * (2.0 ** -5) if e == 0 else (8 + m) * (2.0 ** (e - 6)))


# The SIGN the hardware gives an inline immediate when `srcB_neg` is 0 is NOT
# stated by EXP-0138 (which fitted magnitudes only).  It is measured by this
# experiment's own disclosed pre-freeze pilot (arms P4/P5) and frozen into
# `frozen_pilot.py` BEFORE the gated runs; nothing here guesses it.
def inline_srcB_value(k, srcB_neg=0):
    import frozen_pilot as FP
    v = inline_imm_value(k) * FP.INLINE_NEG0_SIGN
    return f32(-v if srcB_neg else v)


INLINE_IMM_TABLE = {}
for _k in range(64):
    INLINE_IMM_TABLE.setdefault(inline_imm_value(_k), _k)
INLINE_IMM_VALUES = sorted(INLINE_IMM_TABLE)


def inline_imm_encode(x):
    """Smallest k whose inline-immediate value is EXACTLY x.  Raises if x is
    not representable -- the generator only ever draws from
    INLINE_IMM_VALUES, so the oracle is exact by construction and never
    depends on a rounding model."""
    xv = f32(x)
    if xv not in INLINE_IMM_TABLE:
        raise ValueError("%r is not an exactly representable falu2 inline immediate" % (x,))
    return INLINE_IMM_TABLE[xv]


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
    if "stop" in DISABLE_OFFNAT:
        offnatural = False
    v = choose("stop.reserved", [0, 1, 0x5A5A5A], 0, "s") if offnatural else 0
    return emit(led, "stop", {
        "reserved": FV(v, FREE, "EXP-0003/EXP-0010 full 24-bit body corrupted, no-op",
                       "offnat" if v else ""),
    })


def device_load(led, index_reg, idx_off, elem_code, base_slot, R, salt,
                offnatural=True, dst_lo_override=None, dst_ext9_override=None,
                extmode_override=None, ld_format_override=None):
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
        lsb = (zlib.crc32(("extlsb|%s" % salt).encode()) & 1) \
            if (offnatural and "extlsb" not in DISABLE_OFFNAT) else 0
        ext = FV(((R << 1) | lsb) & 0xFF, RULE,
                 "EXP-0101 H1 + EXP-0141 (extmode = 2*R, bit0 don't-care)",
                 "offnat" if lsb else "")
    ldf_nat = 17
    if ld_format_override is not None:
        ldf = ld_format_override
    else:
        ldf = choose("dl.ld_format", ldformat_choices(), ldf_nat, salt) \
            if (offnatural and "dl" not in DISABLE_OFFNAT
                and "dl:ld_format" not in DISABLE_OFFNAT) else ldf_nat
    d9 = dst_ext9_override
    if d9 is None:
        d9 = choose_confirmed("dl.dst_ext9", "dst_ext9", DL_DSTEXT9_OK, 1, salt, "DL_FIELD_OK") if offnatural else 1
    dl = dst_lo_override if dst_lo_override is not None else 1
    return emit(led, "device_load", {
        "space": FV(choose_confirmed("dl.space", "space", DL_SPACE_OK, 0x10, salt, "DL_FIELD_OK") if offnatural else 0x10,
                    FREE, "EXP-0141 exact rule v&0x03==0", "offnat"),
        "addr_mode": FV(choose_confirmed("dl.addr_mode", "addr_mode", DL_ADDRMODE_OK, 0x44, salt, "DL_FIELD_OK") if offnatural else 0x44,
                        FREE, "EXP-0141 INERT 256/256 on this shape", "offnat"),
        "extmode": ext,
        "base_slot": FV(base_slot & 0xFF, CARRIER,
                        "re-derived from our own compiled carrier by baseline.py"),
        "index_reg": FV(index_reg & 0xFF, RULE,
                        "EXP-0141 index GPR selector, r0..r95 valid"),
        "access_desc": FV(choose_confirmed("dl.access_desc", "access_desc", DL_ACCESSDESC_OK, 0x20, salt, "DL_FIELD_OK") if offnatural else 0x20,
                          FREE, "EXP-0141 INERT 256/256", "offnat"),
        "reserved7": FV(choose_confirmed("dl.reserved7", "reserved7", DL_RESERVED_OK, 0x00, salt, "DL_FIELD_OK") if offnatural else 0,
                        FREE, "EXP-0141 INERT 256/256", "offnat"),
        "ld_format": FV(ldf, RULE,
                        "EXP-0158 work/diag/diag_ldformat.jsonl: the code must be one "
                        "that writes EXACTLY ONE register; EXP-0141's wider "
                        "'delivers the 32-bit scalar' set also writes 1-3 further "
                        "consecutive registers",
                        "offnat" if ldf != ldf_nat else ""),
        "dst_lo": FV(dl, RULE, "EXP-0141 EXACT rule dst_lo & 0x03 == 0x01"),
        "dst_ext9": FV(d9, RULE, "EXP-0141 EXACT rule dst_ext9 & 0x01 == 0x01",
                       "offnat" if d9 != 1 else ""),
        "idx_off": FV(idx_off & 0x7FF, RULE, "EXP-0082 address formula"),
        "ldform_hi11": FV(choose_confirmed("dl.ldform_hi11", "ldform_hi11", DL_LDFORMHI_OK, 0x10, salt, "DL_FIELD_OK") if offnatural else 0x10,
                          FREE, "EXP-0141 exact rule v&0x07==0", "offnat"),
        "elem_size": FV(0x40 | ((elem_code & 0x7) << 1), RULE,
                        "EXP-0082 elem_size = 0x40 | (code<<1)"),
        "reserved13": FV(choose_confirmed("dl.reserved13", "reserved13", DL_RESERVED_OK, 0x00, salt, "DL_FIELD_OK") if offnatural else 0,
                         FREE, "EXP-0141 INERT 256/256", "offnat"),
    })


def device_store(led, index_reg, idx_off, base_slot, data_reg, salt, offnatural=True,
                 addr_mode_override=None):
    """14B device_store.  extmode = 2*data_reg is EXP-0090 finding_5, now
    dense over three registers in EXP-0141 (addendum H10)."""
    am_nat = 0x54
    am = addr_mode_override if addr_mode_override is not None else (
        choose_confirmed("ds.addr_mode", "addr_mode", DS_ADDRMODE_OK, am_nat, salt, "DS_FIELD_OK") if offnatural else am_nat)
    return emit(led, "device_store", {
        "space": FV(choose_confirmed("ds.space", "space", DS_SPACE_OK, 0x00, salt, "DS_FIELD_OK") if offnatural else 0,
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
        "access_desc": FV(choose_confirmed("ds.access_desc", "access_desc", DL_ACCESSDESC_OK, 0x21, salt, "DS_FIELD_OK") if offnatural else 0x21,
                          FREE, "EXP-0141 INERT 256/256", "offnat"),
        "reserved7": FV(choose_confirmed("ds.reserved7", "reserved7", DL_RESERVED_OK, 0x00, salt, "DS_FIELD_OK") if offnatural else 0,
                        FREE, "EXP-0141 INERT 256/256", "offnat"),
        "st_format": FV(choose_confirmed("ds.st_format", "st_format", DS_STFORMAT_OK, 17, salt, "DS_FIELD_OK") if offnatural else 17,
                        RULE, "EXP-0141: 84 of 256 store the 32-bit scalar", "offnat"),
        "st_format_ext": FV(choose_confirmed("ds.st_format_ext", "st_format_ext", DS_STFMTEXT_OK, 0, salt, "DS_FIELD_OK") if offnatural else 0,
                            FREE, "EXP-0141 exact rule v&0x60==0", "offnat"),
        "idx_off": FV(idx_off & 0x7FF, RULE, "EXP-0082 store address formula"),
        "st_desc_hi": FV(choose_confirmed("ds.st_desc_hi", "st_desc_hi", DS_DESCHI_OK, 0x24, salt, "DS_FIELD_OK") if offnatural else 0x24,
                         FREE, "EXP-0141 exact rule v&0x11==0", "offnat"),
        "elem_size": FV(choose_confirmed("ds.elem_size", "elem_size", DS_ELEM_OK, 0x11, salt, "DS_FIELD_OK") if offnatural else 0x11,
                        FREE, "EXP-0141: 96 of 256 store correctly", "offnat"),
        "reserved13": FV(choose_confirmed("ds.reserved13", "reserved13", DL_RESERVED_OK, 0x00, salt, "DS_FIELD_OK") if offnatural else 0,
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


def falu2(led, dst, op, srcA_reg, srcB_reg, last_use_srcA, salt="g", offnatural=True,
          mod_hi_override=None, srcB_class_override=None, srcB_neg=0,
          load_sourced=False):
    """6B falu2, register-register.  FULLY SYNTHESISED.

    EXP-0112 copied `mod_hi = 0xC` verbatim ("the natural value observed in
    every own-compiled falu2 reg-reg instance") and left `mod_lo = 0` untested.
    Both are now RULE:
      * `mod_hi` depends on the OPERAND PROVENANCE, which is a finding of this
        experiment's own pilot (arms P1/P2) and a correction to the record.
        For an ALU-sourced operand, bit0 (instr bit44) is the only live bit and
        must be 0 -- 8 of 16 values deliver the right answer and the odd 8
        silently zero, so the chooser picks an even value that is usually NOT
        the compiler's 0xC.  For a LOAD-sourced operand, `mod_hi = 0xC` is the
        ONLY value of sixteen that works: the other seven even values leave the
        loaded operand reading 0.  EXP-0105/EXP-0099's "bits45-47 have no
        observable effect" was measured with an ALU-sourced operand and does
        NOT generalise; EXP-0101 H1's `mods = 0xC0` is the same constraint seen
        through falu2i's 8-bit `mods` window.
      * `srcA_class = 0` / `srcB_class = 0` is the operand-source class
        "srcA GPR, srcB GPR" (EXP-0138's source-class model, carried in the
        pinned db.json as two named fields).  Computed class selectors, not a
        copied byte.
    `opflags` bit1 ("both real") per EXP-0090 finding_1; bit0 = liveness
    (EXP-0086)."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    mh = mod_hi_override if mod_hi_override is not None else pick_mod_hi(
        load_sourced, salt, offnatural)
    bcl = SRCB_CLASS_GPR if srcB_class_override is None else srcB_class_override
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
        "srcA_class": FV(SRCA_CLASS_GPR, RULE, FALU2_MOD_CITE + " (srcA reads the GPR file)"),
        "srcB_class": FV(bcl, RULE, FALU2_MOD_CITE + " (0 = srcB reads the GPR file)",
                         "offnat" if bcl != 0 else ""),
        "srcB_neg": FV(srcB_neg & 1, RULE, "EXP-M4-10: srcB negate bit"),
        "mod_hi": FV(mh & 0xF, PILOT if not load_sourced else RULE,
                     ("EXP-0158 pilot P1: 8 of 16 values work for an ALU-sourced "
                      "operand (bit0 must be 0)") if not load_sourced else
                     ("EXP-0101 H1 + EXP-0158 pilot P2: 0xC is the ONLY value of "
                      "16 that works for a LOAD-sourced operand"),
                     "offnat" if mh != 0xC else ""),
        "srcA_reg_top": FV((srcA_reg >> 6) & 1, RULE, "EXP-0099 inert top bit"),
        "srcB_reg_top": FV((srcB_reg >> 6) & 1, RULE, "EXP-0099 inert top bit"),
    })


def falu2_imm(led, dst, op, srcA_reg, k_value, last_use_srcA, salt="i", offnatural=True,
              srcB_neg=0, srcB_class_override=None, imm_code_override=None,
              srcB_reg_top_override=None, load_sourced=False):
    """6B falu2 with an INLINE 8-BIT FLOAT IMMEDIATE as srcB -- EXP-0138's
    largest single find, used here for the first time by a generator.

    `srcB_class = 1` puts srcB in the non-GPR operand class; the 7-bit srcB
    operand index 64..127 is then an inline minifloat with code k = index-64.
    This materialises a float constant with NO `mov_imm` and NO separate
    `falu2i` seed instruction -- the whole point of exercising it here.

    `k_value` must be EXACTLY representable (see inline_imm_encode); the
    generator only ever draws from INLINE_IMM_VALUES."""
    opsel = {"fadd": 4, "fmul": 5}[op]
    k = imm_code_override if imm_code_override is not None else inline_imm_encode(k_value)
    idx7 = 64 + (k & 0x3F)                       # bit6 set => the immediate class
    mh = pick_mod_hi(load_sourced, salt + "i", offnatural)
    bcl = SRCB_CLASS_NONGPR if srcB_class_override is None else srcB_class_override
    btop = 1 if srcB_reg_top_override is None else srcB_reg_top_override
    return emit(led, "falu2", {
        "dst": FV(dst & 0xF, RULE, "EXP-0090/0112 dst nibble r0..r15"),
        "srcA_size": FV(1, RULE, "b32 operand"),
        "srcA_reg": FV(srcA_reg & 0x3F, RULE, "EXP-0099/0105 6-bit source register"),
        "opsel": FV(opsel, RULE, "EXP-0005/0006 opsel enum"),
        "opflags": FV(((1 if last_use_srcA else 0) | (1 << 1)) & 0x1F, RULE,
                      "EXP-0090 finding_1 (bit1) + EXP-0086 liveness (bit0)"),
        "srcB_size": FV(1, RULE, "b32 operand (the tested configuration)"),
        "srcB_reg": FV(idx7 & 0x3F, RULE,
                       "EXP-0138 SS3: inline minifloat code k = srcB_index-64"),
        "ctrl": FV(0, RULE, "EXP-0119: ctrl bits 0/1 select the 6-byte form"),
        "srcB_imm": FV(0, RULE,
                       "db.json bit39=0: this is NOT the falu2i packed-immediate "
                       "overload -- the inline immediate lives in the mod_lo class"),
        "srcA_class": FV(SRCA_CLASS_GPR, RULE, "EXP-0138: srcA still reads the GPR file"),
        "srcB_class": FV(bcl, RULE,
                         "EXP-0138 source-class model: srcB_class=1 -> srcB reads the "
                         "non-GPR file (0..63 uniform, 64..127 inline minifloat)",
                         "offnat"),
        "srcB_neg": FV(srcB_neg & 1, RULE, "EXP-M4-10 srcB negate bit"),
        "mod_hi": FV(mh & 0xF, PILOT if not load_sourced else RULE,
                     "EXP-0158 pilot P1/P2 (see falu2)", "offnat" if mh != 0xC else ""),
        "srcA_reg_top": FV((srcA_reg >> 6) & 1, RULE, "EXP-0099 inert top bit"),
        "srcB_reg_top": FV(btop & 1, RULE,
                           "EXP-0138 SS3: srcB bit6 is LIVE in the non-GPR class and "
                           "selects the inline-immediate half of the file"),
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
        # Restrict to the values pilot arm P11 MEASURED `ok` on G17P for this
        # field.  EXP-0139 recorded most of these as INERT on the M4; `srcA` is
        # demonstrably NOT inert here (44 of 64 sampled values deliver the sum;
        # the rest place it in the upper half-word or silently zero), which is
        # what broke six IADD_SYNTH cases in raw/g17p-20260830-run01.
        import frozen_pilot as FP
        meas = (FP.IADD_FIELD_OK or {}).get(key.split(".")[-1])
        if meas:
            ok = sorted(meas)
        return choose(key, ok, nat, salt) if offnatural else nat
    return emit(led, "iadd2", {
        "addsub": FV(addsub & 1, RULE, "EXP-0128 SS1.4 polarity (1=add, 0=rN-r0)"),
        "lenbit": FV(IA_LENBIT, RULE, "EXP-0139: only value 1 works"),
        "srcB_reg_hi": FV(pick("ia.srcB_reg_hi", IA_SRCBREGHI_OK, 0), PILOT,
                          "EXP-0158 P11: inert on G17P too (16/16 sampled)", "offnat"),
        "b2_bit0": FV(pick("ia.b2_bit0", IA_B2BIT0_OK, 0), PILOT, "EXP-0158 P11: inert (2/2)", "offnat"),
        "store_en": FV(pick("ia.store_en", IA_STOREEN_OK, 1), PILOT, "EXP-0158 P11: inert (2/2)", "offnat"),
        "b2_fmt": FV(pick("ia.b2_fmt", IA_B2FMT_OK, 0x15), PILOT, "EXP-0158 P11: inert (63/64; 1 victim)", "offnat"),
        "dst": FV(((dst_reg << 1) | 1) & 0xFF, RULE,
                  "EXP-0139: dst = (reg<<1)|size; reg>=96 faults"),
        "opmode": FV(pick("ia.opmode", IA_OPMODE_OK, 2), PILOT,
                     "EXP-0158 P11: bit1 set is sufficient (16/16 sampled)", "offnat"),
        "srcB_imm": FV((4 * N) & 0xFF, RULE, "EXP-0128/0139: srcB_imm = 4*N selects r_N"),
        "srcB_imm_hi": FV(0, RULE, "EXP-0139: only 0 works"),
        "srcB_ext": FV(pick("ia.srcB_ext", IA_SRCBEXT_OK, 0), PILOT,
                       "EXP-0158 P11: 0..3 all ok on G17P; semantics UNKNOWN", "offnat"),
        "srcA": FV(pick("ia.srcA", IA_SRCA_OK, 0xA8), PILOT,
                   "EXP-0158 P11 REFUTES EXP-0139's 'only bits 0,1 decide' on G17P: "
                   "44 of 64 sampled values give the sum; (v&0x18)==0 puts it in the "
                   "UPPER half-word (17 -> 0x110000) and (v&0x7C)==0x50 silently "
                   "zeroes. Chosen from the measured-ok set.", "offnat"),
        "opc_tail": FV(pick("ia.opc_tail", IA_OPCTAIL_OK, 0x17), PILOT,
                       "EXP-0158 P11: 58/64 sampled ok (bits 0,4 set)", "offnat"),
        "opc_tail2": FV(pick("ia.opc_tail2", IA_OPCTAIL2_OK, 0x05), PILOT,
                        "EXP-0158 P11: 64/64 sampled ok (bits 0,2 set)", "offnat"),
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
# INTEGRITY SENTINEL + POISONED READ-BACK  (FIELD-SWEEP-PROTOCOL.md section 7)
# ---------------------------------------------------------------------------
# The read-back buffer is pre-filled by the harness with the 32-bit poison word
# POISON_U32; a word that still reads as poison means the program never wrote
# it at all, which is a DIFFERENT observation from a silent zero.  The sentinel
# is written through a path independent of everything under test: `mov_imm`
# (an INTEGER immediate move, EXP-0140/EXP-0128 hardware-run) into a register,
# then one `device_store`.  It contains no falu2/falu2i/device_load, so a
# correct sentinel beside a wrong data word proves the program ran, was
# spliced, and stored -- i.e. the wrong data word is a real field result and
# not a dead dispatch.  A wrong or poisoned SENTINEL invalidates the case.
POISON_U32 = 0xDEADBEEF
SENTINEL_IMM7 = 0x55          # 85; not 0, not the non-tokenizing 12 (EXP-0140)
SENTINEL_IDX_OFF = 63         # store unit is 16 bytes -> out word 63*4 = 252
SENTINEL_REG = 13             # inside POOL, but the sentinel executes FIRST


def sentinel_word_index():
    return store_byte_offset(0, SENTINEL_IDX_OFF) // 4


def sentinel_expected_f32():
    return bits_f32(SENTINEL_IMM7)


def sentinel_instrs(led, base_slot_out, salt):
    """The two-instruction integrity sentinel.  MUST be emitted immediately
    after the index-register setup and BEFORE any program body, so that no
    later register reuse can affect it."""
    return [
        mov_imm(led, SENTINEL_REG, SENTINEL_IMM7, salt=salt + "sent"),
        device_store(led, R_IDX, SENTINEL_IDX_OFF, base_slot_out,
                     data_reg=SENTINEL_REG, salt=salt + "sent", offnatural=False),
    ]


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
