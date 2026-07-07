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
    None if the leading byte is not in our (float-family) length table."""
    b0 = buf[off]
    lo = b0 & 0x0f
    if b0 == 0x0e:
        return 4                       # stop
    if lo == 0x0c:
        return 4                       # preamble / get_sr-like
    if lo == 0x07:
        return 14                      # device load (0x67) / store (0xE7)
    if b0 == 0x09:
        # float ALU: 2-source (6B) unless the fma/3-source length bit is set.
        return 8 if (buf[off + 2] & 0x02) else 6
    if b0 == 0x0b:
        return 10                      # float unary (fmov / fneg / fabs)
    if b0 == 0x12:
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

DB = [
    # ---- float 2-source ALU: fadd / fmul (the validated seed) --------------
    {
        "mnemonic": "falu2",
        "length": 6,
        "match": [(0, 8, 0x09)],       # byte0 == 0x09 identifies the float-ALU group
        "fields": [
            {"name": "dst",     "start": 8,  "width": 8, "type": "reg"},
            # --- the op-select, decomposed as validated by the EXP-0005 sweep --
            {"name": "opsel",   "start": 16, "width": 3, "type": "opcode",
             "enum": FALU2_OPSEL_ENUM},         # instr bits[16:19] = operation
            {"name": "opmod",   "start": 19, "width": 3, "type": "mod"},   # don't-care for op
            {"name": "srcmode", "start": 22, "width": 2, "type": "enum",
             "enum": {0: "normal"}},            # nonzero -> srcA-passthrough (HW-observed)
            # --------------------------------------------------------------------
            {"name": "srcA",    "start": 24, "width": 8, "type": "reg"},
            {"name": "srcB",    "start": 32, "width": 8, "type": "imm"},
            {"name": "mods",    "start": 40, "width": 8, "type": "mod"},
        ],
        # OP-SELECT BIT-FIELD (within the instruction): bits [16:19] (low 3 bits
        # of byte +2). Width = 3 bits.  0b100=fadd, 0b101=fmul (HW-VALIDATED).
        "semantics": "d = op(a, b)   ; two-source float ALU (opsel bits[16:19])",
        "provenance": "HW-VALIDATED (EXP-0003/EXP-0005): fadd=0b100 fmul=0b101 "
                      "op-select bits[16:19], full 256-value sweep",
    },
    # ---- float 3-source ALU: fma (8-byte extended form) -------------------
    {
        "mnemonic": "falu3",
        "length": 8,
        "match": [(0, 8, 0x09), (17, 1, 1)],   # byte0==0x09 AND length bit (+2,bit1)
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
