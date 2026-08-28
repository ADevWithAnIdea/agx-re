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
#   byte0            group / mnemonic          length (bytes)
#   ----------------------------------------------------------------
#   0x0e             stop / end                4
#   low nibble 0xC   preamble (get_sr-like)    4     (0x0C, 0x1C observed)
#   0x67 / 0xE7      device load / store       14
#   low nibble 0x9   float ALU (2/3 source)    6, or 8 if (byte[+2] & 0x02)
#   low nibble 0xB   float unary / int bitwise 10    (fmov/neg/abs; and/or/xor)
#   0x02             integer min/max           6
#   0x12             float min/max (6) / int compare-select (14, byte+2 lo==0xd)
#   0x9f / 0x1f      integer add/sub (2-src)   10 if (b1&1) else 12 (mul-add form)
#   0xa7             integer shift-r / bfe     10 if (b1&1) else 12
#   0x27             integer unary (popcount)  8
#
# The 0x09 length bit (byte +2, bit 1) selects the 6-byte 2-source base form
# from the 8-byte 3-source (fma) extended form.  For the integer arithmetic
# groups (0x9f/0x1f/0xa7) the analogous length selector is byte +1 bit 0:
# 1 => 10-byte 2-source form, 0 => 12-byte 3-source multiply-add / bitfield form
# (EXP-0007, HW-validated).

LEN_UNKNOWN = None


