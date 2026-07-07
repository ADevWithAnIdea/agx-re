#!/usr/bin/env python3
# isadb.py -- clean-room machine-readable instruction database for the Apple
# A18 Pro (G17P) AGX shader ISA, plus a table-driven assembler and disassembler.
#
# CLEAN-ROOM: every encoding fact in this table was learned from the compiled
# form of MSL **we wrote** (OWN-SHADER), by byte-diffing our own shaders and/or
# by splicing bytes and running them on the real GPU (hardware validation). No
# Apple binary was ever disassembled or introspected. The *shape* of this table
# (an InstructionDesc with match bits + typed bit-fields + sizes) reuses the
# design of the public MIT dougallj/applegpu database; the CONTENTS are ours,
# populated from scratch for G17P (which is a different ISA from G13/G14).
#
# One table drives both directions:
#   disassemble(bytes) -> list of {mnemonic, fields, length, provenance}
#   assemble(mnemonic, fields) -> bytes
# See roundtrip_test.py for the disasm(asm(x))==x / asm(disasm(b))==b proof.
#
# ------------------------------------------------------------------------------
# SCHEMA (each instruction descriptor)
# ------------------------------------------------------------------------------
# {
#   "mnemonic":  str,                  # e.g. "fadd"
#   "length":    int,                  # total instruction length in BYTES
#   "match":     [(bit_start, bit_width, value), ...],  # constant bits that
#                                       # identify the instruction (over the
#                                       # little-endian instruction integer)
#   "fields":    [ {                    # every non-constant bit lives in a field
#                    "name":  str,
#                    "start": int,      # bit offset within the LE instruction int
#                    "width": int,      # field width in bits
#                    "type":  "reg"|"imm"|"enum"|"mod"|"opcode"|"raw",
#                    "enum":  {int:str} # optional, for type=="enum"/"opcode"
#                  }, ... ],
#   "semantics": str,                  # human description of what it computes
#   "provenance":"HW-VALIDATED (EXP-NNNN)" | "inferred (byte-diff)" | ...
# }
#
# Bit numbering: an instruction of N bytes is interpreted as an N-byte
# little-endian integer.  bit 0  = bit 0 of byte 0 (offset +0),
#                         bit 16 = bit 0 of byte 2 (offset +2), etc.
# So "byte offset +k, bit b"  ==  bit (8*k + b).

import json

# ------------------------------------------------------------------------------
# 1. INSTRUCTION-LENGTH RULE  (EXP-0005, task 3)
# ------------------------------------------------------------------------------
# Determined empirically from OUR OWN compiled shaders (never assumed from G13).
#
# Key fact / difference from G13: on G17P the FIRST PARCEL does NOT encode the
# length.  Counter-example from our shaders: `fsub` = `09 01 1c ...` (6 bytes)
# and `fma` = `09 01 1e ...` (8 bytes) share the *identical* first parcel
# `09 01` yet differ in length.  Length is therefore a function of the opcode,
# read from byte 0 (the format/group) and -- for the float-ALU group only -- a
# length bit deeper in the instruction (byte +2, bit 1).
#
# Observed byte0 -> length table (all validated by clean tokenization of our
# own shaders; parcels are always 2 bytes so every length is even):
#
#   byte0            group / mnemonic         length (bytes)
#   ----------------------------------------------------------------
#   0x0e             stop / end               4
#   low nibble 0xC   preamble (get_sr-like)   4     (0x0C, 0x1C observed)
#   low nibble 0x7   device load/store        14    (0x67 load, 0xE7 store)
#   0x09             float ALU (2/3 source)   6, or 8 if (byte[+2] & 0x02)
#   0x0b             float unary (fmov/neg)   10
#   0x12             float min/max            6
#   0x9f             integer ALU              10 or 12  (NOT SOLVED - follow-up)
#
# The 0x09 length bit (byte +2, bit 1) selects the 6-byte 2-source base form
# from the 8-byte 3-source (fma) extended form.

LEN_UNKNOWN = None