# ============================================================================
# EXP-M4-13 R9 desync trailing-word closure (ADDITIVE, per-instance guarded).
# _R9_SIGS / _R9_TRIPLES are proven-safe trailing operand/pad-word signatures: a
# (b0,b1) [or byte+2-conditioned (b0,b1,b2)] leader that is NEVER a named or
# length_only op LEADER at any clean boundary corpus-wide, so it only ever appears
# as a trailing operand / immediate / SFU-coefficient / inter-op PAD word. The
# per-instance _r9_succ_safe guard makes the 2-byte close provably non-swallowing.
# ============================================================================
_R9_SIGS = {
    (0x08, 0x02): 2,
    (0x54, 0x06): 2,
    (0x54, 0x04): 2,
    (0x54, 0x02): 2,
    (0x0f, 0x02): 2,
    (0x26, 0x10): 2,
    (0x18, 0x02): 2,
    (0x80, 0x10): 2,
    (0x64, 0x02): 2,
    (0x80, 0x0a): 2,
    (0x82, 0x04): 2,
    (0x40, 0x01): 2,
    (0x40, 0x00): 2,
    (0x26, 0x00): 2,
    (0x44, 0x21): 2,
    (0x20, 0x83): 2,
    (0xd0, 0x26): 2,
    (0x06, 0x04): 2,
    (0x1e, 0x0a): 2,
    (0x21, 0x00): 2,
    (0x68, 0x00): 2,
    (0x80, 0x16): 2,
    (0x44, 0x01): 2,
    (0x54, 0x0c): 2,
    (0x54, 0x0a): 2,
    (0x06, 0xfc): 2,
    (0x64, 0x0d): 2,
    (0x08, 0x00): 2,
    (0xf2, 0x0a): 2,
    (0x15, 0x05): 2,
    (0x20, 0x6c): 2,
    (0x14, 0x00): 2,
    (0x94, 0x01): 2,
    (0x61, 0x00): 2,
    (0x54, 0x0f): 2,
    (0xf0, 0xc0): 2,
    (0x08, 0x23): 2,
    (0x1e, 0x08): 2,
    (0x21, 0xb0): 2,
    (0x40, 0x1b): 2,
    (0x80, 0x12): 2,
    (0xb2, 0xba): 2,
    (0x01, 0x08): 2,
    (0x4f, 0x00): 2,
    (0xe0, 0xc0): 2,
    (0x15, 0x02): 2,
    (0x34, 0x01): 2,
    (0x54, 0x4a): 2,
    (0x54, 0x0e): 2,
    (0x64, 0x01): 2,
    (0x54, 0x12): 2,
    (0x82, 0x14): 2,
    (0x54, 0x10): 2,
    (0xa2, 0x56): 2,
    (0xe2, 0xba): 2,
    (0x82, 0xba): 2,
    (0x30, 0x06): 2,
    (0xf2, 0x0c): 2,
    (0x20, 0x04): 2,
    (0x51, 0x01): 2,
    (0x40, 0xa0): 2,
    (0x84, 0x00): 2,
    (0x08, 0x03): 2,
    (0x80, 0x14): 2,
    (0xe2, 0xc1): 2,
    (0x80, 0x3a): 2,
    (0x88, 0x63): 2,
    (0x0d, 0x00): 2,
    (0x40, 0x11): 2,
    (0x2e, 0x60): 2,
    (0x3e, 0x54): 2,
    (0x46, 0x00): 2,
    (0x46, 0x64): 2,
    (0x80, 0x1a): 2,
    (0x06, 0x20): 2,
    (0x20, 0x10): 2,
    (0x88, 0x02): 2,
    (0x0c, 0xea): 2,
    (0x48, 0x83): 2,
    (0xd2, 0x08): 2,
    (0xbd, 0x4b): 2,
    (0x80, 0x4a): 2,
    (0x54, 0x4c): 2,
    (0xbf, 0x4f): 2,
    (0xbd, 0x51): 2,
    (0x80, 0x48): 2,
    (0x06, 0x00): 2,
    (0x80, 0x18): 2,
    (0x80, 0x56): 2,
    (0x80, 0x36): 2,
    (0x80, 0x2e): 2,
    (0xa0, 0x00): 2,
    (0x54, 0x36): 2,
    (0x4f, 0xbf): 2,
    (0x56, 0x20): 2,
    (0x0f, 0xc2): 2,
    (0x54, 0x1a): 2,
    (0x48, 0xa3): 2,
    (0x88, 0x83): 2,
    (0x20, 0x88): 2,
    (0x80, 0x1e): 2,
    (0xb2, 0x52): 2,
    (0xd2, 0xbf): 2,
    (0xd2, 0x45): 2,
    (0xe2, 0x0a): 2,
    (0x20, 0x6e): 2,
    (0xe2, 0x3b): 2,
    (0x80, 0x50): 2,
    (0xbd, 0x4d): 2,
    (0x80, 0x44): 2,
    (0x44, 0x00): 2,
    (0x42, 0xba): 2,
    (0xc4, 0x01): 2,
    (0xc2, 0x54): 2,
    (0xe2, 0x56): 2,
    (0xbd, 0x53): 2,
    (0x06, 0x08): 2,
    (0xe2, 0x88): 2,
    (0x80, 0x42): 2,
    (0x48, 0x09): 2,
    (0x15, 0x00): 2,
    (0x40, 0x08): 2,
    (0x20, 0x12): 2,
    (0x54, 0x26): 2,
    (0x92, 0x5c): 2,
    (0x25, 0x83): 2,
    (0xd0, 0x2f): 2,
    (0xa2, 0x5e): 2,
    (0x74, 0x01): 2,
    (0x32, 0x1e): 2,
    (0x80, 0x20): 2,
    (0x54, 0x05): 2,
    (0xc0, 0x80): 2,
    (0xa0, 0x20): 2,
    (0x50, 0x0a): 2,
    (0x4d, 0x00): 2,
    (0x88, 0x23): 2,
    (0x31, 0x06): 2,
    (0x1d, 0x00): 2,
    (0x54, 0x21): 2,
    (0x54, 0x42): 2,
    (0x54, 0x38): 2,
    (0x1e, 0x02): 2,
    (0xb2, 0x4a): 2,
    (0x32, 0xcb): 2,
    (0xbf, 0x49): 2,
    (0x54, 0x18): 2,
    (0x80, 0x46): 2,
    (0xbf, 0x47): 2,
    (0xd0, 0x12): 2,
    (0xf2, 0x52): 2,
    (0x42, 0x49): 2,
    (0xc2, 0xcb): 2,
    (0x62, 0xd1): 2,
    (0x80, 0x4e): 2,
    (0xa1, 0xb0): 2,
    (0x81, 0x10): 2,
    (0x38, 0x0a): 2,
    (0x40, 0x80): 2,
    (0x80, 0x22): 2,
    (0xc0, 0x11): 2,
    (0x54, 0x08): 2,
    (0x32, 0x28): 2,
    (0x15, 0x04): 2,
    (0xc2, 0x5c): 2,
    (0x65, 0x91): 2,
    (0x80, 0x34): 2,
    (0x54, 0x44): 2,
    (0xbd, 0x49): 2,
    (0x86, 0x32): 2,
    (0x92, 0x1e): 2,
    (0x72, 0xad): 2,
    (0x54, 0x22): 2,
    (0x81, 0x00): 2,
    (0xa0, 0x0a): 2,
    (0x20, 0x2a): 2,
    (0x70, 0x0e): 2,
    (0x21, 0x0c): 2,
    (0x21, 0x1a): 2,
    (0x21, 0x22): 2,
    (0x4e, 0x0e): 2,
    (0x54, 0x24): 2,
    (0x54, 0x2a): 2,
    (0xa0, 0x10): 2,
    (0xa0, 0x0e): 2,
    (0x9d, 0x00): 2,
    (0x80, 0xc8): 2,
    (0x86, 0x02): 2,
    (0xa0, 0x04): 2,
    (0x54, 0xbe): 2,
    (0x08, 0xa3): 2,
    (0x08, 0x43): 2,
    (0x48, 0x03): 2,
    (0xc8, 0x23): 2,
    (0x80, 0x01): 2,
    (0xf0, 0x10): 2,
    (0xc0, 0x00): 2,
    (0x21, 0x06): 2,
    (0x20, 0xa0): 2,
    (0x81, 0x08): 2,
    (0x54, 0x46): 2,
    (0x02, 0x41): 2,
    (0xc2, 0x02): 2,
    (0x40, 0x4c): 2,
    (0x42, 0x4c): 2,
    (0x48, 0x00): 2,
    (0x92, 0x06): 2,
    (0xd2, 0x0b): 2,
    (0xf2, 0x40): 2,
    (0xd2, 0x52): 2,
    (0x92, 0xc5): 2,
    (0xe2, 0x40): 2,
    (0xc2, 0x0b): 2,
    (0xc2, 0xbd): 2,
    (0xd2, 0x43): 2,
    (0xb2, 0x0a): 2,
    (0xc2, 0x4e): 2,
    (0x54, 0x48): 2,
    (0x02, 0xc5): 2,
    (0xbd, 0x47): 2,
    (0xa2, 0x4a): 2,
    (0x36, 0x44): 2,
    (0x52, 0x2b): 2,
    (0xb4, 0x57): 2,
    (0x92, 0x14): 2,
    (0xc2, 0x5a): 2,
    (0x32, 0x14): 2,
    (0x42, 0x14): 2,
    (0x32, 0x20): 2,
    (0x52, 0xcf): 2,
    (0xbd, 0x4f): 2,
    (0x80, 0x54): 2,
    (0x44, 0x54): 2,
    (0x42, 0x10): 2,
    (0x80, 0x58): 2,
    (0x80, 0x4c): 2,
    (0xb2, 0x0c): 2,
    (0x54, 0x50): 2,
    (0x54, 0x4e): 2,
    (0x80, 0x32): 2,
    (0x80, 0x3e): 2,
    (0xb2, 0x88): 2,
    (0x02, 0x21): 2,
    (0xa2, 0xba): 2,
    (0x18, 0x04): 2,
    (0xf2, 0x4e): 2,
    (0xf2, 0x5a): 2,
    (0xf2, 0x54): 2,
    (0x02, 0x36): 2,
    (0x44, 0x60): 2,
    (0x52, 0x52): 2,
    (0x80, 0x3c): 2,
    (0x81, 0x0c): 2,
    (0x61, 0x0f): 2,
    (0x14, 0x22): 2,
    (0x45, 0xc2): 2,
    (0x80, 0x1c): 2,
    (0x38, 0x04): 2,
    (0x26, 0x81): 2,
    (0x20, 0x02): 2,
    (0x82, 0x1c): 2,
    (0x21, 0xa0): 2,
    (0x42, 0x2c): 2,
    (0x80, 0x6e): 2,
    (0xbd, 0x5d): 2,
    (0x44, 0x5e): 2,
    (0x54, 0x52): 2,
    (0xb4, 0x5f): 2,
    (0x80, 0x52): 2,
    (0x44, 0x10): 2,
    (0x41, 0x08): 2,
    (0x80, 0x40): 2,
    (0x82, 0x46): 2,
    (0x38, 0x54): 2,
    (0xd2, 0x20): 2,
    (0xbf, 0x5b): 2,
    (0x50, 0x78): 2,
    (0x4e, 0x64): 2,
    (0x54, 0x20): 2,
    (0x80, 0x2c): 2,
    (0x80, 0x38): 2,
    (0x81, 0x06): 2,
    (0x80, 0x64): 2,
    (0x80, 0x5e): 2,
    (0x45, 0x00): 2,
    (0x21, 0x12): 2,
    (0x21, 0x0e): 2,
    (0x24, 0x83): 2,
    (0x21, 0x1c): 2,
    (0x21, 0x2a): 2,
    (0x20, 0x87): 2,
    (0x24, 0x8d): 2,
    (0x21, 0x30): 2,
    (0x25, 0x27): 2,
    (0x40, 0x60): 2,
    (0x40, 0x40): 2,
    (0xc0, 0x02): 2,
    (0x24, 0x87): 2,
    (0x2e, 0x83): 2,
    (0x21, 0x26): 2,
    (0x42, 0x26): 2,
    (0x72, 0x42): 2,
    (0x5d, 0x01): 2,
    (0x30, 0x02): 2,
    (0x40, 0x02): 2,
    (0x28, 0x02): 2,
    (0x50, 0x02): 2,
    (0x34, 0x00): 2,
    (0x0d, 0x08): 2,
    (0x86, 0x01): 2,
    (0xa0, 0x28): 2,
    (0x74, 0x05): 2,
    (0x54, 0x1e): 2,
    (0xff, 0x0f): 2,
    (0x62, 0x2d): 2,
    (0x58, 0x0b): 2,
    (0x68, 0x0d): 2,
    (0x54, 0x7c): 2,
    (0x54, 0x66): 2,
    (0x70, 0x28): 2,
    (0x26, 0x02): 2,
    (0x66, 0x8d): 2,
    (0x20, 0x0c): 2,
    (0x48, 0x23): 2,
    (0x26, 0x80): 2,
    (0x40, 0x81): 2,
    (0x80, 0x80): 2,
    (0xc0, 0x01): 2,
    (0x86, 0x09): 2,
    (0x24, 0x05): 2,
    (0x24, 0x07): 2,
    (0x24, 0x09): 2,
    (0x24, 0x0b): 2,
    (0x24, 0x0d): 2,
    (0x24, 0x0f): 2,
    (0x20, 0x86): 2,
    (0x20, 0x84): 2,
    (0x08, 0x93): 2,
    (0xf0, 0x11): 2,
    (0x26, 0x91): 2,
    (0x21, 0xa1): 2,
    (0x28, 0x81): 2,
    (0x02, 0xa0): 2,
    (0x34, 0x57): 2,
    (0x62, 0x4e): 2,
    (0xa2, 0x50): 2,
    (0x01, 0x8c): 2,
    (0x64, 0x05): 2,
    (0x52, 0xc7): 2,
    (0xb4, 0x51): 2,
    (0x72, 0xcb): 2,
    (0xb2, 0x4c): 2,
    (0x7f, 0xff): 2,
    (0xb2, 0x58): 2,
    (0x26, 0x76): 2,
    (0x32, 0x22): 2,
    (0x52, 0x40): 2,
    (0xf2, 0x24): 2,
    (0xb2, 0x37): 2,
    (0x42, 0x22): 2,
    (0xd2, 0x22): 2,
    (0xd2, 0x3c): 2,
    (0xd2, 0x3b): 2,
    (0xc2, 0x39): 2,
    (0xc2, 0x48): 2,
    (0xb2, 0xc4): 2,
    (0xb2, 0x12): 2,
    (0xe2, 0x3d): 2,
    (0x62, 0xbf): 2,
    (0x32, 0x10): 2,
    (0x02, 0x4a): 2,
    (0xc8, 0xa8): 2,
    (0xf2, 0x47): 2,
    (0xd2, 0x42): 2,
    (0x54, 0x3c): 2,
    (0x86, 0x30): 2,
    (0xf2, 0x16): 2,
    (0x34, 0x2f): 2,
    (0x74, 0x5f): 2,
    (0x25, 0xd5): 2,
    (0x25, 0xd7): 2,
    (0xe8, 0xa8): 2,
    (0x02, 0x54): 2,
    (0x52, 0x43): 2,
    (0x72, 0xcd): 2,
    (0x42, 0xcb): 2,
    (0x92, 0xcf): 2,
    (0x52, 0x4c): 2,
    (0x52, 0x4e): 2,
    (0x26, 0x11): 2,
    (0x02, 0x92): 2,
    (0xbf, 0x4b): 2,
    (0x42, 0x50): 2,
    (0xe2, 0x50): 2,
    (0xe2, 0xcf): 2,
    (0x72, 0xd3): 2,
    (0xbd, 0x55): 2,
    (0x32, 0x25): 2,
    (0xd0, 0x24): 2,
    (0x06, 0x2c): 2,
    (0xa2, 0x37): 2,
    (0x42, 0x37): 2,
    (0x28, 0x8b): 2,
    (0x30, 0x0a): 2,
    (0xf2, 0x4c): 2,
    (0x82, 0x52): 2,
    (0xf2, 0x58): 2,
    (0xbf, 0x4d): 2,
    (0x52, 0x24): 2,
    (0xe2, 0x36): 2,
    (0xe2, 0x10): 2,
    (0xbf, 0x45): 2,
    (0xa0, 0x06): 2,
    (0x8e, 0x60): 2,
    (0x0f, 0x0f): 2,
    (0x26, 0x05): 2,
    (0x71, 0x11): 2,
    (0x61, 0x0d): 2,
    (0x0f, 0x0e): 2,
    (0xd2, 0x0f): 2,
    (0x20, 0xa3): 2,
    (0x28, 0xa1): 2,
    (0x41, 0x0b): 2,
    (0x01, 0x0b): 2,
    (0x24, 0x08): 2,
    (0x24, 0x11): 2,
    (0x45, 0x62): 2,
    (0x58, 0x0f): 2,
    (0x50, 0x0e): 2,
    (0x15, 0x03): 2,
    (0x61, 0x05): 2,
    (0x42, 0xc2): 2,
    (0x8e, 0x48): 2,
    (0x28, 0x08): 2,
    (0x81, 0x11): 2,
    (0x26, 0x8c): 2,
    (0x71, 0x0d): 2,
    (0x21, 0x09): 2,
    (0x21, 0x85): 2,
    (0x21, 0x1e): 2,
    (0x80, 0x09): 2,
    (0x80, 0x05): 2,
    (0x48, 0x98): 2,
    (0x08, 0x94): 2,
    (0x28, 0x18): 2,
    (0xc0, 0x10): 2,
    (0x70, 0xb0): 2,
    (0x24, 0x88): 2,
    (0x0f, 0x0a): 2,
    (0x1d, 0x02): 2,
    (0x34, 0x08): 2,
    (0x91, 0x13): 2,
    (0x0f, 0x0c): 2,
    (0x3d, 0x05): 2,
    (0x68, 0x06): 2,
    (0x30, 0x07): 2,
    (0x18, 0x08): 2,
    (0x50, 0x81): 2,
    (0x28, 0x82): 2,
    (0x3d, 0x0c): 2,
    (0x0b, 0x97): 2,
    (0x66, 0x00): 2,
    (0x15, 0xa0): 2,
    (0x14, 0x07): 2,
    (0xd0, 0x2b): 2,
    (0x1d, 0x01): 2,
    (0x82, 0x2e): 2,
    (0x82, 0x2c): 2,
    (0x82, 0x26): 2,
    (0x82, 0x1a): 2,
    (0x40, 0x15): 2,
    (0x28, 0x40): 2,
    (0x34, 0x02): 2,
    (0x14, 0x04): 2,
    (0x78, 0xa8): 2,
    (0x54, 0x28): 2,
    (0x72, 0x00): 2,
    (0x70, 0xa8): 2,
    (0x80, 0x6c): 2,
    (0x80, 0x78): 2,
    (0x80, 0x7c): 2,
    (0xf2, 0xdb): 2,
    (0xbd, 0x2b): 2,
    (0xb2, 0x3a): 2,
    (0xc2, 0x0a): 2,
    (0x54, 0x58): 2,
    (0x24, 0x00): 2,
    (0xe2, 0x3a): 2,
    (0x34, 0x37): 2,
    (0x74, 0x61): 2,
    (0x72, 0x4f): 2,
    (0xa2, 0xd7): 2,
    (0xd2, 0xd9): 2,
    (0xbf, 0x59): 2,
    (0xbf, 0x51): 2,
    (0x92, 0x5a): 2,
    (0xd2, 0x06): 2,
    (0xa2, 0x0e): 2,
    (0x80, 0xa8): 2,
    (0xc2, 0xd5): 2,
    (0x72, 0x08): 2,
    (0x54, 0x54): 2,
    (0x92, 0x08): 2,
    (0x02, 0xbf): 2,
    (0xb4, 0x4f): 2,
    (0xa5, 0x91): 2,
    (0xa0, 0x01): 2,
    (0xf2, 0x07): 2,
    (0xf2, 0x06): 2,
    (0xc2, 0xb7): 2,
    (0x74, 0x3f): 2,
    (0xe2, 0xb9): 2,
    (0x74, 0x49): 2,
    (0xe2, 0xbb): 2,
    (0xc2, 0x06): 2,
    (0xb2, 0x06): 2,
    (0xe0, 0xa8): 2,
    (0xa2, 0x3e): 2,
    (0xa2, 0x44): 2,
    (0x72, 0xc1): 2,
    (0xbd, 0x3f): 2,
    (0xb2, 0x30): 2,
    (0xa2, 0xc7): 2,
    (0xbd, 0x45): 2,
    (0x86, 0x36): 2,
    (0xb2, 0x22): 2,
    (0xc2, 0xdd): 2,
    (0x80, 0x62): 2,
    (0xb2, 0x24): 2,
    (0xc2, 0x10): 2,
    (0xb2, 0x10): 2,
    (0x1b, 0xe1): 2,
    (0xf2, 0x18): 2,
    (0xa2, 0x55): 2,
    (0x54, 0x56): 2,
    (0x92, 0xdb): 2,
    (0xbd, 0x59): 2,
    (0xd2, 0xdf): 2,
    (0xbd, 0x5f): 2,
    (0xbd, 0x61): 2,
    (0xd2, 0x2c): 2,
    (0x0f, 0x22): 2,
    (0x06, 0x60): 2,
    (0x62, 0x36): 2,
    (0x62, 0x2e): 2,
    (0x80, 0x70): 2,
    (0x6b, 0xa3): 2,
    (0x02, 0xa5): 2,
    (0x7d, 0x2b): 2,
    (0x32, 0x2a): 2,
    (0x07, 0x08): 2,
    (0x01, 0x9e): 2,
    (0x81, 0x34): 2,
    (0x02, 0x28): 2,
    (0x02, 0xa8): 2,
    (0x80, 0x5c): 2,
    (0x81, 0x1a): 2,
    (0x80, 0x2a): 2,
    (0xd8, 0x0a): 2,
    (0x3e, 0x14): 2,
    (0x80, 0x28): 2,
    (0x61, 0x64): 2,
    (0x65, 0x02): 2,
    (0x25, 0x04): 2,
    (0x90, 0x4a): 2,
    (0x25, 0x00): 2,
    (0x2d, 0xc0): 2,
    (0x90, 0x00): 2,
    (0x55, 0xc2): 2,
    (0x8e, 0x20): 2,
    (0x21, 0x16): 2,
    (0x21, 0x14): 2,
    (0x21, 0x34): 2,
    (0x21, 0x0a): 2,
    (0x20, 0x1e): 2,
    (0x40, 0x12): 2,
    (0x06, 0x88): 2,
    (0x21, 0x24): 2,
    (0x15, 0x01): 2,
    (0x01, 0x84): 2,
    (0x20, 0x40): 2,
    (0x24, 0x19): 2,
    (0x86, 0x06): 2,
    (0xe2, 0x11): 2,
    (0xd2, 0x17): 2,
    (0x25, 0x4d): 2,
    (0x26, 0x1d): 2,
    (0x20, 0x8d): 2,
    (0x01, 0x88): 2,
    (0x21, 0x28): 2,
    (0x24, 0x91): 2,
    (0x32, 0xa3): 2,
    (0x32, 0xa5): 2,
    (0x24, 0x99): 2,
    (0x32, 0x9d): 2,
    (0x64, 0x9d): 2,
    (0x61, 0xa3): 2,
    (0x6d, 0xa3): 2,
    (0x6e, 0x9d): 2,
    (0x25, 0x25): 2,
    (0xb2, 0x2b): 2,
    (0xa2, 0x23): 2,
    (0x92, 0x05): 2,
    (0x94, 0x00): 2,
    (0x44, 0x87): 2,
    (0x74, 0x06): 2,
    (0xf4, 0x01): 2,
    (0xd2, 0x8d): 2,
    (0xd2, 0xb1): 2,
    (0xe2, 0xb3): 2,
    (0x70, 0x40): 2,
    (0xc0, 0x22): 2,
    (0x44, 0x0f): 2,
    (0x01, 0x8e): 2,
    (0x41, 0x05): 2,
    (0x2e, 0x13): 2,
    (0xdd, 0x00): 2,
    (0x54, 0x30): 2,
    (0x85, 0x02): 2,
    (0x35, 0x0f): 2,
    (0x2e, 0x0d): 2,
    (0x2e, 0x0a): 2,
    (0x96, 0x08): 2,
    (0x86, 0x21): 2,
    (0x92, 0x21): 2,
    (0xc2, 0x03): 2,
    (0x32, 0x87): 2,
    (0x82, 0x15): 2,
    (0x06, 0x40): 2,
    (0x54, 0x5a): 2,
    (0x20, 0x2e): 2,
    (0x20, 0x1c): 2,
    (0x84, 0x01): 2,
    (0x07, 0x81): 2,
    (0xe0, 0x00): 2,
    (0xa2, 0x01): 2,
    (0x21, 0x2e): 2,
    (0xff, 0x00): 2,
    (0x25, 0x09): 2,
    (0x56, 0x00): 2,
    (0x24, 0x01): 2,
    (0x35, 0x11): 2,
    (0x86, 0x1e): 2,
    (0x52, 0x2d): 2,
    (0x25, 0xa4): 2,
    (0x1d, 0xa0): 2,
    (0x06, 0x86): 2,
    (0x14, 0x14): 2,
    (0x21, 0x83): 2,
    (0x21, 0x01): 2,
    (0x82, 0x31): 2,
    (0x02, 0x27): 2,
    (0x01, 0x60): 2,
    (0x14, 0x01): 2,
    (0xff, 0x0b): 2,
    (0x78, 0x0f): 2,
    (0x54, 0x86): 2,
    (0x54, 0xa0): 2,
    (0x54, 0x64): 2,
    (0x54, 0x6e): 2,
    (0x54, 0x76): 2,
    (0x54, 0x6c): 2,
    (0x54, 0x74): 2,
    (0x92, 0x29): 2,
    (0x4d, 0x40): 2,
    (0x51, 0x00): 2,
    (0x54, 0x16): 2,
    (0x0d, 0x01): 2,
    (0xa2, 0xab): 2,
    (0x6d, 0x1d): 2,
    (0x78, 0x2d): 2,
    (0x68, 0x88): 2,
    (0x44, 0x44): 2,
    (0x36, 0x0c): 2,
    (0xd2, 0x27): 2,
    (0x2d, 0x27): 2,
    (0x52, 0xa3): 2,
    (0x80, 0x24): 2,
    (0x86, 0x22): 2,
    (0x20, 0x26): 2,
    (0x7d, 0xb0): 2,
    (0x94, 0x6c): 2,
    (0x95, 0xd0): 2,
    (0x55, 0xc0): 2,
    (0x4d, 0xa2): 2,
    (0x35, 0xa0): 2,
    (0x45, 0xd0): 2,
    (0x3d, 0xa0): 2,
    (0x35, 0xe0): 2,
    (0x2d, 0xe2): 2,
    (0x1d, 0x60): 2,
    (0x91, 0x14): 2,
    (0xb1, 0x08): 2,
    (0x21, 0x8a): 2,
    (0xc0, 0x81): 2,
    (0x21, 0xc1): 2,
    (0x71, 0x09): 2,
    (0x61, 0x80): 2,
    (0x41, 0x80): 2,
    (0x61, 0x84): 2,
    (0x86, 0x08): 2,
    (0x1e, 0x04): 2,
    (0x86, 0x04): 2,
    (0xff, 0xff): 2,
    (0xc1, 0x95): 2,
    (0x91, 0x8d): 2,
    (0x1e, 0x2b): 2,
    (0xa2, 0x35): 2,
    (0xa2, 0x34): 2,
    (0x80, 0x03): 2,
    (0x52, 0xc9): 2,
    (0x82, 0x03): 2,
    (0xc2, 0x50): 2,
    (0xea, 0x20): 2,
    (0xa2, 0x82): 2,
    (0x44, 0x03): 2,
    (0xa2, 0x02): 2,
    (0x40, 0x0b): 2,
    (0x2d, 0x79): 2,
    (0xa6, 0x00): 2,
    (0xd2, 0x0d): 2,
    (0x62, 0x3b): 2,
    (0x02, 0x39): 2,
    (0xd2, 0x0a): 2,
    (0xc2, 0x52): 2,
    (0xd2, 0xa2): 2,
    (0xc2, 0xa2): 2,
    (0x32, 0x51): 2,
    (0x1a, 0x99): 2,
    (0x1a, 0x45): 2,
    (0x40, 0xa8): 2,
    (0x26, 0x7c): 2,
    (0xc2, 0x22): 2,
    (0xda, 0x39): 2,
    (0x52, 0x3b): 2,
    (0x1e, 0x07): 2,
    (0xd2, 0x38): 2,
    (0x62, 0xcb): 2,
    (0xd2, 0xc4): 2,
    (0x1a, 0xcb): 2,
    (0x02, 0x1c): 2,
    (0x52, 0x47): 2,
    (0xba, 0x35): 2,
    (0x02, 0x4b): 2,
    (0x1a, 0x91): 2,
    (0xf2, 0x3f): 2,
    (0xf2, 0x10): 2,
    (0x54, 0x40): 2,
    (0x1a, 0xbf): 2,
    (0x1a, 0x43): 2,
    (0x41, 0x01): 2,
    (0x1a, 0xc9): 2,
    (0x02, 0x50): 2,
    (0x02, 0x3f): 2,
    (0xf2, 0x3b): 2,
    (0x54, 0x14): 2,
    (0x02, 0xb9): 2,
    (0x62, 0x70): 2,
    (0x42, 0x70): 2,
    (0xea, 0x39): 2,
    (0x42, 0x52): 2,
    (0x32, 0x00): 2,
    (0x82, 0x90): 2,
    (0xad, 0x7d): 2,
    (0x92, 0x92): 2,
    (0x62, 0x55): 2,
    (0x1a, 0x93): 2,
    (0x02, 0x26): 2,
    (0x82, 0x59): 2,
    (0x28, 0x88): 2,
    (0x30, 0x00): 2,
    (0x02, 0x13): 2,
    (0xd8, 0x00): 2,
    (0x86, 0x4a): 2,
    (0x86, 0x2a): 2,
    (0x58, 0x00): 2,
    (0xf0, 0x00): 2,
    (0x86, 0x44): 2,
    (0xa8, 0x00): 2,
    (0x20, 0x07): 2,
    (0x18, 0xc0): 2,
    (0x08, 0x05): 2,
    (0x30, 0x83): 2,
    (0x52, 0x55): 2,
    (0x54, 0x0b): 2,
    (0xe0, 0x11): 2,
    (0x62, 0x57): 2,
    (0xba, 0x0f): 2,
    (0xba, 0x4d): 2,
    (0x3a, 0xd1): 2,
    (0xa2, 0xd2): 2,
    (0xa2, 0x22): 2,
    (0xa2, 0xa2): 2,
    (0x08, 0xa9): 2,
    (0x1a, 0x47): 2,
    (0x21, 0x82): 2,
    (0x36, 0x21): 2,
    (0x0f, 0x0d): 2,
    (0x0f, 0x81): 2,
    (0x81, 0x0e): 2,
    (0x71, 0x0b): 2,
    (0x21, 0xb1): 2,
    (0x41, 0x87): 2,
    (0x3f, 0xff): 2,
    (0x61, 0x15): 2,
    (0xa0, 0x05): 2,
    (0xa0, 0x03): 2,
    (0x06, 0x90): 2,
    (0x8d, 0x08): 2,
    (0x38, 0x0d): 2,
    (0x38, 0x00): 2,
    (0x51, 0x81): 2,
    (0x51, 0x83): 2,
    (0x41, 0x81): 2,
    (0x01, 0x90): 2,
    (0x20, 0x05): 2,
    (0x31, 0x83): 2,
    (0x40, 0x09): 2,
    (0x20, 0x85): 2,
    (0x18, 0x81): 2,
    (0x41, 0x09): 2,
    (0x31, 0xa1): 2,
    (0x61, 0x98): 2,
    (0x25, 0x81): 2,
    (0xa8, 0x91): 2,
    (0x68, 0x9d): 2,
    (0x28, 0x1d): 2,
    (0x30, 0x8e): 2,
    (0x52, 0x90): 2,
    (0x0f, 0x08): 2,
    (0x40, 0x05): 2,
    (0x20, 0x08): 2,
    (0x20, 0xb3): 2,
    (0x38, 0x08): 2,
    (0x68, 0x12): 2,
    (0x07, 0x0a): 2,
    (0x40, 0x87): 2,
    (0x50, 0x80): 2,
    (0x08, 0x40): 2,
    (0x18, 0xa0): 2,
    (0x08, 0xa0): 2,
    (0x26, 0x07): 2,
    (0x31, 0x2f): 2,
    (0x61, 0x1d): 2,
    (0xa2, 0x0d): 2,
    (0x21, 0x20): 2,
    (0x32, 0x19): 2,
    (0xaa, 0x53): 2,
    (0xb2, 0x57): 2,
    (0x30, 0x88): 2,
    (0xda, 0x57): 2,
    (0x1a, 0xa1): 2,
    (0x4a, 0x47): 2,
    (0x3a, 0x53): 2,
    (0x92, 0x53): 2,
    (0x0b, 0xcd): 2,
    (0xc2, 0x51): 2,
    (0xf2, 0x5b): 2,
    (0x54, 0x3e): 2,
    (0x72, 0x37): 2,
    (0x82, 0x19): 2,
    (0xa2, 0x46): 2,
    (0x92, 0xbe): 2,
    (0xca, 0x3e): 2,
    (0xa2, 0x1e): 2,
    (0x34, 0x45): 2,
    (0xb2, 0x20): 2,
    (0x8a, 0xc1): 2,
    (0x42, 0x51): 2,
    (0x1a, 0xc7): 2,
    (0xb2, 0x92): 2,
    (0x54, 0x2e): 2,
    (0xfa, 0xff): 2,
    (0x1b, 0xcf): 2,
    (0x5a, 0x49): 2,
    (0xc2, 0x63): 2,
    (0x6a, 0x57): 2,
    (0xb2, 0x2c): 2,
    (0x54, 0x5e): 2,
    (0xb2, 0x40): 2,
    (0x26, 0x7e): 2,
    (0x54, 0x60): 2,
    (0x42, 0x27): 2,
    (0x54, 0x5c): 2,
    (0x4a, 0x17): 2,
    (0x8a, 0x43): 2,
    (0xc2, 0x59): 2,
    (0x6a, 0x13): 2,
    (0x48, 0x89): 2,
    (0x6a, 0x5b): 2,
    (0x6a, 0x17): 2,
    (0xe2, 0x91): 2,
    (0xb2, 0x21): 2,
    (0x2b, 0xc0): 2,
    (0xfa, 0x5d): 2,
    (0x02, 0x23): 2,
    (0x48, 0x88): 2,
    (0x20, 0x68): 2,
    (0x3f, 0x08): 2,
    (0xd0, 0x22): 2,
    (0x08, 0x88): 2,
    (0x18, 0x88): 2,
    (0xa2, 0x92): 2,
    (0x62, 0x92): 2,
    (0x81, 0x20): 2,
    (0x81, 0x0a): 2,
    (0x81, 0x2c): 2,
    (0x81, 0x26): 2,
    (0x81, 0x12): 2,
    (0x81, 0x14): 2,
    (0x41, 0x97): 2,
    (0x68, 0x10): 2,
    (0xa1, 0x39): 2,
    (0x61, 0x81): 2,
    (0x61, 0x83): 2,
    (0x01, 0x89): 2,
    (0x50, 0x0f): 2,
    (0x20, 0x09): 2,
    (0x08, 0x04): 2,
    (0xa8, 0x8c): 2,
    (0x08, 0x08): 2,
    (0x21, 0x40): 2,
    (0x3e, 0x21): 2,
    (0x2d, 0x13): 2,
    (0x21, 0x3c): 2,
    (0x3e, 0x1f): 2,
    (0x01, 0x94): 2,
    (0x18, 0x8c): 2,
    (0x3e, 0x07): 2,
    (0x84, 0x0a): 2,
    (0x91, 0x06): 2,
    (0xc2, 0x2d): 2,
    (0xb2, 0x25): 2,
    (0x07, 0x8a): 2,
    (0x54, 0x1c): 2,
    (0x0a, 0x73): 2,
    (0x1e, 0x00): 2,
    (0x1e, 0x0c): 2,
    (0x62, 0xbc): 2,
    (0x84, 0x06): 2,
    (0x26, 0x0b): 2,
    (0x30, 0x03): 2,
    (0x5d, 0x00): 2,
    (0x7b, 0x7a): 2,
    (0x2a, 0x80): 2,
    (0xb2, 0x84): 2,
    (0xaa, 0x86): 2,
    (0xa2, 0x84): 2,
    (0x38, 0x33): 2,
    (0x38, 0x30): 2,
    (0x38, 0x2e): 2,
    (0x38, 0x2c): 2,
    (0x38, 0x2a): 2,
    (0x38, 0x28): 2,
    (0x38, 0x24): 2,
    (0x38, 0x25): 2,
    (0x38, 0x22): 2,
    (0x38, 0x20): 2,
    (0x38, 0x1f): 2,
    (0x38, 0x1b): 2,
    (0x38, 0x19): 2,
    (0x38, 0x17): 2,
    (0x38, 0x15): 2,
    (0x38, 0x13): 2,
    (0x38, 0x11): 2,
    (0x38, 0x0f): 2,
    (0x38, 0x0c): 2,
    (0x4a, 0x86): 2,
    (0x7a, 0x86): 2,
    (0x25, 0x8c): 2,
    (0x25, 0x98): 2,
    (0x86, 0x1c): 2,
    (0x02, 0x30): 2,
    (0x28, 0x8c): 2,
    (0x52, 0x27): 2,
    (0x26, 0x9b): 2,
    (0x81, 0x3e): 2,
    (0x06, 0x0c): 2,
    (0x86, 0x0a): 2,
    (0x61, 0x03): 2,
    (0x35, 0x17): 2,
    (0x82, 0xad): 2,
    (0x85, 0x30): 2,
    (0x62, 0xb1): 2,
    (0x45, 0x02): 2,
    (0x2e, 0x91): 2,
    (0x72, 0x2f): 2,
    (0x6a, 0xab): 2,
    (0x7a, 0xab): 2,
    (0x7a, 0x95): 2,
    (0x6a, 0xa9): 2,
    (0x18, 0x15): 2,
    (0x42, 0xc8): 2,
    (0xf2, 0xca): 2,
    (0xa2, 0xa9): 2,
    (0xb2, 0xa9): 2,
    (0x28, 0x00): 2,
    (0x01, 0x0e): 2,
    (0x8d, 0x00): 2,
    (0xcd, 0x00): 2,
    (0x66, 0x0d): 2,
    (0x44, 0x3c): 2,
    (0xca, 0x39): 2,
    (0x4a, 0x42): 2,
    (0x44, 0x3e): 2,
    (0xda, 0x3b): 2,
    (0x64, 0xc3): 2,
    (0x44, 0x40): 2,
    (0xea, 0x3d): 2,
    (0xfa, 0x3f): 2,
    (0x72, 0xa7): 2,
    (0x62, 0xa7): 2,
    (0x66, 0x23): 2,
    (0x91, 0x12): 2,
    (0x41, 0x12): 2,
    (0xa1, 0x12): 2
}
_R9_TRIPLES = {
    (0x20, 0x81, 0x27): 2,
    (0x14, 0x02, 0x00): 2,
    (0x80, 0x06, 0x1f): 2,
    (0x14, 0x02, 0x20): 2,
    (0x54, 0x00, 0x00): 2,
    (0x20, 0x81, 0x1f): 2,
    (0x08, 0x01, 0x0c): 2,
    (0x20, 0x81, 0x9f): 2,
    (0x20, 0x6a, 0xf9): 2,
    (0x28, 0x05, 0x0c): 2,
    (0x80, 0x06, 0x00): 2,
    (0xa2, 0x10, 0x4f): 2,
    (0x02, 0x14, 0xa8): 2,
    (0x52, 0x29, 0x75): 2,
    (0x20, 0x81, 0x47): 2,
    (0x20, 0x81, 0x92): 2,
    (0x20, 0x81, 0x12): 2,
    (0x32, 0xb9, 0xa7): 2,
    (0x32, 0x50, 0xbf): 2,
    (0xf2, 0xba, 0x47): 2,
    (0x42, 0x2b, 0x6f): 2,
    (0x20, 0x81, 0x62): 2,
    (0x28, 0x05, 0x38): 2,
    (0x32, 0x11, 0xad): 2,
    (0x82, 0x0a, 0x47): 2,
    (0x82, 0x0a, 0x22): 2,
    (0x82, 0x0a, 0x14): 2,
    (0x54, 0x00, 0x01): 2,
    (0x82, 0x06, 0x47): 2,
    (0x82, 0x0c, 0x47): 2,
    (0x52, 0x4b, 0xaf): 2,
    (0x4a, 0x0d, 0x65): 2,
    (0x20, 0x81, 0xd2): 2,
    (0x14, 0x02, 0x9f): 2,
    (0x20, 0x81, 0x32): 2,
    (0x51, 0x05, 0x00): 2,
    (0x92, 0x56, 0xbf): 2,
    (0x1a, 0x3f, 0x85): 2,
    (0x54, 0x00, 0x02): 2,
    (0x92, 0x30, 0x4f): 2,
    (0x92, 0x46, 0x4f): 2,
    (0x92, 0x90, 0x47): 2,
    (0x32, 0x86, 0x65): 2,
    (0x80, 0x0e, 0xa7): 2,
    (0x54, 0x00, 0x04): 2,
    (0x02, 0x60, 0xa9): 2,
    (0x42, 0x93, 0x67): 2,
    (0xb2, 0x0b, 0x47): 2,
    (0xd2, 0x91, 0x75): 2,
    (0x32, 0x12, 0xbf): 2,
    (0x1a, 0x11, 0x6d): 2,
    (0x02, 0x24, 0xbf): 2,
    (0xe2, 0x08, 0x7f): 2,
    (0x42, 0x4a, 0xbf): 2,
    (0xb2, 0xc9, 0xa7): 2,
    (0x20, 0x81, 0xc2): 2,
    (0x20, 0x81, 0x02): 2,
    (0x72, 0x13, 0x6f): 2,
    (0x20, 0x82, 0x9f): 2,
    (0x82, 0x0a, 0xbf): 2,
    (0x82, 0x54, 0xbf): 2,
    (0x52, 0x28, 0xbf): 2,
    (0x82, 0x0c, 0xbf): 2,
    (0xe2, 0x90, 0x47): 2,
    (0x62, 0x10, 0x87): 2,
    (0x82, 0xc3, 0xa7): 2,
    (0x14, 0x02, 0x80): 2,
    (0x80, 0x06, 0x22): 2,
    (0x08, 0x01, 0x0e): 2,
    (0x42, 0x02, 0x57): 2,
    (0x80, 0x0e, 0x42): 2,
    (0x02, 0x14, 0x98): 2,
    (0x5a, 0x37, 0x75): 2,
    (0x92, 0xd1, 0xa7): 2,
    (0x82, 0x20, 0x10): 2,
    (0xc2, 0x12, 0x4f): 2,
    (0x82, 0x0a, 0x42): 2,
    (0x80, 0x0e, 0x59): 2,
    (0x80, 0x0e, 0x09): 2,
    (0x20, 0x81, 0x1a): 2,
    (0x80, 0x0e, 0x00): 2,
    (0x02, 0x97, 0x63): 2,
    (0x62, 0xa6, 0x67): 2,
    (0x80, 0x0e, 0x29): 2,
    (0x80, 0x0e, 0x7c): 2,
    (0x72, 0x40, 0x2c): 2,
    (0x02, 0x86, 0x67): 2,
    (0x82, 0x0c, 0x62): 2,
    (0x1d, 0x80, 0x00): 2,
    (0x5b, 0x25, 0x64): 2,
    (0xbb, 0x29, 0x64): 2,
    (0x82, 0x18, 0x62): 2,
    (0x72, 0x03, 0x0b): 2
}