def instr_length(buf, off=0):
    """Return the length in bytes of the instruction starting at buf[off], or
    None if the leading byte is not in our (float-family) length table.

    EXP-0006 refinement: the float-ALU group is identified by the LOW NIBBLE of
    byte0 (== 0x9), NOT the whole byte.  byte0's high nibble carries the dst
    register number (bits [4:8]), so e.g. `59 09 1c 0b 00 c0` (dst=reg5) is the
    same falu2 group as `09 01 1c 05 00 c0` (dst=reg0).  Using the full byte
    (== 0x09) mis-tokenizes any falu2 whose dst register is >= 1.
    """
    b0 = buf[off]
    lo = b0 & 0x0f
    if b0 == 0x0e:
        return 4                       # stop
    if lo == 0x0c:
        return 4                       # preamble / get_sr-like
    if lo == 0x07:
        return 14                      # device load (0x67) / store (0xE7)
    if lo == 0x09:
        # float ALU: 2-source (6B) unless the fma/3-source length bit is set.
        # NB: the 10-byte *extended source-modifier* form (abs; EXP-0006) also
        # has low-nibble 9 but is not distinguishable from byte0/byte2 alone --
        # a documented follow-up; the compiler emits it only for fabs sources.
        return 8 if (buf[off + 2] & 0x02) else 6
    if lo == 0x0b:
        return 10                      # float unary (fmov / fneg / fabs)
    if lo == 0x02 and b0 == 0x12:
        return 6                       # float min/max
    if b0 == 0x9f:
        # integer ALU family: length varies with sub-opcode and is NOT yet
        # solved (out of scope for EXP-0005; noted follow-up).
        return LEN_UNKNOWN
    return LEN_UNKNOWN


# ------------------------------------------------------------------------------
# 2. THE INSTRUCTION DATABASE
# ------------------------------------------------------------------------------
# Provenance legend:
#   HW-VALIDATED (EXP-0005): a hardware dispatch confirmed the SEMANTICS of this
#       encoding (spliced bytes ran on the A18 Pro GPU and produced the expected
#       arithmetic result).
#   inferred (byte-diff): the byte layout is established by differential
#       compilation of our own shaders, but the exact semantics of every field
#       are not each individually hardware-proven.
#   structural (inferred): included so the disassembler can tokenize a whole
#       real shader; the mnemonic is a best-guess role, not HW-proven semantics.

# Float ALU op-select enumeration.  EXP-0005 swept the whole byte at instruction
# offset +2 (256 values) on hardware and located the op-select as the LOW 3 BITS
# of that byte == instruction bits [16:19]:
#     0b100 (4) -> fadd   (d = a + b)   HW-VALIDATED
#     0b101 (5) -> fmul   (d = a * b)   HW-VALIDATED
#     0b111 (7) -> illegal op -> contained GPU fault (all 32 faults had low3==7)
#     bit 0 (instr bit16) = add(0)/mul(1)        [HW-VALIDATED, EXP-0003 & 0005]
#     bit 1 (instr bit17) = length/form bit: 0 = 6-byte 2-source, 1 = 8-byte
#                           3-source (fma). Setting it in a 2-source kernel
#                           desyncs the stream (no store) -> zero output.
#     bit 2 (instr bit18) = arithmetic-enable: must be 1 for fadd/fmul.
# The compiler's canonical encodings are op byte 0x1c (fadd) / 0x1d (fmul), whose
# low3 are 0b100/0b101; bits 3-5 (0b011 there) are don't-care for the operation
# (all 8 combinations still produced fadd/fmul on hardware).
FALU2_OPSEL_ENUM = {
    0b100: "fadd",      # HW-VALIDATED (EXP-0003/EXP-0005)
    0b101: "fmul",      # HW-VALIDATED (EXP-0003/EXP-0005)
}

# EXP-0006 packed-float-immediate (srcB immediate form). NOT IEEE-754. The 8-bit
# byte at instruction bits [8:16] is a minifloat: bit0 = a flag (always 1 = 32b
# immediate), bits[3:1] = 3-bit mantissa, bits[7:4] = 4-bit exponent (bias 11).
# The sign lives OUTSIDE this byte, at instruction bit 19 (byte+2 bit3). Normal:
# (1 + mant/8) * 2^(exp-11) for exp>=9; subnormal (exp==8): (mant/8)*2^(9-11).
# Representable magnitudes: 0, 1/32 .. 30.0. Out-of-range/undyadic K (e.g. 0.1,
# 255) make the compiler fall back to a register-load form. HW-VALIDATED across
# K in {0, +-0.0625..30} (EXP-0006 raw/validate_imm_dst.log).
def imm_decode(b1, sign):
    e = (b1 >> 4) & 0xf
    m = (b1 >> 1) & 0x7
    v = (m / 8.0) * (2.0 ** (9 - 11)) if e == 8 else (1 + m / 8.0) * (2.0 ** (e - 11))
    return -v if sign else v

def imm_encode(K):
    """Return (b1_byte, sign_bit) for the nearest representable packed immediate."""
    sign = 1 if K < 0 else 0
    a = abs(float(K)); best = None
    for e in range(8, 16):
        for m in range(8):
            v = (m / 8.0) * (2.0 ** (9 - 11)) if e == 8 else (1 + m / 8.0) * (2.0 ** (e - 11))
            b1 = (e << 4) | (m << 1) | 1
            if best is None or abs(v - a) < best[0]:
                best = (abs(v - a), b1)
    return best[1], sign

DB = [
    # ---- float 2-source ALU: fadd / fmul (reg-reg form) --------------------
    # EXP-0006 fully mapped, HW-VALIDATED, the operand encoding (little-endian
    # 48-bit instruction; bit b == byte (b//8) bit (b%8)):
    #   [0:4]   group id = 0x9                                   (match)
    #   [4:8]   dst register number (b0 high nibble)   HW-VALIDATED (dstc sweep)
    #   [8]     srcA size: 1 = 32-bit, 0 = 16-bit (reads low half) HW-VALIDATED
    #   [9:16]  srcA register number (aliases mod 64 -> 64 GPRs)  HW-VALIDATED
    #   [16:19] opsel: 0b100=fadd 0b101=fmul                      HW-VALIDATED
    #   [19:24] op/cache flags (source last-use/discard hints)    inferred
    #   [24]    srcB size (1=32b, 0=16b low half)                 HW-VALIDATED
    #   [25:32] srcB register number                              HW-VALIDATED
    #   [32:39] control (low 2 bits must be 0 for a valid store)  inferred
    #   [39]    srcB-immediate mode select (0=register srcB)      HW-VALIDATED
    #   [40:43] source-mode low bits                              inferred
    #   [43]    srcB negate modifier (a + (-b))                   HW-VALIDATED
    #   [44:48] source-mode high bits (0xC base observed)         inferred
    {
        "mnemonic": "falu2",
        "length": 6,
        "match": [(0, 4, 0x9)],        # low nibble of byte0 identifies the group
        "fields": [
            {"name": "dst",       "start": 4,  "width": 4, "type": "reg"},   # HW-VALIDATED
            {"name": "srcA_size", "start": 8,  "width": 1, "type": "enum",
             "enum": {1: "b32", 0: "b16"}},                                   # HW-VALIDATED
            {"name": "srcA_reg",  "start": 9,  "width": 7, "type": "reg"},    # HW-VALIDATED
            {"name": "opsel",     "start": 16, "width": 3, "type": "opcode",
             "enum": FALU2_OPSEL_ENUM},                                       # HW-VALIDATED
            {"name": "opflags",   "start": 19, "width": 5, "type": "mod"},    # cache/discard, inferred
            {"name": "srcB_size", "start": 24, "width": 1, "type": "enum",
             "enum": {1: "b32", 0: "b16"}},                                   # HW-VALIDATED
            {"name": "srcB_reg",  "start": 25, "width": 7, "type": "reg"},    # HW-VALIDATED
            {"name": "ctrl",      "start": 32, "width": 7, "type": "mod"},    # inferred
            {"name": "srcB_imm",  "start": 39, "width": 1, "type": "enum",
             "enum": {0: "reg", 1: "immediate"}},                            # HW-VALIDATED
            {"name": "mod_lo",    "start": 40, "width": 3, "type": "mod"},    # inferred
            {"name": "srcB_neg",  "start": 43, "width": 1, "type": "mod"},    # HW-VALIDATED (a+(-b))
            {"name": "mod_hi",    "start": 44, "width": 4, "type": "mod"},    # inferred (0xC base)
        ],
        "semantics": "d = op(srcA, [-]srcB)  ; 2-source float ALU. src operand "
                     "byte = (reg<<1)|is32 (64 GPRs, bit0=size). dst reg in b0[4:8]. "
                     "srcB negate = bit43. srcB-immediate mode = bit39 (see falu2i).",
        "provenance": "HW-VALIDATED (EXP-0006): dst/srcA/srcB positions, (reg<<1)|size "
                      "encoding, 16-bit-low-half read, srcB negate (a+b->a-b), and "
                      "srcB-immediate mode all confirmed by splice-and-observe. "
                      "opsel from EXP-0003/EXP-0005. op/cache/ctrl flag bits inferred.",
    },
    # ---- float 2-source ALU: srcB PACKED IMMEDIATE form (a + K) ------------
    # Same length (6B) as reg-reg falu2, distinguished by bit39 (srcB-imm) == 1.
    # Layout differs: b1 becomes the packed immediate; srcA moves to b3.
    {
        "mnemonic": "falu2i",
        "length": 6,
        "match": [(0, 4, 0x9), (39, 1, 1)],
        "fields": [
            {"name": "dst",       "start": 4,  "width": 4, "type": "reg"},   # HW-VALIDATED
            {"name": "imm_flag",  "start": 8,  "width": 1, "type": "mod"},   # =1 (32b imm)
            {"name": "imm_mant",  "start": 9,  "width": 3, "type": "imm"},   # HW-VALIDATED
            {"name": "imm_exp",   "start": 12, "width": 4, "type": "imm"},   # HW-VALIDATED (bias 11)
            {"name": "opsel",     "start": 16, "width": 3, "type": "opcode",
             "enum": FALU2_OPSEL_ENUM},                                       # HW-VALIDATED
            {"name": "imm_sign",  "start": 19, "width": 1, "type": "mod"},   # HW-VALIDATED (sign)
            {"name": "opflags",   "start": 20, "width": 4, "type": "mod"},   # inferred
            {"name": "srcA_size", "start": 24, "width": 1, "type": "enum",
             "enum": {1: "b32", 0: "b16"}},                                   # HW-VALIDATED
            {"name": "srcA_reg",  "start": 25, "width": 7, "type": "reg"},    # HW-VALIDATED
            {"name": "ctrl_lo",   "start": 32, "width": 7, "type": "mod"},    # inferred (bit39=imm marker)
            {"name": "mods",      "start": 40, "width": 8, "type": "mod"},    # inferred
        ],
        "semantics": "d = op(srcA, K)  ; srcB is the packed non-IEEE float immediate "
                     "K = imm_decode(b1, sign). exp(bits12:16,bias11) mant(bits9:12) "
                     "flag(bit8) sign(bit19). Range +-{0,1/32..30}. HW-VALIDATED EXP-0006.",
        "provenance": "HW-VALIDATED (EXP-0006): every K in {0,+-0.0625..30} spliced and "
                      "the runtime output equalled a+K (raw/validate_imm_dst.log).",
    },
    # ---- float 3-source ALU: fma (8-byte extended form) -------------------
    {
        "mnemonic": "falu3",
        "length": 8,
        "match": [(0, 4, 0x9), (17, 1, 1)],   # low-nibble 0x9 AND length bit (+2,bit1)
        "fields": [
            {"name": "dst",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "op",   "start": 16, "width": 8, "type": "opcode",
             "enum": {0x1e: "fma"}},
            {"name": "srcA", "start": 24, "width": 8, "type": "reg"},
            {"name": "srcB", "start": 32, "width": 8, "type": "reg"},
            {"name": "srcC", "start": 40, "width": 8, "type": "reg"},
            {"name": "ext",  "start": 48, "width": 16, "type": "raw"},
        ],
        "semantics": "d = a*b + c   ; three-source float ALU (fma)",
        "provenance": "inferred (byte-diff, EXP-0001 k05_fma)",
    },
    # ---- float min/max ----------------------------------------------------
    {
        "mnemonic": "fminmax",
        "length": 6,
        "match": [(0, 8, 0x12)],
        "fields": [
            {"name": "dst",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "op",   "start": 16, "width": 8, "type": "opcode",
             "enum": {0x1e: "fminmax"}},
            {"name": "srcA", "start": 24, "width": 8, "type": "reg"},
            {"name": "sel",  "start": 32, "width": 8, "type": "enum",
             "enum": {0x00: "fmax", 0x01: "fmin"}},   # byte+4 bit0 = min/max
            {"name": "mods", "start": 40, "width": 8, "type": "mod"},
        ],
        "semantics": "d = max(a,b) (sel=0) or min(a,b) (sel=1)",
        "provenance": "inferred (byte-diff, EXP-0005 maxf/minf)",
    },
    # ---- float unary (fmov with negate/abs modifier) ----------------------
    {
        "mnemonic": "funary",
        "length": 10,
        "match": [(0, 8, 0x0b)],
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8,  "type": "raw"},
            {"name": "op",   "start": 16, "width": 8,  "type": "opcode",
             "enum": {0x0e: "fmov"}},
            {"name": "srcA", "start": 24, "width": 8,  "type": "reg"},
            {"name": "mod",  "start": 32, "width": 8,  "type": "mod"},  # 0a=neg,02=abs
            {"name": "ext",  "start": 40, "width": 40, "type": "raw"},
        ],
        "semantics": "d = mod(a)   ; unary move (neg mod=0x0a, abs mod=0x02)",
        "provenance": "inferred (byte-diff, EXP-0005 neg/absf)",
    },
    # ---- device load (structural) -----------------------------------------
    {
        "mnemonic": "device_load",
        "length": 14,
        "match": [(0, 8, 0x67)],
        "fields": [{"name": "body", "start": 8, "width": 104, "type": "raw"}],
        "semantics": "load 32-bit element from a device buffer into a register",
        "provenance": "structural (inferred, EXP-0001/EXP-0005)",
    },
    # ---- device store (structural) ----------------------------------------
    {
        "mnemonic": "device_store",
        "length": 14,
        "match": [(0, 8, 0xe7)],
        "fields": [{"name": "body", "start": 8, "width": 104, "type": "raw"}],
        "semantics": "store a register to a 32-bit device-buffer element",
        "provenance": "structural (inferred, EXP-0001/EXP-0005)",
    },
    # ---- preamble / get_sr-like (structural) ------------------------------
    {
        "mnemonic": "preamble",
        "length": 4,
        "match": [(0, 4, 0x0c)],       # low nibble == 0xC  (0x0C / 0x1C observed)
        "fields": [
            {"name": "b0hi", "start": 4,  "width": 4,  "type": "raw"},
            {"name": "body", "start": 8,  "width": 24, "type": "raw"},
        ],
        "semantics": "fixed program preamble (thread-index / setup); role TBD",
        "provenance": "structural (inferred, EXP-0001)",
    },
    # ---- stop / end -------------------------------------------------------
    {
        "mnemonic": "stop",
        "length": 4,
        "match": [(0, 8, 0x0e)],
        "fields": [{"name": "body", "start": 8, "width": 24, "type": "raw"}],
        "semantics": "program end (whole body of an empty kernel); not a strictly "
                     "enforced terminator (EXP-0003: corrupting it did not fault)",
        "provenance": "inferred (EXP-0001/EXP-0003)",
    },
]