def _r9_named_at(buf, off, L):
    """True iff a real DB descriptor of length L MATCHES the L bytes at off."""
    if off + L > len(buf):
        return False
    v = _int_from_bytes(bytes(buf[off:off + L]))
    for _d in DB:
        if _d["length"] == L and _matches(_d, v):
            return True
    return False

def _r9_succ_safe(buf, q):
    """Non-swallow guard: only close a 2-byte R9 word when the successor at q is
    itself undecodable, a <=2B op, or a real NAMED op -- never mid-op."""
    if q >= len(buf):
        return True
    L = instr_length(buf, q)
    if L is None or L <= 2:
        return True
    return _r9_named_at(buf, q, L)

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
    # ---- SFU range-reduction 2-byte operand-WORDS (EXP-M4-12 S1, sin/cos) ----------
    # The transcendental argument range-reduction (sin/cos) injects little-endian
    # immediate/coefficient WORDS between the SFU ops. Each is 2 bytes, cleanly
    # bracketed between known-length ops; tightly gated on (byte0, byte+1) so it can
    # never mis-length a real op. Operands are intentionally NOT bit-decoded -- doing so
    # would reconstruct the range-reduction sequence, which clean-room rule 5 forbids.
    # Every gate is anchored by an isolated OWN-SHADER compile (S1 evidence table).
    _b1 = buf[off + 1] if off + 1 < len(buf) else -1
    _b2 = buf[off + 2] if off + 2 < len(buf) else -1
    # ---- EXP-M4-13 R9 desync trailing-word closure (ADDITIVE, guarded) ----------
    # Fires only where baseline instr_length was None at a real boundary; the
    # _r9_succ_safe guard makes it provably non-regressing (never swallows a real op).
    _r9 = _R9_SIGS.get((b0, _b1))
    if _r9 is None:
        _r9 = _R9_TRIPLES.get((b0, _b1, _b2))
    if _r9 is not None and _r9_succ_safe(buf, off + _r9):
        return _r9
    # ---- RAY-QUERY traversal / getter op (EXP-M4-13 R2 nf_simd) --------------------
    # 8-byte low-nibble-f op emitted only in intersection_query traversal/getters. Gated
    # tightly on byte+1==0x80 AND byte+2==0x86 (the SFU-datapath marker) so it never touches
    # call_indirect (0f 80 0x85), simd_reduce (0x3f/0xbf byte+2 0x54/0x56) or ret (0x8f).
    # The trailing `[07|0f] 22 82 ZZ` is its OWN bytes +4..+7 (the round-1 spurious 0f22 leaders).
    if lo == 0x0f and _b1 == 0x80 and _b2 == 0x86:          return 8   # rt_query_traverse
    # ---- fldexp (EXP-M4-13 R2 nf_simd): runtime ldexp(float,int)=a*2^n, `0f 15 80` -------
    if b0 == 0x0f and _b1 == 0x15 and _b2 == 0x80:          return 6   # fldexp
    # ---- rtq_pred (EXP-M4-13 R2 n6_deriv): ray-query traversal predicate word `06 c2 00 00` --
    # Byte-INVARIANT 4-byte token in intersection_query loops. Gated tight on byte+1==0xc2 so it
    # never touches the 2-byte `06 02` SFU marker below.
    if b0 == 0x06 and _b1 == 0xc2 and _b2 == 0x00 \
            and off + 3 < len(buf) and buf[off + 3] == 0x00:   return 4   # rtq_pred
    if b0 == 0x06 and _b1 == 0x02:                          return 2   # 06 02
    if b0 == 0x01 and _b1 == 0x00:                          return 2   # 01 00
    if b0 == 0x00 and _b1 in (0x00, 0x80, 0x84):            return 2   # 00 00 / 00 80 / 00 84
    # ---- EXP-M4-13 R4 (cascade 0x00): VERTEX varying-output SLOT op, 4 bytes ----
    # `00 YY 40 SS` (byte+1 in {0x04,0x0a,0x0c}, byte+2==0x40) emitted before each vary_store;
    # byte+3 = varying slot. byte+1 set is DISJOINT from the 2-byte pad set {0x00,0x80,0x84}
    # above and the stop (0e), so it never mis-lengths a pad or stop. Additive.
    if b0 == 0x00 and _b1 in (0x04, 0x0a, 0x0c) and _b2 == 0x40:   return 4   # vary_slot (EXP-M4-13 R4)
    if b0 == 0x00:
        return 2                   # pad_operand catch-all (EXP-M4-13 R8, ADDITIVE desync-root
                                   # closure): every remaining `00 XX` is a trailing operand /
                                   # immediate / SFU-coefficient / inter-op PAD word -- the
                                   # pad_operand NEGATIVE RESULT generalised from the {00,80,84}
                                   # b1-set to all other b1. Reached ONLY after the 2-byte
                                   # {00,80,84} pad rule and the 4-byte vary_slot (b2==0x40) rule
                                   # both fail, i.e. only for 00-led bytes that previously returned
                                   # LEN_UNKNOWN. Decodes as the low-nibble-0 pad_operand descriptor.
    if b0 == 0x80 and _b1 in (0x00, 0x08, 0x0c):            return 2   # 80 00 / 80 08 / 80 0c
    if b0 == 0x20 and _b1 in (0x00, 0x80) and _b2 != 0x24:  return 2   # 20 00 / 20 80 (b2!=0x24: half2)
    if b0 == 0x20 and _b1 in (0x01, 0x81, 0x82) and _b2 == 0x0f:  return 2   # RT/CF predicate-mask
                                       # operand word (EXP-M4-13 R4): `20 {01,81,82} | 0f 05 54 ..` precedes an
                                       # if_push+jump_cond. Decodes as pad_operand (low-nibble-0). Additive.
    if b0 == 0xa0 and _b1 == 0x0c:                          return 2   # a0 0c
    if b0 == 0x03 and _b1 == 0x02 and _b2 != 0x26:          return 2   # 03 02 (b2!=0x26: sample-id read)
    if b0 == 0xa0 and _b1 == 0x00 and _b2 == 0x00:          return 4   # a0 00 00 00: loop-header compact
                                       # init op (EXP-M4-12 S4: k_cf_loop@0x44, get_sr -> [4] -> iadd2;
                                       # reproduced in cf_for/cf_break). Distinct from the 2-byte `a0 0c`.
    # ---- get_sr special-register read / mov_imm (EXP-0031, HW-validated) ----
    # byte0 low-3-bits == 0b100: either the 0xNc preamble form or the 0xN4 datapath
    # form; byte1 = the SR number; byte+2/+3 = a 32-bit-source suffix whose byte+3
    # low-nibble == 6 (`.. 10 06` / `.. 14 66` observed). dst = byte0 high nibble.
    # Gated on that suffix so it never swallows the 2-byte `mov_imm` (small immediate,
    # no suffix), the fragment 0x04 centroid read, or an rt_intersect (byte+1==0xea).
    if (b0 & 0x07) == 0x04 and not (off + 1 < len(buf) and buf[off + 1] == 0xea):
        if off + 3 < len(buf) and (buf[off + 3] & 0x0f) == 0x06:
            return 4                   # get_sr (EXP-0031 HW: byte1=SR#, byte0-hi=dst)
        if b0 == 0x0c:
            return 2                   # mov_imm (constant-folded builtin, e.g. 0c 20).
                                       # Restricted to byte0==0x0c (the HW-validated r0-dst
                                       # form) so it never over-claims other 0xNc ops.
        # ---- sr_read_wide (EXP-M4-13 n4_tex): 8-byte member of this datapath family ----
        # The wide/indexed builtin or intersection_query PROPERTY read. dst = byte0 high
        # nibble (all dst regs). byte+1 bit7 set = selector (distinguishes from the
        # reconverge-operand word `X4 0Y 00 00`, byte+1 < 0x80); byte+3 == 0x00 and byte+2
        # low-nibble in {2,6} exclude get_sr (byte+3 lo-nib 6), rt_intersect (byte+1==0xea,
        # already excluded above) and desync-landing pairs (byte+2 lo-nib 9). Length 8
        # anchored by the immediately-following op across the corpus.
        if (b0 & 0x0f) == 0x04 and off + 3 < len(buf) and buf[off + 1] >= 0x80 \
                and buf[off + 3] == 0x00 and (buf[off + 2] & 0x0f) in (0x02, 0x06):
            return 8                   # sr_read_wide (EXP-M4-13 n4)
    # ---- FRAGMENT-STAGE memory / output family (EXP-0029, HW-validated) ----
    # The fragment stage reuses the low-nibble-7 memory family with distinct byte+1
    # variants that never occur in compute (compute load/store use byte+1 in
    # {0x00,0x10,0x11,0x01,0x02}, byte+2==0x56; the fragment forms below use
    # byte+2==0x54). Gate on those so compute tokenization is unaffected.
    if b0 == 0xe7 and (buf[off+1] if off+1 < len(buf) else -1) in (0x06, 0x16):
        return 12                      # fragment COLOUR STORE / explicit imageblock<T>.write to tile
                                       # memory (EXP-0029 / EXP-O2D HW). byte+1 0x16 == 0x06|0x10 = the
                                       # FIRST store after a 0x87 tile-access setup (dispatchThreadsPerTile
                                       # tile shader); 0x06 = a subsequent store / simple-MRT colour store.
    if b0 == 0x67 and (buf[off+1] if off+1 < len(buf) else -1) in (0x06, 0x0e, 0x16):
        return 12                      # fragment TILEBUFFER READ (0x0e programmable-blend tile_read,
                                       # EXP-0029) / explicit imageblock<T>.read (0x06 / 0x16 tile
                                       # first-access variant, EXP-O2D HW)
    if b0 == 0x87 and off + 2 < len(buf) and buf[off+2] == 0x54:
        return 6                       # fragment tile/RT access-setup (EXP-0029)
    # COMPUTE scoreboard fence, high-scope variants (EXP-M4-01): byte0 0x87/0x80 are the
    # 0x07 scoreboard_fence family with the high bit set (a wider memory / device scope).
    # 4 bytes -- `87 02 00 00` / `80 02 00 00`. In k_tex_atomic these gate every
    # texture-atomic RMW (icmp -> fence -> if_push -> atomic_mem), the exact slot the
    # 0x07 fence fills in the non-texture atomics kernel. Gated off the fragment 0x87
    # (byte+2==0x54, handled above) and off 0x80 operand-tail bytes (byte+1 != 0x02).
    if b0 == 0x87:
        if off + 2 < len(buf) and buf[off + 1] == 0x00 and 0 < buf[off + 2] < 0x80:
            return 2                   # BARE compute fence, 2 bytes (EXP-M4-12 S3): byte+1==0x00 and
                                       # byte+2 is the NEXT op's byte0 (a real op-leader, 0<b2<0x80),
                                       # NOT a scope operand. k_uint_arith@0x114 `87 00 3a 80` -> the
                                       # `3a 80 ..` icmp_pred follows. Real scope operands set bit7
                                       # (e.g. `87 00 80 04`), so this never eats a 4-byte scoped fence.
        return 4                       # compute scoreboard fence (device/texture scope)
    if b0 == 0x80 and off + 1 < len(buf) and buf[off + 1] == 0x02:
        # compute scoreboard fence (0x80 scope variant): the FULL form is `80 02 00 00`
        # (4B, byte+2==0x00). A BARE `80 02` (byte+2 != 0x00, e.g. `80 02 0f 06` immediately
        # before a pop_reconverge in k_tex_atomic@866) is the 2-byte compact form -- do NOT
        # claim 4 there or it eats the following CF op. EXP-M4-01.
        return 4 if (off + 2 < len(buf) and buf[off + 2] == 0x00) else 2
    if b0 == 0x97:
        return 10                      # fragment colour-register pack/move (EXP-0029; no compute 0x97)
    if b0 == 0xd7 and off + 2 < len(buf) and buf[off+1] == 0x14 and buf[off+2] == 0x54:
        return 6                       # fragment [[depth]] store (EXP-0029)
    if b0 == 0x67 and off + 2 < len(buf) and buf[off + 1] == 0x03 and buf[off + 2] in (0x54, 0x56):
        # EXP-M4-13 R2 (n7_fence): RELAXED byte+2==0x54 -> {0x54,0x56}. atomic_exchange(threadgroup)
        # sets the byte+2==0x56 source cache-hint; the old ==0x54 gate missed it -> generic 0x67->14
        # over-read by 2 -> k_atomics_tg_xchg desync.
        return 12                      # THREADGROUP atomic load/store, 12 bytes (EXP-M4-12 S4):
                                       # k_atomics_tg -- the `67 03 54 ..` tg-atomic is 12B, but the
                                       # generic `0x67 -> 14` over-read it by 2 and swallowed a `0f 06`
                                       # pop_reconverge, cascading into the `44 05 00 40 00 00` residue.
    if b0 in (0x67, 0xe7):
        return 14                      # device load (0x67) / store (0xE7)
    # ---- FRAGMENT varying INTERPOLATION family (EXP-0029, HW-validated) ----
    # `iter` interpolate op: byte0 0x2f/0xaf, byte+2==0x54, 10 bytes; the 8-byte
    # form (byte+6==0x0a) is the interpolate-at setup (centroid/sample barycentric).
    # Compute fspecial (byte0 0x2f/0xaf) uses byte+2==0x56 or, in precise mode,
    # byte+2==0x54 but never byte+6==0x0a -> the 8-byte case is fragment-only.
    if b0 in (0x2f, 0xaf) and off + 2 < len(buf) and buf[off+2] == 0x54:
        if off + 6 < len(buf) and buf[off+6] == 0x0a:
            return 8                   # interpolate-at setup (centroid/sample position)
        # else fall through to the existing 0x2f/0xaf -> 10 rule below.
    # `iter_flat`: flat varyings load the provoking-vertex attribute via byte0 0x1f
    # with byte+2==0x54 and a small byte+1 (0x03 / 0x0b), 6 bytes. NB compute integer
    # ALU is also byte0 0x1f/0x9f and CAN carry byte+2==0x54 (e.g. `9f 11 54 ...`),
    # so this is gated on the fragment-specific byte+1 signatures to avoid colliding
    # with the compute integer length rule below.
    if b0 == 0x1f and off + 2 < len(buf) and buf[off+2] == 0x54 and buf[off+1] in (0x03, 0x0b):
        return 6                       # fragment flat / attribute load (EXP-0029)
    # ---- MESH output-store SOURCE op (EXP-M4-13 R5 stage_len): `04 SS e7 02`, 2 bytes ----
    # A compact mesh-stage source word that feeds the immediately-following 14-byte
    # device_store (0xe7 leader at byte+2, its 0x02 sub-byte at byte+3). The flat fragment
    # centroid rule (`0x04 -> 8`) over-read it by 6 and swallowed the store head + a `0f 06`
    # pop_reconverge. Gate on byte+2==0xe7 && byte+3==0x02 so it never touches the fragment
    # centroid read (byte+2 != 0xe7), get_sr, sr_read_wide or rt_intersect (byte+1==0xea).
    if b0 == 0x04 and off + 3 < len(buf) and buf[off + 2] == 0xe7 and buf[off + 3] == 0x02:
        return 2                       # mesh_out_src (compact mesh output-store source, R5)
    # ---- EXP-M4-13 R7 desync-root closure (0x04 over-read): two compute/RT compact 4-byte ops
    # the flat `0x04 -> 8` centroid rule over-read by 4 (swallowing the following pop_reconverge /
    # rt_ray_mem / if_push / frame_marker). Both are compute/RT-only signatures the fragment
    # centroid read never produces; get_sr / sr_read_wide / rt_intersect are already handled above.
    if b0 == 0x04 and _b1 == 0x01 and _b2 == 0x00:
        return 4                       # n4_cf_word: `04 01 00 00` reconverge/predicate-prep word
                                       # (compute/RT only; fragment centroid reads set byte+1 high-bit).
    if b0 == 0x04 and _b2 == 0x20 and off + 3 < len(buf) and buf[off + 3] == 0x80:
        return 4                       # n4_rt_word: `04 <d> 20 80` RT-query compact op. byte+3==0x80
                                       # distinguishes it from fragment reads (byte+3==0x00).
    # byte0==0x04 8-byte RESIDUE (op04_len8): the low-nibble-4 datapath fallback after
    # get_sr / sr_read_wide / rt_intersect / mesh_out_src / n4_cf_word / n4_rt_word.
    # NB (EXP-M4-14 splice+audit): NOT a fragment-position read ([[position]]/[[front_facing]]
    # lower to get_sr+iter). This fixed length-8 is a CANDIDATE OVER-CONSUMER of a following
    # leader in compute/third-party streams (byte+2 is a heterogeneous mix of real op-leaders);
    # LEFT UNCHANGED here because no single shorter length is provably regression-free -- a
    # modifier/context-aware length is needed (flagged for the length-rule owner). See op04_len8.
    if b0 == 0x04 and off + 1 < len(buf) and buf[off+1] != 0xea:
        return 2                       # EXP-0148 H5 candidate: 2 bytes

    if b0 == 0x03 and off + 2 < len(buf) and buf[off+2] == 0x26:
        return 10                      # sample-id / sample-position read
    # ---- THREADGROUP / EXECUTION BARRIER (EXP-0025, HW-validated) ----
    # threadgroup_barrier compiles to a distinct 6-byte op: byte0 0x07, byte+2 0x54
    # (07 04 54 <mem_scope> <flags> 00). This is the ONLY explicit ordering/"wait"
    # primitive the compute compiler emits: device load/store/atomic/texture are NOT
    # scoreboard-waited in the instruction stream (they rely on a HARDWARE register
    # interlock; a consumer that reads a pending destination register stalls in HW).
    # The barrier synchronises CROSS-LANE threadgroup-memory ordering, which HW register
    # interlock cannot cover. byte+2==0x54 gates it off from the vtx/frag 0x07 varying
    # stores (compute only). simdgroup_barrier emits NO 0x07 op (lockstep 32-lane simd).
    if b0 == 0x07 and off + 2 < len(buf) and buf[off + 2] == 0x54:
        # EXP-0038: the NON-LEAF-frame link-register SAVE/RESTORE is an 8-byte op in
        # the same 0x07 family (byte+1==0x00, byte+4==0x81), distinct from the 6-byte
        # threadgroup_barrier / pixel_order (byte+1 in {0x04,0x14}). The old flat rule
        # lengthed both as 6 and desynced every non-leaf helper -- gate on byte+1.
        if off + 1 < len(buf) and buf[off + 1] == 0x00:
            return 8                   # link register save/restore around a nested call (EXP-0038 HW)
        return 6                       # threadgroup / execution barrier | pixel_order (EXP-0025/0029 HW)
    # ---- COMPUTE MEMORY / SCOREBOARD FENCE (byte0 0x07, byte+2 in {0x00,0x02}) ----
    # A 4-byte fence the compiler inserts around calls and divergent control flow,
    # DISTINCT from the 6-byte threadgroup_barrier (byte+2==0x54). HW-observed forms:
    # `07 22 02 00` (immediately before a 43 frame-marker/call, RT-1b census),
    # `07 02 00 00` / `07 00 00 00` (around break/continue divergence, RT-ISA-FIX).
    # Gated on byte+2 in {0x00,0x02} so it never touches the 0x54 barrier above or the
    # vertex/fragment 0x07 varying stores. (RT-ISA-FIX: closes the RT-1b census gap
    # where a `07 22 02` halted strict tokenization for want of a length rule.)
    if b0 == 0x07 and off + 2 < len(buf) and (
            buf[off + 2] in (0x00, 0x02, 0x20, 0x88)
            or (buf[off + 2] == 0x22 and buf[off + 1] == 0x22)):
        return 4                       # compute memory / scoreboard fence (RT-ISA-FIX HW).
                                       # EXP-M4-13 R5 (n7_barrier): byte+1==0x22 && byte+2==0x22 is the
                                       # SUBGROUP-VOTE fence `07 22 22 80` (multi-vote sibling of the 0x20
                                       # single-vote form) and byte+2==0x88 is the copysign SIGN-COMBINE op
                                       # `07 c2 88 00`; both were unlengthed (byte+2 not in the old set) and
                                       # desynced their operand tails as spurious 0x54. Both are 4B; byte+2
                                       # bit0==0 so scoreboard_fence already matches once lengthed (copysign
                                       # additionally gets a more-specific descriptor). The 0x22 case is
                                       # gated on byte+1==0x22 (the validated subgroup-vote signature) so it
                                       # never lengthens the `07 00 22`/`07 02 22` cascade-region bytes in
                                       # the ray-query commit kernels (which would shift a downstream resync).
                                       # EXP-M4-01 round-3: byte+2==0x20 is the SUBGROUP-scope
                                       # variant (`07 00 20 80` in k_subgroup_ballot@58, between the
                                       # simd_ballot ops and the reduce iadd2 chain); 4B, anchored by
                                       # a clean 6-op resync to the stop. Same 0x07 fence family.
    # ---- TEXTURE / SAMPLE family (EXP-0016, HW-validated) ----
    # Texture sample & texture.read are a 14-byte bundle: a 4-byte coordinate/result
    # "companion" (byte0 low-nibble 5, byte+1==0x80, byte+2==0x0c) immediately
    # followed by the 10-byte sampler op (byte0 low-nibble 0 = the 0xb0/0x90 group;
    # its high nibble is the result-register selector). Gate on the companion
    # signature so it never collides with the 4-byte psel/sel (byte0 0x05/0x16).
    if ((b0 & 0x07) == 0x05 and off + 2 < len(buf)
            and (buf[off + 1] & 0xf0) == 0x80 and buf[off + 2] == 0x0c):
        return 14                      # tex_sample / tex_read (companion + sampler op);
                                       # low-3-bits 5 covers the 0x0d sample_compare companion (EXP-0034).
                                       # EXP-0037 FIX: byte+1 widened from ==0x80 to high-nibble 8 so the
                                       # CHAINED-companion forms (0x82/0x84/0x88 before the 2nd..Nth sample
                                       # op in multi-sample kernels) also absorb their 0xb0/0x90 sampler op.
    if b0 == 0xd7:
        return 16                      # texture WRITE (memory family; EXP-0016 HW)
    # ---- SUBGROUP / QUAD FAMILY (EXP-0018, HW-validated) ----
    # SIMD-group & quad reduce/scan: byte0 in {0xbf,0x3f (simd), 0xb7,0x37 (quad)},
    # 8 bytes, always byte+2 == 0x56. NB byte0 0x37 is ALSO the fragment-only
    # derivative (10B, EXP-0016); disambiguate on byte+2 (reduce ops set 0x56,
    # derivatives do not). Compute vs fragment never coexist, so this is safe.
    if b0 in (0xbf, 0x3f, 0xb7) and off + 2 < len(buf) and (buf[off + 2] & ~0x02) == 0x54:
        return 8                       # simd/quad reduce/scan. EXP-0038: accept byte+2 in
                                       # {0x54,0x56} -- bit17 is a source cache/last-use hint,
                                       # not an op change (a later-consumer reduce comes out 0x54).
                                       # NB gate is ONLY on 0xbf/0x3f/0xb7 -- the 0x37 derivative-vs-
                                       # quad-reduce disambiguation below is deliberately untouched.
    if b0 == 0x37:
        if off + 2 < len(buf) and buf[off + 2] == 0x56:
            return 8                   # quad reduce/scan (and/min)  EXP-0018
        if off + 2 < len(buf) and buf[off + 2] == 0x80:
            return 8                   # COMPUTE texture gradient/coordinate setup (EXP-M4-01):
                                       # `37 xx 80 00 00 00 00 00` (all-zero operands) in the software
                                       # texture-coordinate atomic address path. 8B; the following
                                       # `27 00 54 .. f0 13 01 00` is a 12-byte ibfe. The fragment
                                       # derivative (dfdx/dfdy) is byte+2==0x54 and stays 10 below.
        return 10                      # derivative / quad-difference (dfdx/dfdy); EXP-0016
    # SIMD/quad shuffle & broadcast: byte0 0x47 (broadcast / up) / 0xc7 (xor / down),
    # 10 bytes (EXP-0018 HW-validated semantics).
    if b0 in (0x47, 0xc7):
        return 10                      # simd/quad shuffle / broadcast
    # ---- byte0 0x17: three length-distinct ops, disambiguated by byte+1 (EXP-M4-12) ----
    # The old flat `-> 10` was correct only for compute simd_ballot; it mis-lengthed the
    # fragment unpack_convert (should be 8) and the texture coordinate-projection setup
    # (should be 12), whose 2-byte overruns produced the r_blend / k_cvt_pack / k_tex_msaa
    # / k_tex_array_cube residue cascades. byte+1 cleanly separates the three:
    #   byte+1 low-nibble 4 (0x04/0x14)            -> 8   unpack_convert (fragment tilebuffer
    #                                                     colour unpack, S4; and fp-pack convert,
    #                                                     S3 k_cvt_pack -- two back-to-back 8B unpacks)
    #   byte+1 in {0x01,0x05} & (byte+2 & ~2)==0x54 -> 12  texture coordinate-projection /
    #                                                     sample-address SETUP (S2 k_tex_msaa,
    #                                                     k_tex_array_cube; carries a trailing
    #                                                     operand word past the base 10B form)
    #   else (byte+1 low-nibble 7)                 -> 10  simd_ballot / vote mask source (compute)
    if b0 == 0x17:
        if (_b1 & 0x0f) == 0x04:
            return 8
        if _b1 in (0x01, 0x05) and (_b2 & ~0x02) == 0x54:
            return 12
        if _b1 == 0x02 and _b2 == 0x00:
            return 12                  # rtq_dualsrc (EXP-M4-13 R7 desync-root): intersection_query
                                       # dual-source op `17 02 00 ..` carries TWO 4-byte operand words
                                       # (+4..+11); the flat -> 10 under-read it and exposed the 2nd
                                       # operand as a spurious UNDEC. Tight gate (byte+1==0x02 &&
                                       # byte+2==0x00) so simd_ballot (17 02 54 / 17 02 82) keeps 10.
        return 10                      # simd_ballot / vote mask source
    if lo == 0x09:
        # float ALU: 2-source (6B) unless the fma/3-source length bit is set.
        # NB: the 10-byte *extended source-modifier* form (abs; EXP-0006) also
        # has low-nibble 9 but is not distinguishable from byte0/byte2 alone --
        # a documented follow-up; the compiler emits it only for fabs sources.
        # EXP-0025: byte+2 == 0x38 selects a COMPACT 4-byte float accumulate
        # (arithmetic-enable bit clear; dst=srcA implicit accumulator, srcB=byte+3).
        # The reduction compiler emits it interleaved with the 6-byte 0x3c fadds.
        # (This is arithmetic, NOT a scoreboard wait -- proven by a byte+3 source-reg
        #  sweep + the add-count = N-1 for an N-value sum; EXP-0025.)
        # EXP-0037 op-select-aware length FIX: the flat `8 if (byte+2 bit1) else 6`
        # mis-lengths the fused-mul COORDINATE / matrix-multiply op-selects 0x26/0x2e
        # (byte+2 bit1 is SET yet the 2-source form is 6 bytes) -- for those, the
        # length selector is byte+4 bit1, not byte+2 bit1. 0x18/0x38 = 4-byte compact
        # accumulate. Everything else keeps the HW-validated fadd/fmul/fma rule.
        b2 = buf[off + 2] if off + 2 < len(buf) else -1
        if b2 in (0x18, 0x38, 0x19, 0x21, 0x31, 0x30, 0x39):
            return 4                   # compact float accumulate/move (arith-enable bit clear).
                                       # EXP-M4-01: 0x19 (t_sqrt@28 `09 05 19 01`), 0x21/0x31 (s_div@136
                                       # `79 8d 21 97`/@244) join the EXP-0025 0x18/0x38 forms -- all are
                                       # the 4-byte low-nibble-9 form the div/sqrt refinement emits between
                                       # cvt anchors (anchored gap length = 4). EXP-M4-12 S4 adds the bit0
                                       # siblings 0x30 (r_deriv_f `89 81 30 11`) and 0x39 (r_tex_f
                                       # `19 03 39 11` / `29 07 39 09`) -- same 4-byte compact form; their
                                       # absence orphaned the following tex_deriv / frag_color_pack.
        if b2 in (0x26, 0x2e):
            b3 = buf[off + 3] if off + 3 < len(buf) else -1
            b4 = buf[off + 4] if off + 4 < len(buf) else -1
            b6 = buf[off + 6] if off + 6 < len(buf) else -1
            b7 = buf[off + 7] if off + 7 < len(buf) else -1
            if b2 == 0x2e and b3 == 0x87 and b4 == 0x23 and b6 == 0x42 and b7 == 0x00:
                return 12              # 12B texture-coordinate TRANSFORM (0x2e sibling of the 0x3e
                                       # coord op), EXP-M4-12 S2: k_tex_array_cube@0x5e
                                       # `49 0f 2e 87 23 a0 42 00 00 06 02 00`. The `byte+4 bit1 -> 8`
                                       # rule mis-lengthed it 8 and exposed its tail `00 06 02 00` as a
                                       # spurious leader. Signature `2e 87 23 .. 42 .. 00` is unique
                                       # (no 6/10B coord op shares it).
            # EXP-M4-01: the EXTENDED-source fused mul-add coord op carries a trailing
            # `00 <slot>` operand word (10 bytes). Signature byte+4==0x82, byte+6==0x42,
            # byte+7==0x02; the trailing word's byte+1 is the varying/output SLOT (a
            # monotone 0x04,0x08,0x0c,0x10,... run in every VS: r_basic_v/r_deriv_v/
            # r_tex_v @80..@160). The old `byte+4 bit1 -> 8` rule stopped at `.. 42 02`
            # and exposed the slot word as a spurious 2-byte 0x00 group.
            if b4 == 0x82 and b6 == 0x42 and b7 == 0x02:
                return 10              # extended-source fmul-add coord op (VS varying compute)
            return 8 if (b4 & 0x02) else 6  # fused mul / mul-add coord op (EXP-0037)
        if b2 == 0x3e and (buf[off + 4] if off + 4 < len(buf) else -1) == 0x80:
            return 6                   # 6B uniform-source falu (op-select 0x3e, byte+4==0x80),
                                       # EXP-M4-12 S4: r_blend_f `19 03 3e 09 80 06`. 0x3e has bit1 set
                                       # so the fma branch below mis-lengthed it 8, orphaning the
                                       # frag_color_pack `54 05` tail. Gated on byte+4==0x80 so the
                                       # compute coord form (`3e .. 23 a0 42`, byte+4==0x23) keeps fma.
        if b2 & 0x02:
            # fma / 3-source form. EXP-M4-10 (ISA-2/3, HW byte-diff): the fma ALSO
            # carries the saturate/abs EXTENDED tail, so it is length-POLYMORPHIC on
            # byte+4 exactly like the 2-source form: plain fma byte+4 low2=01 -> 8,
            # saturate(fma) byte+4=0x82 -> 10 (`09 01 1e 05 82 08 02 00 00 82`),
            # abs-src fma byte+4=0x83 -> 12 (`09 01 1e 05 83 08 02 00 00 80 01 00`).
            # The old flat `return 8` mis-lengthed saturate/abs fma and desynced the
            # tail. EXP-M4-13 (rare_e5ad): the low2==0 case IS reached -- the compact
            # VECTOR-CONTINUATION fma (2nd..Nth component of a floatN fma, byte+4==0x80 ->
            # low2=0) is 6 bytes, not 8. The old `else 8` over-read every continuation by 2
            # and exposed the next component's byte+2 op-select (0x1e/0x2e/0x3e) as a
            # spurious leader. Use the SAME uniform 6+2*(byte+4&3) as the 2-source branch
            # (own-shader t_fma4 == corpus float_arith__fma_v4 reproduces it byte-exact).
            b4 = buf[off + 4] if off + 4 < len(buf) else 0
            return 6 + 2 * (b4 & 0x03)
        # EXP-M4-10 (ISA-2/3, HW-splice): the EXTENDED 2-source float-ALU form
        # (output-clamp `saturate` / srcA-slot negate / abs) is LONGER than the compact
        # 6-byte form even though byte+2 bit1 (the fma length bit) is CLEAR. Its length is
        # 6 + 2*(byte+4 & 0x3): byte+4 0x00 -> 6 (plain fadd/fmul, and the 0x80 immediate /
        # uniform forms whose low 2 bits are 0), 0x01 -> 8 (saturate output-clamp bit57, or
        # srcA-negate), 0x02 -> 10 (abs srcA/srcB slot). HW-splice proven: saturate(a+b) =
        # `09 05 1c 01 01 00 00 82` (8B); the old `8 if b2&0x02 else 6` mis-lengthed it as 6
        # and dropped the `00 82` clamp-mod tail (leftover 20 bytes, tokenizer desync).
        b4 = buf[off + 4] if off + 4 < len(buf) else 0
        return 6 + 2 * (b4 & 0x03)
    if lo == 0x0b:
        # EXP-0020: the uniform-register -> GPR move is a compact 4-byte form in
        # this group (`Xb YY 01 08`). The 10-byte funary/ilogic forms always carry
        # byte+2 in {0x0e (fmov), 0x1e/0x1f (bitwise LUT base)}. The register/64-bit
        # shift-amount PREP stage (0x2b/0x3b/0x5b/0x8b, EXP-0033) is 10 with byte+2
        # low-nibble e/f. Anything else in this group (e.g. the compact call-argument
        # move `ab 82 21 c0`, half-unpack helpers) is not yet characterized -> leave
        # the length UNKNOWN rather than mis-length (and mis-align) the stream.
        # EXP-M4-13 R2 (nb_ray): the 0x?b group is TWO sub-families keyed on byte+2's LOW
        # nibble: {0,1,9,b} = 4-byte COMPACT REGISTER MOVES (incl. the RAY-struct marshalling
        # moves around rt_intersect / intersection_query); {7,e,f} = 10-byte source-modifier /
        # logic / convert ALU. byte0 HIGH nibble = dst reg in every form; byte+3 in {0x00,0x08}
        # = none/32-bit-register operand type. All rules below are byte-diff / anchored-bracket
        # inferred from OWN-MSL (no GPU dispatch).
        b2 = buf[off + 2] if off + 2 < len(buf) else -1
        b1 = buf[off + 1] if off + 1 < len(buf) else -1
        b3 = buf[off + 3] if off + 3 < len(buf) else -1
        # ---- EXP-M4-13 R4 (cascade 0x40): VERTEX output-position op, 8 bytes ----
        # `Xb 00 26 00 40 00 00 SS` (SS = varying/output slot). Was mis-lengthed 4 by the
        # compact-move rule, so its `40 00 00 SS` tail (+4..+7) surfaced as the dominant
        # spurious 0x40 root desync. Gated on the exact signature; b3==0x00 so it never
        # touches the R4 src-class-0x02 move; placed before the (b2&0xf0)==0x20 rule (b2==0x26).
        if b1 == 0x00 and b2 == 0x26 and b3 == 0x00 \
                and off + 4 < len(buf) and buf[off + 4] == 0x40:
            return 8                   # vtx_out_pos (EXP-M4-13 R4)
        if b1 == 0x35:
            return 2                   # compact texture coord/LOD selector (EXP-M4-01): `2b 35`/`0b 35`.
        if b2 == 0x01:
            return 4                   # uniform_mov (uniform-bank -> GPR). nb_ray BROADENED from
                                       # (b2==0x01 && byte+3==0x08) to any byte+3 (adds the b3==0x00 sibling).
        # ---- 10-byte modifier / logic / convert ALU: byte+2 low-nibble {7,e,f} ----
        # funary(0x0e)/ilogic(0x1e/0x1f)/`& mask`(0x17)/funary_imm(0x0f) + the shift-amount PREP
        # stage generalised from byte0 {2b,3b,5b,8b} to ANY dst high-nibble. 0xd7/0xe7 byte+2 are
        # device-store byte0s appearing as a spurious mid-desync leader -> excluded.
        if b2 == 0x17 or (b2 & 0x0f) in (0x0e, 0x0f):
            return 10
        if (b2 & 0x0f) == 0x07 and b2 not in (0xd7, 0xe7):
            return 10                  # b_alu10_lo7 modifier/convert/setup (incl. tex_coord_setup 0x27,
                                       # `& mask` variants 0x07/0x47/0x57/0x67/0x87/0xa7). nb_ray.
        # ---- 4-byte compact register moves ----
        if (b2 & 0x0f) == 0x0b:
            return 4                   # reg_move_cb: pack/bitcast/convert compact move (0x0b/0x1b/0x2b/0x3b).
        if (b2 & 0xf0) == 0x20:
            return 4                   # compact scalar/call-argument MOVE (byte+2 hi-nibble 2, EXP-0036).
        if b2 in (0x1c, 0x3c):
            return 4                   # compact SHIFT/ROTATE-amount op (EXP-M4-01).
        if b2 in (0x40, 0x41, 0x80, 0x81):
            return 4                   # RAY register-marshalling MOVE (ray_move family, EXP-O2C / nb_ray):
                                       # 0x81 copy / 0x80 zero-init (bit7 class) + 0x41 copy / 0x40 zero
                                       # (bit6 class). Reused for MPP matmul2d TRANSPOSE tile moves.
        if b2 == 0x09 and b3 == 0x00:
            return 4                   # rtq_state_move (intersection-query state read, nb_ray).
        if b1 == 0x00 and b2 == 0x06:
            return 8                   # tg_atomic_prep: threadgroup-atomic RMW descriptor prep (8B).
        if (b2 & 0x0f) in (0x00, 0x01, 0x09) and b3 in (0x00, 0x08):
            return 4                   # GENERAL 4-byte compact move (reg_move_c0/c1/c9 + source-class
                                       # variants; nb_ray). byte+3 in {none,32-bit-reg}. Covers the
                                       # `Xb 00 00 00` prep, call-arg marshalling, and RT-query grids.
        # ---- EXP-M4-13 R4 (lenhi): source-class 0x02 compact register move ----
        # Same 4-byte compact move as reg_move_c0/c1/c9 but with source-class byte+3==0x02
        # (Dawn std140 uniform->storage matrix-column marshalling `Xb YY Z0/Z1/Z9 02`).
        # Additive: fires only where byte+3==0x02, a case that previously fell through to
        # LEN_UNKNOWN. Reuses the existing reg_move_c0/c1/c9 descriptors (byte+2 low nibble).
        if (b2 & 0x0f) in (0x00, 0x01, 0x09) and b3 == 0x02:
            return 4
        return LEN_UNKNOWN             # other uncharacterized 0xNb compact form
    # ---- INTEGER COMPARE / MIN-MAX / SELECT / CARRY group (byte0 low-nibble 2) ----
    # EXP-M4-01 (M4/A18 census): this is ONE group whose byte0 HIGH nibble is the
    # DESTINATION register (r0..r15), exactly like the low-nibble-9 float ALU. The
    # DB previously hard-coded only dst r0..r3 (0x02/0x12/0x22/0x32) and left every
    # higher-register form (0x42,0x52,0x62,0x72,0x82,0x92,0xa2,0xb2,0xc2,0xd2,...)
    # UNDECODED -- the dominant source of census resync cascades. The op & length are
    # selected by the byte+2 op-select (all op-selects are <= 0x3f; a larger byte+2 is
    # an operand tail, not a real op). Lengths confirmed by anchored gaps (cvt/iadd/
    # imad/store brackets) in i_max/i_cmp/mm3/l_add/l_cmp/i_selreg/u_div/s_div/s_mod:
    #   byte+2 in {0x1e,0x2e,0x3e, 0x26,0x36, 0x35} -> 6   iminmax / carry_gen
    #   byte+2 in {0x1d,0x2d}                       -> 14  icmpsel (select 0/1 const)
    #   byte+2 == 0x27, byte+3==0x80 (reg operand)  -> 10  coord/madd
    #             ..   byte+3==0x81 & byte+4==0x22  -> 10  rt_transform_test (EXP-O2C)
    #             ..   else                         -> 8   quotient/wide-select
    #   byte+2 low-nibble {7,f} or 0x25, byte+3 hi-nibble 0/8 (reg descriptor) -> 10
    #                                                      register-operand cmpsel/select
    #   byte+1 == 0xc2, tail `.. 80 08`             -> 8   transcend range-reduction sel
    # Unrecognized op-selects fall back to the ORIGINAL per-dst-reg behavior so tails
    # and unhandled forms never get a wrong length (never regresses vs the old rules).
    if (b0 & 0x0f) == 0x02:
        b1 = buf[off + 1] if off + 1 < len(buf) else -1
        b2 = buf[off + 2] if off + 2 < len(buf) else -1
        b3 = buf[off + 3] if off + 3 < len(buf) else -1
        b4 = buf[off + 4] if off + 4 < len(buf) else -1
        # EXP-M4-13 R4 (rt_traversal): 2-byte compact PREP word before a b_alu14 (byte+2==0x83
        # int/simd ALU). byte0 low-nibble 2, high-nibble = dst; byte+1 = (dst<<1)|1. Tightly
        # gated on the compact-register relation AND the exact b_alu14 follower (byte+2 in
        # {0x3f,0x5f,0x7f}, byte+4==0x83) so it can never mis-length a real low-nibble-2 min/max.
        if b1 == (((b0 >> 4) << 1) | 1) and b2 in (0x3f, 0x5f, 0x7f) and b4 == 0x83:
            return 2                   # b_alu14_prep2 (EXP-M4-13 R4)
        if b1 == 0xc2 and (buf[off+6] if off+6 < len(buf) else -1) == 0x80 \
                      and (buf[off+7] if off+7 < len(buf) else -1) == 0x08:
            return 8                   # transcendental range-reduction select (t_sin@24)
        if 0 <= b2 <= 0x3f:
            ln = b2 & 0x0f
            if b2 == 0x21:
                return 10              # register-operand SELECT + trailing operand word, ALL dst regs
                                       # (EXP-M4-12 S1). t_sin/cos + sign range-reduction; the census
                                       # "6B" `X2 81 21 81 22 b0` was a resync-gap artifact -- the
                                       # trailing `02 02 20 80` / `03 02 09 05` is THIS op's operand
                                       # word. Disamb: at 8B the sign/round walk overruns; only 10B
                                       # reaches stop cleanly (isolated `sign`, transcend_round@38/@46).
            if b2 == 0x25:
                return 8 if (b4 & 0x02) == 0 else 10
                                       # icmp/select op-select 0x25, length-polymorphic on the srcC
                                       # descriptor byte+4 bit1: register srcC (clear) = 8B; immediate
                                       # 0/1-select srcC (set, `.. 22 81 .. 20 80` tail) = 10B. ALL dst
                                       # regs incl 0x22 (EXP-M4-12 S3: k_int64@0xa2 `92 8f 25 8b 85 19
                                       # 07 00` = 8B; the old reg-select rule below mis-lengthed it 10).
            if b2 in (0x1e, 0x2e, 0x3e, 0x26, 0x36, 0x35, 0x3d, 0x23, 0x2b, 0x03):
                return 6               # iminmax / carry_gen / fcmp-pred (0x3d, EXP-M4-01:
                                       # k_int_arith@224 `42 0d 3d 09 22 81` = 6B, feeds a psel)
                                       # / SFU polynomial fma (0x23, EXP-M4-01: k_transcend
                                       # `42 81 23 80 96 08` = 6B, the exp/log/pow Horner step
                                       # feeding a sel; anchored by the following 0x16 sel).
                                       # EXP-M4-12 S1 adds the sin/cos range-reduction op-selects
                                       # 0x2b (SFU range-reduction select, `72 01 2b 82 96 08` r7 /
                                       # `32 05 2b 82 95 06` r3 / `22 05 2b 0d 87 06` r2 -- uniform 6B
                                       # all dst regs; the old 0x22 rule mis-lengthed b2=0x2b as 10) and
                                       # 0x03 (SFU polynomial select, `42 85 03 0d 87 08` r4).
            if b2 in (0x1d, 0x2d):
                if b2 == 0x2d and b3 == 0x80:
                    return 10          # register-operand cmpsel (div/mod correction SELECT, EXP-M4-12
                                       # S3: k_uint_arith@0x134 `12 06 2d 80 26 80 ..` = 10B). The old
                                       # flat `-> 14` over-read it and swallowed the next op's head.
                return 14              # icmpsel: compare -> 0/1 const (b2=0x1d, b3=0x05)
            if b2 in (0x27, 0x2f) and b3 == 0x80:
                # madd / register-operand select `dst = srcA*srcB + srcC`, for ALL dst regs
                # INCLUDING 0x22. EXP-M4-01: byte+4 is the srcC operand descriptor and its bit1
                # (0x02) selects a WIDE srcC carrying a trailing 16-bit operand word -> 10 bytes;
                # clear -> 8. Cleanly separates all corpus occurrences of BOTH the 0x27 form
                # (5x wide=10, 2x=8: k_cf_switch@78/k_int_bitcount@72) and the 0x2f form (k_int64@230
                # /k_subgroup_ballot@72 wide=10; k_int_bitcount@98/k_int_arith@258 =8). The old flat
                # `-> 10` mis-lengthed the 8-byte forms and exposed the next op body as a spurious head.
                return 10 if (b4 & 0x02) else 8
            if b2 == 0x27:
                # remaining byte+2==0x27 forms (b3 != 0x80), for ALL dst regs incl 0x22.
                if b3 == 0x81 and b4 == 0x22:
                    return 10          # rt_transform_test (EXP-O2C)
                return 8               # quotient / wide-select. EXP-M4-01: also covers dst 0x22
                                       # (k_tex_atomic@386 `22 2f 27 31 84 06 87 02` = 8B).
            if b0 != 0x22:             # 0x22 keeps its baseline for the other ambiguous forms
                if (ln in (0x07, 0x0f) or b2 == 0x25) and (b3 & 0xf0) in (0x00, 0x80) \
                        and (b3 & 0x0f) != 0x04:
                    # EXP-M4-13 R4 (cascade 0x54): the store-EPILOGUE cmpsel is 8 bytes, not 10.
                    # When a device_store head (`e7 00`/`67 00`) sits at bytes +8..+9, the op is
                    # 8B; the old `-> 10` over-read it by 2, swallowing the store head and
                    # orphaning `54 00 00 0X 21 00` as a spurious 0x54 root desync. Narrow gate
                    # (store head follows); no genuine 10B cmpsel has e7/67-00 at +8..+9.
                    if off + 9 < len(buf) and buf[off + 8] in (0xe7, 0x67) and buf[off + 9] == 0x00:
                        return 8
                    return 10          # register-operand cmpsel / select. byte+3 is the
                                       # 2nd-source register descriptor (hi-nibble 0/8, e.g.
                                       # 0x80/0x83/0x87/0x07). A predicate-producing compare
                                       # that feeds a SEPARATE 0x05 psel (gsel4/dsel5: byte+3
                                       # low-nibble 4, e.g. 0x84) is the 6-byte form below.
        # fall back to the original per-dst-reg rules (dst r0..r3 forms). EXP-M4-01:
        # gate 0x02/0x32 on byte+2 being a REAL op-select (<= 0x3f). A real iminmax/
        # carry_gen always carries its op-select in byte+2 (<= 0x3f); when byte+2 > 0x3f
        # the leading `02`/`32` is NOT this op (it is a compact op or a resync landing),
        # so the old unconditional `-> 6` GREEDILY ate the following op -- e.g. `02 00 59
        # 0b 3e 07` ate a coord_madf in k_tex_array_cube and `02 00 af 01 54` ate an
        # fspecial in k_transcend. Leaving those LEN_UNKNOWN lets the real op tokenize.
        if b0 == 0x02:
            if 0 <= b2 <= 0x3f: return 6
            return 2 if b1 == 0x00 else LEN_UNKNOWN
                                       # EXP-M4-12 S4: `02 00` (b1==0x00, b2 not a real op-select) is a
                                       # 2-byte compact select/predicate helper (k_atomics@0x168 fence->
                                       # [2]->frame_marker; k_subgroup_shuffle@0x7c shuffle->[2]->iadd2).
                                       # A real 6-byte iminmax always carries its op-select (<=0x3f) in
                                       # byte+2; when it does not, the leading `02 00` is this compact op.
        if b0 == 0x12:
            if b2 == 0x3f:
                return 8               # compare/select op-select 0x3f feeding a final iadd2 accumulate
                                       # (EXP-M4-12 S3: k_uint_arith@0x190 `12 0d 3f 11 81 0c 05 00` =
                                       # 8B; the fminmax `-> 6` left `05 00` and exposed a spurious 0x54).
            return 14 if (b2 & 0x0f) == 0x0d else 6
        if b0 == 0x22: return 6 if (b2 & 0x0f) == 0x0e or b2 == 0x35 else 10
        if b0 == 0x32: return 6 if 0 <= b2 <= 0x3f else LEN_UNKNOWN
        # EXP-M4-13 R7 (desync-root 0x42 / getter_marshal): the dst>=r4 low-nibble-2 compact
        # op with byte+2==0x00 AND byte+3==0x00 is the exact dst>=r4 analogue of the dst-r0
        # `if b0==0x02: 0<=b2<=0x3f -> 6` rule above. Reached ONLY for dst>=r4 (0x42/0x52/0x62/
        # 0x82/0x92/0xa2/0xc2/0xe2), where instr_length previously returned LEN_UNKNOWN -> PURELY
        # ADDITIVE. b3==0x00 gate is load-bearing (b3!=0 forms are genuinely 8/10B tessellation
        # vertex ops). The now-lengthed bytes decode as the existing typed n2_op6 descriptor.
        # 346 ops named across 44 files, 0 files worse; roots 0x42(143)/0x82(79)/0xa2(58)/0x62(55).
        if b2 == 0x00 and b3 == 0x00 and off + 5 < len(buf):
            return 6                   # getter_marshal / n2_op6 dst>=r4 (EXP-M4-13 R7)
        return LEN_UNKNOWN             # new high-nibble dst, unrecognized op-select
    # ---- integer ALU family (EXP-0007, HW-validated by clean tokenization + splice) ----
    # Integer arithmetic is byte0 0x9f/0x1f (iadd/isub, bit7=srcA-negate) and 0xa7
    # (shift-right / bitfield-extract).  Within these groups the length is 10 bytes
    # (2-source form) when b1 bit0 == 1, and 12 bytes (3-source multiply-add / bfe
    # form) when b1 bit0 == 0.  EXP-0007: iadd/isub b1=0x01 -> 10B, imul/imad/ibfe
    # b1=0x00 -> 12B; splicing iadd's b1 bit0 -> the stream is mis-length'd and the
    # dispatch faults, confirming b1 bit0 is the format/length selector.
    if b0 in (0x9f, 0x1f):
        return 10 if (buf[off + 1] & 0x01) else 12
    # ---- CONVERT / SHIFT / BITFIELD / COUNT family (0x27 / 0xa7), EXP-0013 ----
    # 0x27 (base) and 0xa7 (=0x27|0x80) form a broad unary/convert/shift group whose
    # length is selected by byte+1 (the form field), NOT simply by b1 bit0. Observed
    # (HW-validated by clean tokenization of our own convert/shift kernels, EXP-0013):
    #   0xa7: b1==0x07 -> 8  (int/uint -> float convert)
    #         b1  odd  -> 10 (arithmetic shift-right immediate: a7 .. 10B)
    #         b1  even -> 12 (logical shift-r = bitfield-extract form: a7 .. 12B)
    #   0x27: b1==0x07 -> 10 (float/half -> int/uint convert)
    #         b1==0x05 -> 8  (popcount / integer unary reduce)   [EXP-0007]
    #         b1 in {0x00,0x10} -> 12 (bitfield-extract / shift prep stage)
    #         else     -> 8  (other unary)
    if b0 == 0xa7:
        b1v = buf[off + 1]
        if b1v in (0x07, 0x17):
            return 8                   # int/uint -> float/half convert (EXP-0013 HW; EXP-M4-01
                                       # adds b1==0x17, the sibling convert form: k_cvt_fi@68 /
                                       # k_cvt_half@48 `a7 17 54 .. 8e 60` are 8B, anchored by the
                                       # FOLLOWING `a7 07 54 ..` cvt_i2f. The old odd->10 rule ate
                                       # into that next op and exposed its tail as a spurious 0x54.
        if b1v in (0x04, 0x05):
            return 8                   # bit-count/scan: reverse_bits / find-MSB (EXP-0033 HW)
        return 10 if (b1v & 0x01) else 12
    if b0 == 0x27:
        b1v = buf[off + 1]
        # EXP-M4-13 R2 (n7_fence): shift-left-by-reg / bitfield-INSERT variable-operand form
        # (ibfins). byte+1 in {0x11,0x20} currently fell to the 8-byte else-branch, orphaning
        # the operand tail into an 0xf0 desync. The 12-byte operand form has byte+8 in {0xc0,0xf0}
        # (register/immediate operand descriptor); genuine 8-byte 0x27 ops never do. Narrowly
        # gated on byte+1 in {0x11,0x20} so popcount/ibitcount(0x05)/cvt(0x07) are untouched.
        if b1v in (0x11, 0x20) and off + 8 < len(buf) and buf[off + 2] in (0x54, 0x56) \
                and buf[off + 8] in (0xc0, 0xf0):
            return 12                  # ibfins (shl-by-reg / insert-var, EXP-M4-13 R2)
        if b1v == 0x07:
            return 10                  # float -> int convert (EXP-0013 HW)
        if b1v == 0x01:
            return 12                  # ROTATE-by-immediate funnel shift (EXP-0033 HW)
        if b1v in (0x00, 0x02, 0x10):
            return 12                  # bitfield-extract / shift-prep / matrix-load prep stage.
                                       # EXP-M4-01: byte+1==0x02 is the 12-byte matrix-load prep form
                                       # (k_matrix@58 `27 02 54 .. f0 11 01 00`, anchored iadd2..iadd2);
                                       # the old rule dropped it to the 8-byte else-branch and exposed the
                                       # tail `f0 11 01 00` as a spurious 0xf0 undecoded group.
        return 8                       # integer unary (popcount / reduce)
    # ---- native-half (fp16) float ALU (byte0 0x10, EXP-0033) ----
    # The 16-bit-destination sibling of the 0x09 float ALU (half/half2 arithmetic);
    # same length bit (byte+2 bit1) as 0x09/0x11.
    if b0 == 0x10:
        if buf[off + 2] & 0x02:
            # fp16 fma / 3-source. EXP-M4-10: same saturate/abs byte+4 polymorphism as
            # the 0x09 fp32 fma (8/10/12), so length off byte+4 low2 (guard 0 -> 8).
            b4 = buf[off + 4] if off + 4 < len(buf) else 0
            return (6 + 2 * (b4 & 0x03)) if (b4 & 0x03) else 8
        # EXP-M4-10 (ISA-2): the fp16 EXTENDED form (saturate output-clamp / negate / abs)
        # is 6 + 2*(byte+4 & 0x3), same as the 0x09 fp32 group. saturate(a+b) fp16 =
        # `10 03 1c 02 01 00 00 82` (8B, byte+7 bit1 clamp). Old flat rule dropped the tail.
        b4 = buf[off + 4] if off + 4 < len(buf) else 0
        return 6 + 2 * (b4 & 0x03)
    # ---- byte0 0x11: fp32->fp16 convert (EXP-0013) *and* NATIVE bfloat ALU (EXP-O2D) ----
    # This group is length-POLYMORPHIC on byte+1 (LOAD-BEARING, EXP-O2D):
    #   byte+1 == 0x03 : fp32->fp16 narrowing convert (cvt_f2h, `11 03 1c 81 00 c2`) = 6B.
    #                    (The float->bfloat convert `bfloat(x)` is ALSO byte+1==0x03 but 8B --
    #                    byte+4 0x00 half vs 0x01 bfloat; that 6-vs-8 convert sub-split is a
    #                    documented follow-up. bfloat ARITHMETIC is unambiguously byte+1 in {0x02,0x04}.)
    #   byte+1 in {0x02 (scalar), 0x04 (bfloat2-packed)} : NATIVE bfloat (brain-float16) ALU
    #                    (bf_alu) -- add/mul (opsel byte+2 0x1c/0x1d) = 8B, fma (opsel 0x1e,
    #                    byte+2 bit1 set) = 10B. HW-VALIDATED (splice byte+2 0x1c<->0x1d = add<->mul).
    # The OLD flat `8 if (byte+2 & 0x02) else 6` rule mis-lengthed every bfloat op (bf_add 0x1c -> 6,
    # bf_fma 0x1e -> 8) and desynced every bfloat kernel; disambiguate on byte+1, NOT byte+2 (cvt_f2h
    # and bf_add SHARE opsel byte+2 == 0x1c).
    if b0 == 0x11:
        b1v = buf[off + 1] if off + 1 < len(buf) else -1
        if b1v == 0x03:
            # EXP-M4-13 (n1_opselect): the 6-vs-8 convert sub-split. float->HALF (cvt_f2h,
            # byte+4 bit0 clear) = 6B; float->BFLOAT (cvt_f2bf, byte+4 bit0 set) = 8B. The
            # old flat `->6` mis-lengthed float->bfloat. (cvt_f2h `11 03 1c 81 00 c2` stays 6.)
            return 8 if (off + 4 < len(buf) and (buf[off + 4] & 0x01)) else 6
        if b1v in (0x02, 0x04):
            return 10 if (off + 2 < len(buf) and (buf[off + 2] & 0x02)) else 8   # bfloat add/mul (8) | fma (10)
        return 8 if (off + 2 < len(buf) and (buf[off + 2] & 0x02)) else 6         # legacy fallback
    # ---- fp16 PACK/CONVERT compact op (low-nibble-1, byte+1==0x01, byte+2==0x3c), 6B ----
    # EXP-M4-01 round-3: k_cvt_half@32 `31 01 3c 81 00 c2` (dst r3). The half<->int/float
    # pack-convert helper the mixed-precision `half(int)`/`int(half)` path emits; distinct from
    # the 0x11 bfloat/cvt group (byte+1 in {0x02,0x03,0x04}). High nibble = dst reg. Anchored 6B
    # (the following `27 07 54 ..` cvt_f2i tokenizes cleanly; a walk of the whole kernel closes).
    if (b0 & 0x0f) == 0x01 and (buf[off + 1] if off + 1 < len(buf) else -1) == 0x01 \
            and (buf[off + 2] if off + 2 < len(buf) else -1) == 0x3c:
        return 6
    # ---- GENERAL low-nibble-1 CONVERT + native bfloat ALU, dst r0..r15 (EXP-M4-13 n1) ----
    # Generalises the byte0==0x11 cvt_f2h/bf_alu length rule above to ALL dst regs (byte0
    # high nibble = dst). byte0==0x11 is already fully handled by the block above, so these
    # only fire for the other 15 dst regs.
    #   byte+3 hi-nibble 8 (==0x8x) & byte+2 lo-nibble 0xc -> single-source CONVERT:
    #        float->half 6B (byte+4 bit0 clear) / float->bfloat 8B (byte+4 bit0 set).
    #        Gated on byte+3==0x8x so it never claims a resync landing.
    #   byte+1 in {0x02,0x04} & byte+3 != 0x8x -> native bfloat ALU: bf_add/bf_mul 8B,
    #        bf_fma (byte+2 0x1e, bit1 set) 10B.
    if (b0 & 0x0f) == 0x01 and b0 != 0x11:
        _n1b1 = buf[off + 1] if off + 1 < len(buf) else -1
        _n1b3 = buf[off + 3] if off + 3 < len(buf) else -1
        if _n1b3 == 0x81 and off + 2 < len(buf) and (buf[off + 2] & 0x0f) == 0x0c:
            return 8 if (off + 4 < len(buf) and (buf[off + 4] & 0x01)) else 6   # convert ->bf 8 / ->half 6
        if _n1b1 in (0x02, 0x04) and _n1b3 != 0x81:
            return 10 if (off + 2 < len(buf) and (buf[off + 2] & 0x02)) else 8  # bf_fma 10 / bf_add,bf_mul 8
    # ---- low-nibble-3 group: 4-byte move/zero-extend, or 10-byte 0x27-form -------
    # byte0 0x13 (dst r0) zero-extend (uint->ushort->uint) is a 4-byte move (EXP-0013).
    # EXP-M4-01: the SAME low-nibble-3 group with byte+2==0x27 is a distinct 10-byte op
    # (k_tex_atomic@226 `33 8a 27 bf 10 02 00 00 00 00`, two anchored 10B ops; also in
    # k_transcend). High nibble = dst reg. Gate the 10-byte form on byte+2==0x27 so the
    # 4-byte zero-extend (byte0==0x13, byte+2 != 0x27) is unaffected.
    # low-nibble-3 group: byte0 HIGH nibble = destination register (r0..r15), like
    # the low-nibble-2 icmp/select and low-nibble-a icmp_pred families (rounds 1-2).
    # The DB previously hard-coded only 0x13 (dst r0) and left every higher-register
    # form UNDECODED. The byte+2==0x27 form is a 10-byte op (matrix/tex address prep,
    # EXP-M4-01 round-1); every OTHER form is the 4-byte zero-extend / id-compose / move
    # (0x13 zero-extend; 0x23 thread/threadgroup-id compose `23 00 00 01`, k_builtins_ids;
    # 0x43 call-site marker `43 00 00 01`; 0x73 mesh helper `73 00 00 01`, mesh_mesh@70).
    # HW-anchored: every occurrence is followed by a cleanly-tokenized run (round-3 census).
    # EXP-M4-13: byte0==0x03 (dst r0) now takes this rule TOO. Its two special forms are
    # already handled EARLIER: `03 02 ..` (byte+1==0x02, byte+2!=0x26) -> 2 (SFU range-reduction
    # WORD, line ~110) and `03 .. 26` -> 10 (fragment sample-id read, line ~193). Anything else
    # `03 ..` is the generic 4-byte compact move / 10-byte 0x27 addr-prep. The old `and b0 != 0x03`
    # exclusion left every dst-r0 form (155 corpus desyncs) unlengthed.
    if (b0 & 0x0f) == 0x03:
        return 10 if (off + 2 < len(buf) and buf[off + 2] == 0x27) else 4
    # ---- compact low-nibble-c move (byte0 0x2c), 4 bytes (EXP-M4-01) ------------
    # s_div@178 `2c 0c 00 02` (anchored between a falu3 and a falu2, gap = 4). A
    # compact move/immediate form; high nibble = dst reg. Gated on byte+1==0x0c so it
    # never swallows the get_sr (byte+3 lo-nibble 6) or a longer 0xNc op.
    if b0 == 0x2c and (buf[off + 1] if off + 1 < len(buf) else -1) == 0x0c:
        return 4
    # ---- 0xNc compact MOV-IMMEDIATE (byte0 low-nibble c), 2 bytes (EXP-M4-12 S2) --------
    # dst = byte0 high nibble; byte+1 = an 8-bit immediate/coefficient. Closes k_tex_lod@0x12
    # (`2c cd`, the gradient->LOD coefficient), k_tex_atomic@0x38 (`ac 01`), k_transcend_round@0x50
    # (`3c 01`). Exclusions are LOAD-BEARING (enumerated over all 0xNc boundary ops corpus-wide):
    #   byte+3 lo-nibble 6 -> get_sr (4B, handled at top);  byte+1==0x0c -> the `2c 0c` 4-byte move
    #   above;  byte+1==0xea -> rt_intersect.
    # EXP-M4-13 (rare_e5ad): byte+1==0x02 was BLANKET-excluded to protect the 6-byte `1c 02 00 ..`
    # tg_addr_compute. The mesh OBJECT stage loads a small grid-dim immediate==2 into r5..r9 as
    # `7c 02 | 8c 02 | 9c 02 | 5c 02 | 6c 02` (mesh_grid3d, uint3(2,2,2)) -- those ARE 2-byte mov_imm.
    # tg_addr is UNIQUELY byte0==0x1c with byte+2==0x00, so refuse only the `.. 02 00` signature
    # instead of all byte+1==0x02 (a mov_imm imm==2 is followed by the next op leader, byte+2 != 0x00).
    if (b0 & 0x0f) == 0x0c and (buf[off + 1] if off + 1 < len(buf) else -1) not in (0x0c, 0xea) \
            and not ((buf[off + 1] if off + 1 < len(buf) else -1) == 0x02
                     and (buf[off + 2] if off + 2 < len(buf) else -1) == 0x00) \
            and ((buf[off + 3] if off + 3 < len(buf) else -1) & 0x0f) != 0x06:
        return 2
    # ---- THREADGROUP-memory address / base compute (byte0 0x1c, `1c 02 00 ..`), 6B ----
    # EXP-M4-01 round-3: k_threadgroup@46 `1c 02 00 00 00 00`, bracketed between two low-nibble-3
    # threadgroup-id ops and the half_alu/threadgroup device_store; a 6-byte threadgroup-buffer
    # base/offset compute. Gate tightly on byte+1==0x02, byte+2==0x00 so it never claims the
    # 4-byte get_sr datapath form (byte+3 low-nibble 6) nor a resync-exposed 0x1c operand tail.
    if b0 == 0x1c and (buf[off + 1] if off + 1 < len(buf) else -1) == 0x02 \
            and (buf[off + 2] if off + 2 < len(buf) else -1) == 0x00:
        return 6
    # ---- packed-half2 ALU (byte0 low-nibble 0/8, byte+2==0x24), 6 bytes ---------
    # EXP-M4-01: k_half2_pack@32 `38 82 24 84 00 c8` / `30 83 24 85 00 08` (anchored
    # 6B each between loads and the store); k_half_arith@38 `18 84 24 85 00 08`. The
    # packed-half2 arithmetic op (distinct from the 0x10 scalar native-half ALU and
    # from the 0x18 b1==0x05 half_pack). High nibble = dst reg. byte+2==0x24 gate keeps
    # it off the texture sampler ops (0x30/0x90/0xb0, whose byte+2 is a texture opsel).
    if (b0 & 0x0f) in (0x00, 0x08) and b0 != 0x00 \
            and (buf[off + 2] if off + 2 < len(buf) else -1) == 0x24:
        return 6
    # ---- half combine/fma op (byte0 low-nibble 0, byte+2==0x39), 10 bytes (EXP-M4-12 S3) ----
    # k_half_arith@0x2c `20 05 39 04 10 02 1e 03 80 04` (dst r2). A genuine 10-byte half
    # `(x+y)*(x-y)+x*y`-style combine; DB had no rule (LEN_UNKNOWN). Distinct from the
    # low-nibble-9 byte+2==0x39 compact-accumulate (4B) above -- this is low-nibble 0.
    # Exclude the sampler byte0s (0x30/0x90/0xb0) and the 0x00 stop.
    if (b0 & 0x0f) == 0x00 and b0 not in (0x00, 0x30, 0x90, 0xb0) \
            and (buf[off + 2] if off + 2 < len(buf) else -1) == 0x39:
        return 10
    # ---- FLOAT SPECIAL-FUNCTION unary (byte0 0x2f / 0xaf, 10B, EXP-0013) ----
    # exp2 (0xaf), log2 (0x2f) and the round family floor/ceil/trunc/rint (0x2f, with
    # the round-mode in byte+8) are single 10-byte ops in COMPUTE. (NB: in vertex/
    # fragment code 0x2f/0x3f/0xaf are the interp/tex/deriv groups -- different, and
    # not tokenized here; EXP-0008.)
    if b0 in (0x2f, 0xaf):
        return 10
    # ---- RAY-TRACING transform / box-test companion op (rt_transform_test, EXP-O2C) ----
    # byte0 low-nibble 0x2 (high nibble = dst reg), full signature byte+2==0x27, byte+3==0x81,
    # byte+4==0x22, 10 bytes. The ray-vs-node coordinate transform / AABB slab-test ALU executed
    # INSIDE the traversal loop, distinct from the dedicated rt_intersect primitive. Gate on the
    # WHOLE `27 81 22` signature (NOT just byte+2==0x27) -- the compute texel-address / coordinate
    # ALU is also `Xx 81 27 ...` (low-nibble-2, byte+2==0x27) but has byte+3==0x80 / byte+4!=0x22,
    # so the loose byte+2-only gate spuriously names that compute residual as rt_transform_test
    # (EXP-0040 census caught it in k_int_arith/k_cf_switch/etc). Place BEFORE the 0x02/0x32
    # handlers (which return unconditionally) so a dst-reg nibble of 0/3 doesn't mis-length it.
    if ((b0 & 0x0f) == 0x2 and off + 4 < len(buf)
            and buf[off + 2] == 0x27 and buf[off + 3] == 0x81 and buf[off + 4] == 0x22):
        return 10                      # rt_transform_test (EXP-O2C, full `27 81 22` signature)
    if b0 == 0x02:
        return 6                       # integer min/max (signed/unsigned)
    if b0 == 0x12:
        # byte0 0x12 is float min/max (6B, byte+2 == 0x1e) OR the integer
        # compare-and-select producer (14B, byte+2 low-nibble == 0x0d, e.g. 0x1d).
        return 14 if (buf[off + 2] & 0x0f) == 0x0d else 6
    # ---- CONTROL FLOW / PROGRAM STRUCTURE (EXP-0010, HW-validated lengths) ----
    # 0x0a: integer compare -> per-lane execution predicate (feeds an early
    #       return / break / continue). 6-byte form; the compare immediate is at
    #       byte+3 and the condition SENSE is in byte0/byte+1 (HW: splicing byte0
    #       0x0a<->0x02 inverts >= vs <, swapping which lanes execute -- EXP-0010).
    # 0x0a and its dst-register siblings (0x1a,0x2a,0x3a,0x9a,0xca,...): the 6-byte
    # integer compare -> per-lane execution PREDICATE. Exactly like the low-nibble-2
    # icmp/select family, byte0's HIGH nibble is the destination (predicate) register,
    # so the DB must key on the LOW nibble == 0xa, not the whole byte. The old
    # `b0 == 0x0a` rule left every dst>0 form (2a/3a/1a/9a/ca) UNDECODED, desyncing
    # the compare-heavy divergent kernels (k_tex_atomic, k_uint_arith, k_int64). byte+2
    # is the compare op-select (<= 0x3f: 0x22/0x23/0x25/0x2b/0x35/0x39/0x3a observed);
    # length is uniformly 6. EXP-M4-01 census (anchored: every 0x?a is followed by a
    # cleanly-tokenized if_push/psel/imad, byte-identical in shape to the 0x0a form).
    if (b0 & 0x0f) == 0x0a:
        # gated on byte+2 being a real compare op-select (<= 0x3f); a byte+2 > 0x3f means
        # this `Xa` is not an icmp (compact op / resync landing) -- do not greedily length 6.
        b2a = buf[off + 2] if off + 2 < len(buf) else -1
        if 0 <= b2a <= 0x3f:
            return 6
    # 0x05 / 0x16: conditional SELECT (branchless if / ternary) d = pred?A:B, 4B.
    #       Cleanly tokenizes gsel4 (0x05) and dsel5 (0x16). The compare feeding
    #       it is byte0 0x02/6B (shares length with iminmax).
    if b0 in (0x05, 0x16):
        return 4
    # 0x85: psel HIGH-predicate-register variant (0x05 | 0x80), 4 bytes (EXP-M4-12 S3).
    # k_uint_arith@0x11c `85 00 20 80` (tail `20 80`); parallels k_int64@0x66 `05 00 20 80`.
    # Gated on the `20 80` tail so it never claims an unrelated 0x85 operand byte.
    if b0 == 0x85 and off + 3 < len(buf) and buf[off + 2] == 0x20 and buf[off + 3] == 0x80:
        return 4
    # 0x0f: control-flow / execution-mask group; sub-opcode in byte+1. The JUMP
    #       (loop back-edge / block skip) is `0f 00 54 <off6> 00` = 10 bytes with a
    #       SIGNED byte-relative offset (EXP-0010 E6, HW-validated: a -44 back-edge
    #       in prodloop; zeroing it -> infinite-loop hang, off-boundary targets
    #       fault). Other 0f sub-ops (mask push/pop/reconverge, mov-under-mask) are
    #       variable-length and a documented follow-up -> left UNKNOWN so they are
    #       never mis-tokenized.
    if b0 == 0x0f:
        b1 = buf[off + 1] if off + 1 < len(buf) else -1
        if b1 == 0x00:
            return 10                  # JUMP: unconditional PC-relative (loop back-edge /
                                       # block skip), EXP-0010 / RT-ISA-FIX HW
        if b1 == 0x01:
            return 10                  # CONDITIONAL jump: masked PC-relative branch (the
                                       # `else`-skip / loop-exit guard). Same 10-byte shape as
                                       # 0f 00; byte+1=0x01 = take-only-if-active. RT-ISA-FIX HW:
                                       # splicing byte+1 0x01->0x00 (cond->uncond) made every lane
                                       # skip the loop body -> all-zero output.
        if (b1 & 0x0f) == 0x05:
            # 0f 05 = direct CALL (14B) when the 0x8f link register appears at byte+4,
            # else the execution-mask PUSH (4B). EXP-0035 / RT-ISA-FIX. (byte+6 is 0x54 or
            # 0x56 depending on the cache/last-use bit, so gate on byte+4==0x8f only.)
            # EXP-M4-13 R4 (rt_traversal): GENERALIZED from b1==0x05 to any byte+1 low-nibble
            # 5 -- a non-zero HIGH nibble selects a predicate/condition register (if_push_pred),
            # the 4-byte PUSH the RT-query / integer simd-prefix kernels emit before a 0f 01
            # jump_cond. High-nibble forms are gated on byte+2 in {0x54,0x56} (CF marker) so a
            # stray 0f X5 operand byte can never mis-length. The plain 0x05 keeps EXACT prior
            # behavior (fldexp `b1==0x15,b2==0x80 -> 6` is already handled earlier).
            if b1 != 0x05:
                if _b2 in (0x54, 0x56):
                    return 4           # if_push_pred (predicate-register PUSH, EXP-M4-13 R4)
                return LEN_UNKNOWN     # unrecognized 0f X5 high-nibble form
            if off + 4 < len(buf) and buf[off + 4] == 0x8f:
                return 14              # direct CALL (EXP-0035 HW)
            return 4                   # execution-mask PUSH (if-enter). RT-ISA-FIX FIX: the
                                       # non-call push is 4 bytes, not 8 -- clean tokenization of
                                       # our own (HW-correct) for/while/nested CF kernels requires 4
                                       # (`0f 05 54 <lvl>` then the next op); the old 8 desynced the
                                       # loop head. The 14-byte CALL keeps its 0x8f gate.
        if b1 == 0x80:
            return 6                   # computed-target branch (0f 80): indirect CALL leader
                                       # (EXP-0035) and the break-to-loop-exit form; 6B.
        if b1 == 0x06:
            return 6                   # reconverge / mask-pop (0f 06 ..; block/loop end).
                                       # RT-ISA-FIX HW: corrupting byte+1 0x06->0x00 -> CMDBUF_ERROR.
        if b1 == 0x04:
            return 4                   # inner exec-mask op (0f 04 04 <lvl>): 4 bytes, anchored by the
                                       # following 0f 01 jump_cond in cf_big's nested while+continue.
                                       # RT-ISA-FIX (inferred, single occurrence -- byte+2==0x04 not 0x54).
        return LEN_UNKNOWN
    # ---- FUNCTION RETURN (byte0 0x8f, EXP-0035) ----
    # Control-flow family (low nibble 0xf) with the link/return high bit; 4 bytes,
    # byte+2 == 0x54 CF marker; no encoded target (HW link register / CF stack).
    if b0 == 0x8f:
        return 4
    # ---- CALL-SITE / FRAME-SETUP marker (byte0 0x43, EXP-0035; re-scoped EXP-0030) ----
    # `43 00 00 01` precedes every out-of-line CALL (plain compute kernels too), and
    # `43 00 06 xx` is the non-leaf-frame prologue variant. NOT a mesh-unique op --
    # mesh merely reuses it for helper-subroutine calls. 4 bytes.
    if b0 == 0x43:
        return 4
    # ---- integer min/max CHAINED-operand variant / shift-sign-extend helper (0x22) ----
    # EXP-0033: 0x22 (= 0x02|0x20) is length-polymorphic on byte+2 like 0x12 -- the
    # min3/max3/clamp chained min/max op is 6 bytes (byte+2 low-nibble == 0x0e, the
    # 0x1e iminmax op byte); other 0x22 forms (shift / sign-extend helpers) are 10.
    if b0 == 0x22:
        b2 = buf[off + 2] if off + 2 < len(buf) else -1
        # 6 = min3/max3/clamp chained min/max (byte+2 lo-nibble 0x0e) OR the u64
        # carry-generate sibling of 0x32 (byte+2==0x35, EXP-0038); else 10 (shift helper).
        return 6 if ((b2 & 0x0f) == 0x0e or b2 == 0x35) else 10
    # (the register/64-bit shift-amount PREP stage 0x2b/0x3b/0x5b/0x8b is handled in
    #  the low-nibble-0xb block above, gated on byte+2 low-nibble e/f -- EXP-0033.)
    # ---- SIMD-group MATRIX multiply-accumulate (byte0 0xcf, 12B, EXP-0022) ----
    # The dedicated 8x8 cooperative-matrix MAC (simdgroup_multiply_accumulate).
    # 12 bytes, byte+2 == 0x56 (single op) / 0x54 (tiled, MPP matmul2d). A single
    # 0xcf executes one whole 8x8x8 tile MAC; simdgroup_load/store are ordinary
    # 0x67/0xe7 memory ops, not matrix instructions. HW-validated.
    if b0 == 0xcf:
        return 12                      # matrix_mac (EXP-0022 HW)
    # ---- HARDWARE RAY TRACING (EXP-0023, HW-validated) ----
    # Dedicated ray-intersection instruction: byte0 LOW nibble 0x4 (byte0 HIGH nibble =
    # result/destination register), byte+1 == 0xea (a constant intersect sub-opcode).
    # 8 bytes. Emitted (exactly twice: traverse + result-read) by EVERY raytracing::
    # intersector / intersection_query kernel, and ABSENT from a hand-written software
    # ray/triangle (Moller-Trumbore) loop -> proves a dedicated HW intersect op. The
    # 0xea gate keeps it from colliding with unrelated low-nibble-4 operand bytes.
    if (b0 & 0x0f) == 0x4 and off + 1 < len(buf) and buf[off + 1] == 0xea:
        return 8                       # rt_intersect (EXP-0023 HW)
    # Dedicated acceleration-structure / ray-data load: byte0 0xdf, a memory-family
    # sibling of 0x67/0xe7 (byte+2 == 0x54), 14 bytes. Loads BVH-node / ray / stack
    # data during traversal; present in every RT kernel, absent from the software loop.
    if b0 == 0xdf:
        return 14                      # rt_as_load (EXP-0023)
    # Dedicated ray-data / traversal-stack memory op (rt_ray_mem, EXP-O2C): byte0 0x5f, the
    # memory-family low nibble 0xf sibling of 0xdf/0x67/0xe7 (byte+2 == 0x54/0x56 memory marker),
    # 14 bytes. Store/spill side of the 0xdf AS-load; fetches/spills the ray struct + per-node
    # traversal-stack state and carries the ray_data payload copy-in/out. 12-28 per RT kernel,
    # ABSENT from a hand-written software triangle loop.
    if b0 == 0x5f:
        # EXP-M4-13 R4 (rt_traversal): byte+1-gated length model. byte+1 is the addressing
        # sub-op; byte+2 an address-space/cache mode. The old blunt `byte+2 in {0x54,0x56}
        # -> 14` mislengthed two byte+1 sub-ops and missed two address modes.
        _r5b1 = buf[off + 1] if off + 1 < len(buf) else -1
        _r5b2 = buf[off + 2] if off + 2 < len(buf) else -1
        if _r5b2 == 0x83:
            return 14                  # b_alu14 sibling (byte+2==0x83 int/simd ALU)
        if _r5b1 == 0x11 and _r5b2 == 0x54:
            return 6                   # rt_ray_mem_short (ALL 92 corpus occurrences back-to-back at 6)
        if _r5b1 == 0x10 and _r5b2 == 0x54:
            return 12                  # rt_ray_mem_ldidx (ALL 32 corpus occurrences back-to-back at 12)
        if _r5b1 == 0x02 and _r5b2 in (0x04, 0x54, 0x56, 0x64):
            return 14                  # rt_ray_mem (0x04 continuation byte-identical to the 0x54 form)
        if _r5b2 in (0x54, 0x56):
            return 14                  # rt_ray_mem fallback (preserves prior behavior for other byte+1)
    # ---- VERTEX-stage varying / [[position]] store (byte0 0x57, EXP-0037) -----
    # Traditional VS output store to the UVS / vertex-parameter buffer that the FS
    # iter op interpolates (EXP-0029). Memory-family opcode (low-nibble 7); byte+3 =
    # source GPR, byte+4 = destination output slot. 8 bytes. HW-splice-proven.
    if b0 == 0x57:
        return 8                       # vary_store (EXP-0037 HW)
    # ---- NON-LEAF FUNCTION FRAME PROLOGUE (byte0 0x6f, EXP-0038) --------------
    # Establishes the per-thread scratch frame a non-leaf callee uses to save its
    # link register around inner calls. `6f 03 04 00 00 20`. 6 bytes.
    if b0 == 0x6f:
        return 6                       # frame_prologue (EXP-0038 HW role)
    # ---- FOUR-BYTE 0x60 FORM (byte0 0x60, RT-1a-FIX item 4) -------------------
    # `60 00 00 00` appeared instruction-aligned right after the entry get_sr in
    # one prior A18 high-register-pressure kernel. No prior length rule ->
    # tokenization halted there. RT-1a-FIX HW-validated the length is 4: with 0x60->4
    # the following 10-byte iadd2 (`9f 11 54 ...`) aligns cleanly, and splicing the
    # op's byte+3 (=+7) to 0xff FAULTS (it is this instruction's last, live byte)
    # while byte0/+1/+2 are runtime-inert for the computation. 4 bytes.
    if b0 == 0x60:
        # RT-1a-FIX HW: exact `60 00 00 00` form is 4B (byte+3 live). EXP-M4-01.
        # EXP-0041: absent from nine M4 own mains, including 208--576 B scratch;
        # the historical spill_frame_marker name is not a universal semantic rule.
        # round-3: the `60 00 <nonzero>` form is a 2-byte compact frame/scope marker that
        # PRECEDES a threadgroup-atomic store (`60 00` + `e7 02 54..` in k_atomics_tg@26, which
        # matches the bare `e7 02 54..` threadgroup store in the isolated tg_store) or a divergent
        # control-flow block (`60 00` + `1b 00 00 00` in k_atomics@362). Both resync 8 clean ops
        # (lenprobe). Gate on byte+2: ==0x00 keeps the spill marker at 4.
        return 4 if (off + 2 < len(buf) and buf[off + 2] == 0x00) else 2
    # ---- u64 CARRY-GENERATE (byte0 0x32, EXP-0038) ---------------------------
    # Unsigned-overflow compare (integer compare/min-max family, base 0x02|0x30;
    # byte+2==0x35, byte+4==0x22) detecting the carry-out of the low-word add in a
    # 64-bit ADD chain. Its predicate feeds a 0x05 psel that adds carry into the high
    # word. 6 bytes. HW+splice-validated.
    if b0 == 0x32:
        return 6                       # carry_gen (EXP-0038 HW)
    # ---- HALF-LANE PACK (byte0 0x18, EXP-0038) -------------------------------
    # Assembles the two fp16 lanes of a half2 (native-half 0x10 ALU result) into one
    # packed 32-bit register before the device store. `18 05 18 03`. 4 bytes. byte0
    # high nibble = dst reg nibble (0x08/0x18/0x28/0x38 = dst r0..r3). HW round-trip
    # proven. GATED on the validated compute shape (byte+1==0x05, byte+2 = half_alu
    # result reg with high-nibble 1) so it never mis-lengths the 6-byte high-register
    # sibling form (byte+2==0x24, a documented follow-up) NOR spuriously names operand
    # bytes reached via census resync (`18 05 e7 00` etc.). EXP-0039 regression-tested:
    # blanket 0x18->4 named operand bytes as half_pack and dropped k_cvt_half 78->76.
    if (b0 == 0x18 and off + 2 < len(buf)
            and buf[off + 1] == 0x05 and (buf[off + 2] & 0xf8) == 0x18):
        return 4                       # half_pack (EXP-0038 HW; shape-gated EXP-0039)
    # ---- COMPACT half move/pack `18 00` (byte0 0x18, byte+1==0x00), 2 bytes -------
    # EXP-M4-01: a 2-byte compact half move that immediately follows every `27 04`
    # convert in the software texture-coordinate address path (k_tex_atomic @264/@736,
    # k_iso_texatomic @234 where the very next op is a plain iadd2, forcing the 2-byte
    # boundary). Distinct from half_pack (byte+1==0x05) and half2 ALU (byte+2==0x24).
    if b0 == 0x18 and off + 1 < len(buf) and buf[off + 1] == 0x00:
        return 2                       # compact half move/pack (EXP-M4-01)
    # Sibling compact 2-byte moves in the same class (high nibble = dst reg, byte+1 =
    # source): `00 8c` precedes a `27 04` convert in the texture-coord path (k_tex_atomic
    # @338/@810); `80 04` precedes a store/convert in the half & uint paths (k_half_arith
    # @52, k_uint_arith @106). Anchored 2B by the following full op. EXP-M4-01.
    if b0 == 0x00 and off + 1 < len(buf) and buf[off + 1] == 0x8c:
        return 2                       # compact move (EXP-M4-01)
    if b0 == 0x80 and off + 1 < len(buf) and buf[off + 1] == 0x04:
        return 2                       # compact move (EXP-M4-01)
    # ---- native-half HIGH-HALF float ALU (low-nibble-8, EXP-M4-13 R2 n8_eight) ----
    # The high-16-bit-half sibling of the 0x10 low-half half ALU (the .y lane of a packed
    # half2). byte+2 = the SAME float op-select as 0x09/0x10 (0x1c hadd / 0x1d hmul / 0x1e hfma /
    # 0x26 hmul_coord / 0x2e hfma_coord); length model identical: 6 + 2*(byte+4 & 3). The
    # (byte+4 & 0x7c)==0 gate is LOAD-BEARING -- it refuses RT-getter / tessellation desync
    # landings whose byte+2 coincidentally hits the op-select set. Placed AFTER the committed
    # 0x18 half_pack / `18 00` 2-byte rules so those still win. byte+2==0x24 packed-half2 is
    # handled by the earlier packed-half2 rule.
    if (b0 & 0x0f) == 0x08 and off + 4 < len(buf) \
            and buf[off + 2] in (0x1c, 0x1d, 0x1e, 0x26, 0x2e) and (buf[off + 4] & 0x7c) == 0:
        return 6 + 2 * (buf[off + 4] & 3)
    # ---- COORDINATE / interpolation fused-mul ALU LEADER (0x2e/0x3e, EXP-0037) -
    # 10-byte form `2e/3e b1 23 a0 42 00 00 06 02 00` in the texture coordinate /
    # cube-array normalized-coord math. GATE TIGHTLY on byte+2==0x23 (the `23 a0 42`
    # coordinate signature) so it never fires on bare low-nibble-e resync bytes;
    # exclude 0x0e (stop, matched above). Distinct from the byte+2 op-select 0x26/0x2e
    # case (a low-nibble-9 float op) handled in the 0x09 block. EXP-0037 inferred.
    if (b0 & 0x0f) == 0x0e and b0 != 0x0e and off + 2 < len(buf) and buf[off + 2] == 0x23:
        return 10                      # coord_madf (EXP-0037)
    # ---- 16-byte texture-READ SAMPLER variant (trailing operand word), EXP-M4-12 S2 ----
    # k_tex_atomic@0x3c4 `90 00 17 01 a0 02 80 00 02 00 ...` -- the texture-read sampler op
    # under register pressure carries a trailing 6-byte operand word, making it 16 bytes; the
    # 10-byte fallback below over-read it as 10 and left `00 20 00 00 00 00` (byte0 0x00, never a
    # real leader) as residue. The plain read has byte+4==0x00 (10B via the companion path);
    # this variant is uniquely byte+1==0x00 && byte+2==0x17 && byte+4==0xa0.
    if b0 in (0x30, 0x90, 0xb0) and off + 4 < len(buf) and buf[off + 1] == 0x00 \
            and buf[off + 2] == 0x17 and buf[off + 4] == 0xa0:
        return 16
    # ---- STANDALONE texture SAMPLER OP fallback (0x30/0x90/0xb0, EXP-0037) -----
    # A bare 10-byte sampler op (byte0 = result_reg<<4 | 0) NOT preceded by a matched
    # tex_sample companion -- only reachable via resync. Gate tightly on byte+2 in the
    # texture-variant set so it never over-claims a plain 0x90/0x30 operand byte. This
    # is belt-and-suspenders for census robustness; the companion-gate widening above is
    # the primary closer. EXP-0037.
    if b0 in (0x30, 0x90, 0xb0) and off + 2 < len(buf) and buf[off + 2] in (
            0x00, 0x04, 0x07, 0x09, 0x13, 0x17, 0x1b, 0x20, 0x21,
            0x29, 0x39, 0x53, 0x79, 0x80, 0x97):
        return 10                      # standalone sampler op (EXP-0037 fallback)
    # ---- CUBE-ARRAY normalized-coordinate constant/reciprocal load (0xf0, EXP-M4-01) ----
    # `f0 c0 04 00` (4B) in the cube/cube-array coordinate math (k_tex_array_cube@48): a
    # small constant/reciprocal-of-major-axis load feeding the face-select coord_madf chain.
    # Gate tightly on the whole `f0 c0 04` signature so it never claims an operand-tail 0xf0
    # (e.g. the `f0 11 01 00`/`f0 13 01 00` matrix-load / ibfe tails absorbed by their upstream
    # 0x27 ops in round-1) reached via resync.
    if b0 == 0xf0 and off + 2 < len(buf) and buf[off + 1] == 0xc0 and buf[off + 2] == 0x04:
        return 4
    # ---- EXP-M4-13 R4 (rt_traversal): low-nibble-f 14-byte int/simd ALU, byte+2==0x83 ----
    # A distinct opcode from iadd2/imad (byte+2==0x54). High-nibble 0x3f/0x7f (the 0x5f form
    # is handled in the 0x5f block above). Additive: 0x3f/0x7f with byte+2==0x83 reached None.
    if b0 in (0x3f, 0x7f) and off + 2 < len(buf) and buf[off + 2] == 0x83:
        return 14                      # b_alu14_c83 (EXP-M4-13 R4)
    # ---- EXP-M4-13 R4 (lenhi): 0xef high-register integer address/index ALU, 10B ----
    # byte0 0xef is a low-nibble-f integer address/index ALU op DISTINCT from iadd2/imad
    # (0x1f/0x9f). Uniformly 10 bytes, does NOT follow the iadd2 `b1 bit0` length selector.
    # Placed LAST so every specific low-nibble-f handler (0x1f/0x9f/0x2f/0xaf/0x5f/0xdf/
    # 0x6f/0x8f/0xcf/0x0f) wins first; none claim 0xef. Additive: 0xef reaches here as None.
    if b0 == 0xef and off + 2 < len(buf) and buf[off + 2] == 0x54:
        return 10
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
    # EXP-M4-13 R2 (n9_falu, byte-diff): opsel 0b110 = fma (6-byte continuation / coord form),
    # 0b111 = fmul_interp (FRAGMENT perspective-correct interpolation finalize multiply attr*1/w).
    0b110: "fma",          # byte-diff (n9): dot-product continuation / coord fused mul-add
    0b111: "fmul_interp",  # byte-diff (n9): fragment perspective-divide finalize multiply
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
    """Decode the 8-bit packed minifloat srcB immediate (falu2i).

    GUARDED to the HW-validated domain (RT-1a-FIX, item 5). b1 must be a byte and
    the exponent field e = bits[7:4] must be >= 8 (the documented representable
    range {0, 1/32 .. 30}). e < 8 is NOT a minifloat: that byte range is the float
    UNIFORM-REGISTER source overload (see the `falu2_uni` descriptor) -- RT-1a-FIX
    re-validated on hardware that `09 0d 14 01 80 c0` (e=0) reads a *uniform
    register* (a=10, u=7 -> 17; u=100 -> 110), NOT a + imm_decode(0x0d) ~= 10.0009.
    Extrapolating the minifloat formula into e<8 produced exactly that bogus value,
    so we raise instead (the old code returned it silently)."""
    if not (0 <= b1 <= 0xff):
        raise ValueError(f"imm_decode: b1={b1:#x} is not an 8-bit byte (0..255)")
    e = (b1 >> 4) & 0xf
    m = (b1 >> 1) & 0x7
    if e < 8:
        raise ValueError(
            f"imm_decode: b1={b1:#x} exp={e} < 8 is outside the packed-minifloat "
            f"domain -- this encoding is a falu2_uni uniform-register source "
            f"(RT-1a-FIX HW-validated), not an immediate.")
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