# Index by mnemonic for the assembler.
_BY_MNEM = {d["mnemonic"]: d for d in DB}


# ------------------------------------------------------------------------------
# 3. GENERIC (table-driven) CODEC
# ------------------------------------------------------------------------------

def _int_from_bytes(b):
    return int.from_bytes(b, "little")

def _bytes_from_int(v, length):
    return v.to_bytes(length, "little")

def _get_bits(v, start, width):
    return (v >> start) & ((1 << width) - 1)

def _matches(desc, v):
    for (start, width, value) in desc["match"]:
        if _get_bits(v, start, width) != value:
            return False
    return True


def decode_one(buf, off=0):
    """Decode a single instruction at buf[off].

    Returns (record, length) where record is a dict:
      {mnemonic, op_mnemonic(if any), fields:{name:value}, length, hex,
       provenance, semantics}
    Raises ValueError if length is unknown or no descriptor matches.
    """
    length = instr_length(buf, off)
    if length is None:
        raise ValueError(f"unknown instruction length at offset {off} "
                         f"(byte0={buf[off]:#04x})")
    raw = bytes(buf[off:off + length])
    if len(raw) < length:
        raise ValueError(f"truncated instruction at offset {off} "
                         f"(need {length}, have {len(raw)})")
    v = _int_from_bytes(raw)
    # candidate descriptors: length matches AND all match-bits satisfied.
    cands = [d for d in DB if d["length"] == length and _matches(d, v)]
    if not cands:
        raise ValueError(f"no descriptor matches bytes {raw.hex()} at offset {off}")
    # Prefer the most specific match (most constrained bits).
    desc = max(cands, key=lambda d: sum(w for (_, w, _) in d["match"]))
    fields = {}
    op_mnem = None
    for f in desc["fields"]:
        val = _get_bits(v, f["start"], f["width"])
        fields[f["name"]] = val
        if f["type"] in ("opcode", "enum") and "enum" in f:
            name = f["enum"].get(val)
            if f["type"] == "opcode" and name:
                op_mnem = name
    rec = {
        "mnemonic": desc["mnemonic"],
        "op_mnemonic": op_mnem,
        "fields": fields,
        "length": length,
        "hex": raw.hex(),
        "provenance": desc["provenance"],
        "semantics": desc["semantics"],
    }
    return rec, length


def disassemble(buf):
    """Tokenize a whole byte string into a clean instruction sequence.
    Returns (records, leftover_bytes). leftover is b'' on a clean tokenization."""
    recs = []
    off = 0
    n = len(buf)
    while off < n:
        try:
            rec, length = decode_one(buf, off)
        except ValueError as e:
            # stop; report how far we got and what is left.
            rec = {"mnemonic": "<unknown>", "error": str(e),
                   "hex": bytes(buf[off:]).hex(), "length": None}
            recs.append(rec)
            return recs, bytes(buf[off:])
        recs.append(rec)
        off += length
    return recs, b""


def assemble(mnemonic, fields):
    """Assemble one instruction from a mnemonic + {field_name: value} dict.
    Returns raw bytes. Every field declared in the descriptor must be supplied
    (or defaulted to its match/const bits)."""
    if mnemonic not in _BY_MNEM:
        raise KeyError(f"unknown mnemonic {mnemonic!r}")
    desc = _BY_MNEM[mnemonic]
    length = desc["length"]
    v = 0
    # constant / match bits first
    for (start, width, value) in desc["match"]:
        v |= (value & ((1 << width) - 1)) << start
    # then the fields
    declared = {f["name"] for f in desc["fields"]}
    unknown = set(fields) - declared
    if unknown:
        raise KeyError(f"{mnemonic}: unknown field(s) {sorted(unknown)}")
    for f in desc["fields"]:
        val = fields.get(f["name"], 0)
        mask = (1 << f["width"]) - 1
        if val & ~mask:
            raise ValueError(f"{mnemonic}.{f['name']}={val:#x} exceeds width {f['width']}")
        v |= (val & mask) << f["start"]
    return _bytes_from_int(v, length)