# ------------------------------------------------------------------------------
# INSTRUCTION DESCRIPTORS -- loaded from db.json, the SINGLE SOURCE OF TRUTH.
#
# This module used to carry its own `DB = [...]` literal, a second copy of the
# same descriptors that db.json holds. The two drifted: commit cf544b4d applied
# the EXP-0099 falu2/falu2i register-field correction (7-bit index -> 6 bits
# plus a HW-tested-inert top bit) and 13 semantics corrections to db.json only,
# so the assembler/disassembler kept decoding against the superseded model
# while docs/isa/encoding-tables.md and docs/isa/agx3.xml described the
# corrected one. Round-trip still passed, because both models tokenize the same
# bytes -- which is exactly why the drift went unnoticed and is exactly the
# failure mode docs/evidence-classification.md warns about.
#
# db.json is now authoritative for everyone: this module, gen_encoding_tables.py
# and gen_agx3_xml.py all read it. Edit db.json, never a copy.
# ------------------------------------------------------------------------------

import json as _json
import os as _os

_DB_JSON = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "db.json")

with open(_DB_JSON) as _f:
    _DB_DOC = _json.load(_f)

# match entries are lists in JSON; the codec below unpacks them as
# (start, width, value) triples, which works for lists as well as tuples.
DB = _DB_DOC["instructions"]