def assemble_op(op_mnemonic, **fields):
    """Convenience: assemble a float-ALU op by its arithmetic mnemonic
    (e.g. 'fadd','fmul','fma','fmax','fmin') resolving the opcode field."""
    # search descriptors for an opcode enum containing op_mnemonic
    for desc in DB:
        for f in desc["fields"]:
            if f.get("type") in ("opcode", "enum") and op_mnemonic in (f.get("enum") or {}).values():
                opval = [k for k, val in f["enum"].items() if val == op_mnemonic][0]
                allf = dict(fields)
                allf[f["name"]] = opval
                # fill any missing declared fields with 0
                for ff in desc["fields"]:
                    allf.setdefault(ff["name"], 0)
                return assemble(desc["mnemonic"], allf)
    raise KeyError(f"no descriptor provides op {op_mnemonic!r}")


# ------------------------------------------------------------------------------
# 4. MACHINE-READABLE EXPORT
# ------------------------------------------------------------------------------

def to_json():
    """Serialize the DB (and the length rule, described) to a JSON string."""
    out = {
        "isa": "Apple A18 Pro / G17P AGX (clean-room, OWN-SHADER derived)",
        "parcel_bytes": 2,
        "length_rule": {
            "note": "first parcel does NOT encode length on G17P (fsub 09 01 1c "
                    "= 6B vs fma 09 01 1e = 8B share first parcel); length is a "
                    "function of byte0 (group) + for 0x09 a length bit at byte+2 bit1.",
            "byte0_table": {
                "0x0e": 4, "lownibble_0xC": 4, "lownibble_0x7": 14,
                "0x09": "6, or 8 if (byte[+2] & 0x02)",
                "0x0b": 10, "0x12": 6, "0x9f": "unsolved (int ALU)",
            },
        },
        "instructions": DB,
    }
    return json.dumps(out, indent=2)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(to_json())
    else:
        print(f"AGX G17P ISA DB: {len(DB)} instruction descriptors")
        hwv = [d for d in DB if d["provenance"].startswith("HW-VALIDATED")]
        print(f"  HW-VALIDATED: {len(hwv)}  -> {[d['mnemonic'] for d in hwv]}")
        for d in DB:
            print(f"  {d['mnemonic']:14s} len={d['length']:2d}  {d['provenance']}")