ISA = _DB_DOC.get("isa")
PARCEL_BYTES = _DB_DOC.get("parcel_bytes")
LENGTH_RULE = _DB_DOC.get("length_rule")
SCOREBOARD_MODEL = _DB_DOC.get("scoreboard_model")
LENGTH_RULE_GAPS = _DB_DOC.get("length_rule_gaps")

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
                    "function of byte0 (group) + a per-group length bit. Float 0x09 "
                    "uses byte+2 bit1; integer arithmetic (0x9f/0x1f/0xa7) uses "
                    "byte+1 bit0 (1=10B 2-src, 0=12B 3-src mul-add / bitfield). "
                    "EXP-0007 HW-validated.",
            "byte0_table": {
                "0x0e": 4, "lownibble_0xC": 4,
                "0x67/0xe7": "14  [load/store: device, threadgroup (byte+1 bit1=0x02) "
                             "and constant all share this opcode pair -- EXP-0012]",
                "0x07 (+ byte+2==0x54)": "6  [THREADGROUP/EXECUTION BARRIER "
                             "(threadgroup_barrier): 07 04 54 <mem_scope> <flags> 00. byte+3 = "
                             "fenced memory scope 0x61 threadgroup / 0x85 device. The ONLY explicit "
                             "ordering op in compute -- device load/store/atomic/texture are NOT "
                             "scoreboard-waited (HW register interlock). EXP-0025 HW/splice-proven]",
                "lownibble_0x9": "6, or 8 if (byte[+2] & 0x02), or 4 if byte+2 in {0x18,0x38}  [float ALU; "
                             "byte+2 in {0x18,0x38} = compact 4-byte float accumulate (falu_acc), EXP-0025 / "
                             "RT-1a-FIX -- NOT a wait; 0x18 vs 0x38 is a source cache/last-use hint. "
                             "srcB-imm form (bit39=1): byte+1 exp>=8 (bit15=1) = minifloat immediate (falu2i), "
                             "exp<8 (bit15=0) = UNIFORM-register source (falu2_uni), RT-1a-FIX. "
                             "byte+2==0x25 (still 6B) = transcendental ESTIMATE SEED (byte0 0x29): "
                             "byte+3 0x09 rcp / 0x0b rsqrt / 0x0d sqrt estimate, ~8 mantissa bits, "
                             "the Newton-Raphson seed for precise 1/x/rsqrt/sqrt, EXP-0026]",
                "0x2f/0xaf": "10  [float SPECIAL-FUNCTION UNIT (SFU): one op computes rcp/rsqrt/exp2 "
                             "(byte0 0xaf) | round/sqrt/log2 (byte0 0x2f), function = byte+1 "
                             "(0x00 rcp|round / 0x01 rsqrt|sqrt / 0x02 exp2|log2). exp/log/pow/div "
                             "compose these. fast-math emits single ops; precise 1/x/sqrt/div refine "
                             "with Newton-Raphson. EXP-0013 (exp2/log2/round) + EXP-0026 (rcp/rsqrt/sqrt)]",
                "lownibble_0xB": "4 if (byte+2==0x01 and byte+3==0x08) [uniform_mov: "
                                 "uniform-reg -> GPR, EXP-0020]; else 10 [float unary / "
                                 "integer and/or/xor]",
                "0x02": "6  [integer min/max | compare-for-select]",
                "0x12": "6 float min/max, or 14 if (byte+2 & 0x0f)==0x0d [int compare]",
                "0x9f/0x1f": "10 if (byte+1 & 1) else 12  [integer add/sub | mul-add]",
                "0xa7": "10 if (byte+1 & 1) else 12  [integer shift-r | bitfield]",
                "0x27": "8  [integer unary / popcount]",
                "0x0a": "6  [integer compare -> execution predicate (branch/return)]",
                "0x05/0x16": "4  [conditional select (branchless if/ternary)]",
                "0x0f": "EXECUTION-MASK family, byte+1 sub-op (RT-ISA-FIX): 0x00 jump 10 / 0x01 "
                        "jump_cond(else,loop-guard) 10 / 0x05 if_push 4 (or 14 if byte+4==0x8f = direct CALL) / "
                        "0x06 pop_reconverge 6 / 0x80 call_indirect(computed branch) 6 / 0x04 mask_op 4",
                "0x07 (byte+2 in {0x00,0x02})": "4  [compute memory/scoreboard fence around calls & "
                        "divergent CF (07 22 02 00 pre-call; 07 02/00 00 CF). RT-ISA-FIX HW]",
                "lownibble_0x5 + byte+1==0x80 + byte+2==0x0c":
                        "14  [TEXTURE sample / read: 4B coord/result companion + 10B "
                        "sampler op (0xb0/0x90). EXP-0016 HW-validated]",
                "0xd7": "16  [TEXTURE write (memory-family store). EXP-0016 HW-validated]",
                "0x37": "8 if byte+2==0x56 [quad reduce/scan, EXP-0018]; else 10 "
                        "[derivative / quad-difference dfdx/dfdy/fwidth, EXP-0016]",
                "0xbf/0x3f/0xb7 (+ byte+2==0x56)":
                        "8  [SUBGROUP/QUAD reduce & prefix-scan: bit3=scope(1 simd/0 quad), "
                        "bit7+byte+1=op, byte+7=datatype/shape. SIMD width 32. EXP-0018 HW]",
                "0x47/0xc7": "10  [SUBGROUP/QUAD shuffle & broadcast: bit7=dir, byte+1=simd/"
                        "quad/rotate, byte+6=(lane<<1), byte+2 0x54/0x56 (cache bit, RT-ISA-FIX). EXP-0018 HW]",
                "0x17": "10  [simd_ballot (byte+1 low-nib 7: 0x07 active-mask/any/all, 0x17 ballot(pred), "
                        "RT-ISA-FIX) | unpack_convert (byte+1 low-nib 4). EXP-0018/0033 HW]",
                "0x67 (byte+1==0x11)": "14  [device ATOMIC RMW (elected-lane), op at byte+12. "
                        "EXP-0018 HW]",
                "0x67 (byte+1==0x01)": "14  [standalone ATOMIC exchange/cmpxchg/indexed, op at "
                        "byte+12. EXP-0018 HW]. Atomics are native single ops, NOT CAS loops.",
                "0xcf": "12  [SIMD-group MATRIX multiply-accumulate: one full 8x8x8 cooperative-"
                        "matrix tile MAC d=a*b(+c). DEDICATED matrix HW. byte+2 0x56 single / 0x54 "
                        "tiled; byte+7=C src reg; byte+11 bit0=accumulate-enable. simdgroup_load/"
                        "store are ordinary 0x67/0xe7 memory ops, NOT matrix ops. EXP-0022 HW]",
                "lownibble_0x4 + byte+1==0xea":
                        "8  [RAY TRACING: dedicated ray-INTERSECT op. byte0 hi nibble=result reg; "
                        "byte+2 mode (0x90 const-origin / 0x10 dyn-origin / 0xd0 +fn-table); byte+6 "
                        "bit7=intersection-function-table present. Emitted 2x/kernel (traverse + "
                        "result-read). ABSENT from a software Moller-Trumbore loop. EXP-0023 HW]",
                "0xdf": "14  [RAY TRACING: dedicated acceleration-structure / ray-data load (memory-"
                        "family sibling of 0x67/0xe7, byte+2==0x54). BVH-node/ray/stack fetch during "
                        "the (software) traversal loop. EXP-0023]",
                # ---- EXP-0036 consolidation additions (EXP-0031/0033/0035) ----
                "byte0 low-3-bits 0b100": "4 get_sr (SR#=byte1, dst=byte0-hi; byte+3 lo-nibble==6 "
                        "suffix, covers 0xNc & 0xN4 forms) | 2 mov_imm (byte0==0x0c, no suffix). EXP-0031",
                "0x10": "6, or 8 if (byte+2 & 0x02)  [NATIVE-HALF (fp16) float ALU, sibling of 0x09. EXP-0033]",
                "0x27 (byte+1==0x05, byte+2==0x56)": "8  [popcount / bit-scan single op (ibitcount). EXP-0033]",
                "0x27 (byte+1==0x01)": "12  [ROTATE-by-immediate funnel shift (irotate). EXP-0033]",
                "0xa7 (byte+1 in {0x04,0x05})": "8  [reverse_bits / find-MSB bit-scan (ibitcount). EXP-0033]",
                "0x97 (byte+2==0x56)": "10  [pack_convert (pack_float_to_unorm/snorm2x16); byte+2==0x54 is the "
                        "fragment frag_color_pack. EXP-0033]",
                "0x17 (byte+2==0x56)": "10  [unpack_convert (unpack_unorm2x16); simd_ballot (byte+1==0x07) is "
                        "the ballot/vote source. EXP-0033/0018]",
                "0x22": "6 if (byte+2 lo-nibble==0x0e) [iminmax_chain: min3/max3/clamp] else 10 [shift/"
                        "sign-extend helper]. EXP-0033",
                "0xNb (byte+2 low-nibble e/f, 0x2b/3b/5b/8b)": "10 shift-amount PREP stage; (byte+2 hi-nibble 2) "
                        "= 4 compact call-argument MOVE; (byte+2 in {0e,1e,1f}) = 10 funary/ilogic; "
                        "(byte+2==0x01,byte+3==0x08) = 4 uniform_mov. EXP-0033/0036",
                "0x43": "4  [CALL-SITE / FRAME-SETUP marker (`43 00 00 01`), precedes every out-of-line CALL "
                        "in compute & mesh. NOT mesh-unique. EXP-0035 (re-scoped EXP-0030)]",
                "0x0f (byte+1==0x05)": "14 direct CALL if byte+4==0x8f (target = call_addr+4+off40) else 8 "
                        "exec-mask push; (byte+1==0x80) = 6 INDIRECT CALL leader; (byte+1==0x06) = 6 reconverge. EXP-0035",
                "0x8f": "4  [function RETURN (`8f <lm> 54 00`); no encoded target (HW link register / CF stack); "
                        "byte+1 0x02 leaf / 0x12 non-leaf. EXP-0035]",
                # ---- EXP-0037 (vertex varying store + texture coordinate math) ----
                "0x57": "8  [VERTEX varying / [[position]] store to the UVS/parameter buffer the FS iter op "
                        "interpolates. Memory-family (low-nibble 7). byte+3=source GPR, byte+4=output slot "
                        "(index<<5; position=slots 0-3). EXP-0037 HW-splice-proven]",
                "lownibble_0x5 + (byte+1 & 0xf0)==0x80 + byte+2==0x0c":
                        "14  [tex_sample companion-gate WIDENED (EXP-0037) from byte+1==0x80 to high-nibble 8 so "
                        "the CHAINED-companion forms (0x82/0x84/0x88 before the 2nd..Nth sample op) also absorb "
                        "their 10-byte 0xb0/0x90 sampler op]",
                "0x09 op-select 0x26/0x2e": "8 if (byte+4 & 0x02) else 6  [fused mul / mul-add COORDINATE / "
                        "matrix-multiply op -- byte+2 bit1 is SET yet the 2-source form is 6B, so length reads "
                        "byte+4 bit1 not byte+2 bit1 (EXP-0037). 0x09 op-select 0x18/0x38 = 4 compact accumulate]",
                "0xNb (byte+2 in {0x27,0x2f})": "10  [texture COORDINATE / LOD / gather-offset setup ALU "
                        "(tex_coord_setup); must precede the (byte+2 hi-nibble 2)=4 compact-move branch. EXP-0037]",
                "0x2e/0x3e (byte+2==0x23)": "10  [coordinate / interpolation fused mul-add ALU LEADER (coord_madf); "
                        "gated tightly on the `23 a0 42` coord signature. EXP-0037]",
                "0x30/0x90/0xb0 (byte+2 in texture-variant set)": "10  [standalone texture SAMPLER OP fallback, "
                        "resync-only; primary closer is the companion-gate widening. EXP-0037]",
                # ---- EXP-0038 (u64 carry / non-leaf frame / half pack / cache bit) ----
                "0x32": "6  [u64 CARRY-GENERATE (carry_gen): unsigned-overflow compare (byte+2==0x35, byte+4==0x22) "
                        "detecting the low-word add carry in a 64-bit ADD chain; predicate feeds a 0x05 psel. EXP-0038]",
                "0x22 (byte+2==0x35)": "6  [carry-generate sibling of 0x32 (intermediate carry of a 3-operand u64 add); "
                        "the byte+2 lo-nibble 0x0e min3/max3/clamp form is also 6, else 10. EXP-0038]",
                "0x6f": "6  [NON-LEAF FUNCTION FRAME PROLOGUE (frame_prologue): establishes the per-thread scratch "
                        "frame a non-leaf callee uses to save its link register around inner calls. EXP-0038]",
                "0x60": "4  [FOUR-BYTE 0x60 FORM (historical name spill_frame_marker): `60 00 00 00` was "
                        "observed after entry get_sr in one prior A18 high-pressure kernel. Runtime-inert for "
                        "that computation (byte0/+1/+2 splices no-op), byte+3 live (0xff faults). EXP-0041 "
                        "found it absent from nine M4 own mains including 208--576 B scratch, so it is not a "
                        "universal spill marker. Length 4 validated; exact role unresolved]",
                "device_load/store +5 index_reg (RT-1a-FIX)": "+5 is the INDEX GPR that supplies a[idx] (NOT "
                        "`count`; sweeping +5 selects which GPR feeds the index); +6 is INERT; +1 = address space; "
                        "the additive IMMEDIATE index-offset lives at +9 bit7 (+1) / +10 (+2/unit) / +11 low (+512/"
                        "unit). Vector width/count is at +8 (dst_width) / +12 (elem_size). RT-1a-FIX HW-validated.",
                "iadd2 add/sub polarity (RT-1a-FIX)": "byte0 bit7 = ADD(1,0x9f) / SUBTRACT(0,0x1f) select. The DB "
                        "previously had this INVERTED (labelled every add srcA_neg=1 and gave 0x1f d=srcA+srcB "
                        "although 0x1f subtracts). Splice 0x9f->0x1f turns 10+20 into 10-20=-10. HW-validated.",
                "0x07 (byte+1==0x00, byte+2==0x54)": "8  [LINK-REGISTER SAVE/RESTORE around a nested call in a "
                        "non-leaf frame (link_save_restore); the byte+1 in {0x04,0x14} forms are the 6-byte "
                        "threadgroup_barrier / pixel_order. EXP-0038]",
                "0x18": "4  [HALF-LANE PACK (half_pack): assemble a half2's two fp16 lanes into one packed 32-bit "
                        "register before the store. byte0 hi nibble = dst reg (0x08/0x18/0x28/0x38 = r0..r3). EXP-0038]",
                "0xbf/0x3f/0xb7 cache bit": "the reduce length/match gate accepts byte+2 in {0x54,0x56} (bit17 = a "
                        "source cache/last-use hint, not an op change; EXP-0038). NB the 0x37 derivative-vs-quad-"
                        "reduce byte+2==0x56 disambiguation is deliberately NOT relaxed.",
                # ---- EXP-O2C (RT completion tail + tensor operand decode) ----
                "0x5f (byte+2 in {0x54,0x56})": "14  [RAY-TRACING ray-data / traversal-stack memory op (rt_ray_mem); "
                        "the store/spill-side sibling of the 0xdf AS-load, carries the ray_data payload copy-in/out. "
                        "EXP-O2C]",
                "0xN2 (byte+2==0x27)": "10  [RAY-TRACING ray-vs-node transform / AABB box-test companion (rt_transform_test), "
                        "byte+3==0x81 byte+4==0x22; ~4-5 per intersector. Gated on byte+2==0x27 and placed BEFORE the "
                        "0x02/0x32 handlers (which return unconditionally). EXP-O2C]",
                "0xNb (byte+2 in {0x80,0x81})": "4  [RAY register-marshalling MOVE (ray_move): byte+2==0x81 copies a "
                        "computed reg into the block rt_intersect consumes, 0x80 zero-inits a component. Reused 35-38x "
                        "for MPP matmul2d TRANSPOSE tile moves. EXP-O2C]",
                "0xcf operand decode": "the 0xcf matrix_mac operands are now FULLY decoded (EXP-O2C splice): byte+5=A "
                        "(left) operand, byte+6=B (right), byte+7=C accumulator src, byte+8=dst, byte+3=A sub-descriptor "
                        "(load-bearing), byte+10=op-enable 0x24, byte+1=dtype, byte+2=mode (0x56 standalone SEMANTIC "
                        "vs 0x54 tiled/MPP), byte+11 bit0=accumulate-enable. All MPP tensor ops lower to this one op.",
                # ---- EXP-O2D (compute/fragment ISA tail) ----
                "0x11": "6 if byte+1==0x03 (fp32->fp16 convert cvt_f2h); else 8 if byte+1 in {0x02,0x04} (NATIVE bfloat "
                        "ALU add/mul, opsel byte+2 0x1c/0x1d) or 10 if also (byte+2 & 0x02) (bfloat fma, opsel 0x1e). "
                        "LOAD-BEARING FIX (EXP-O2D): the old flat `8 if byte+2&0x02 else 6` mis-lengthed every bfloat op "
                        "(bf_add 0x1c -> 6, bf_fma 0x1e -> 8) and desynced bfloat kernels. Disambiguate on byte+1 -- "
                        "cvt_f2h and bf_add SHARE opsel byte+2==0x1c.",
                "0xe7 (byte+1 in {0x06,0x16})": "12  [fragment COLOUR STORE (0x06 frag_color_store) / explicit "
                        "imageblock<T>.write (0x16 = first tile store after a 0x87 setup, imageblock_store): byte+5 = "
                        "imageblock field BYTE-OFFSET>>1 (vs MRT's RT index rt<<1), byte+7 = slice format. EXP-0029/O2D]",
                "0x67 (byte+1 in {0x06,0x0e,0x16})": "12  [fragment TILEBUFFER READ (0x0e tile_read, programmable "
                        "blend) / explicit imageblock<T>.read (0x06/0x16 tile variant, imageblock_load). EXP-0029/O2D]",
                "0x07 (byte+2==0x54, byte+3==0x84)": "6  [DEVICE MEMORY FENCE (mem_fence): "
                        "atomic_thread_fence(mem_device, seq_cst) = `07 04 54 84 0a 00`. byte+3 0x84 = device-memory "
                        "FENCE (vs threadgroup_barrier's 0x85 device = 0x84|0x01, the 0x01 = the added EXECUTION "
                        "barrier); byte+4 0x0a = device memory-class flag. Ordering realised by fence PRESENCE, not a "
                        "bit on the 0x67 RMW op (relaxed emits no fence, seq_cst emits it; acquire/release REJECTED by "
                        "MSL). mem_texture is a byte+4==0x06 pair that decodes as pixel_order. EXP-O2D]",
                "get_sr SR 0x84": "simd_is_helper_thread (FS): the get_sr-family leader `04 84 11 06`, read then "
                        "compared. Distinct from 0x82 simd_lane_id / 0x85 simd_group_id. EXP-O2D",
                "simd_reduce byte+1==0x06 bit7": "FLOAT simd_product / prefix-product (bit7=1, byte0=0xbf) vs "
                        "simd_sum (bit7=0, byte0=0x3f); byte+7 0x32 = FLOAT exclusive-scan. INTEGER product has no "
                        "native reduce op (shuffle+multiply tree). EXP-O2D",
                "simd_shuffle byte+1==0x06": "simd_shuffle_and_fill_up/down (fill data = a separate preceding 0x67 "
                        "load) / rotate; modulo variant changes byte+6 (0x4a->0x42) + a tail modulo byte. EXP-O2D",
            },
        },
        "scoreboard_model": {
            "note": "EXP-0025 (HW-validated). Unlike G13 (Mesa agx_insert_waits.c: an explicit "
                    "2-byte `wait` op + a 2-slot software scoreboard, AGX_MAX_PENDING=8), G17P emits "
                    "NO per-op scoreboard wait in the compute stream. Long-latency ops (device "
                    "load/store, atomics, texture sample/read) feed their consumers DIRECTLY.",
            "mechanism": "HARDWARE register interlock: an async op marks its destination register "
                    "pending; a consumer reading that register stalls in HW until the op retires. No "
                    "wait instruction, no slot-assign field, no wait-mask field in the async ops.",
            "max_in_flight": "HW-managed (bounded by the 96-GPR register file), not a compiler "
                    "constant. >=20 independent device loads outstanding, all consumed correctly with "
                    "no wait (manyload20). G13's 8-deep 2-slot software scoreboard has no G17P analog.",
            "ordering": "device RAW hazards: HW interlock (no op). CROSS-LANE threadgroup-memory "
                    "ordering: the explicit threadgroup_barrier (byte0 0x07, above). simdgroup_barrier "
                    "emits no op (lockstep simd). No separate device-scope memory-fence op was observed "
                    "in compute beyond the barrier's byte+3=0x85 device-scope variant.",
            "danger": "Because there is no software wait to omit, a compiler CANNOT introduce the "
                    "classic G13 silent-corruption bug for device RAW. The residual silent-corruption "
                    "surface is the threadgroup_barrier: splicing its byte+3 fence scope 0x61->0x00 "
                    "produced 128/256 stale-zero reads with STATUS OK (EXP-0025).",
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
