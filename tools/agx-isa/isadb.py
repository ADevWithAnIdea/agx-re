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
    if b0 in (0x67, 0xe7):
        return 14                      # device load (0x67) / store (0xE7)
    # ---- TEXTURE / SAMPLE family (EXP-0016, HW-validated) ----
    # Texture sample & texture.read are a 14-byte bundle: a 4-byte coordinate/result
    # "companion" (byte0 low-nibble 5, byte+1==0x80, byte+2==0x0c) immediately
    # followed by the 10-byte sampler op (byte0 low-nibble 0 = the 0xb0/0x90 group;
    # its high nibble is the result-register selector). Gate on the companion
    # signature so it never collides with the 4-byte psel/sel (byte0 0x05/0x16).
    if (lo == 0x05 and off + 2 < len(buf)
            and buf[off + 1] == 0x80 and buf[off + 2] == 0x0c):
        return 14                      # tex_sample / tex_read  (companion + sampler op)
    if b0 == 0xd7:
        return 16                      # texture WRITE (memory family; EXP-0016 HW)
    if b0 == 0x37:
        return 10                      # derivative / quad-difference (dfdx/dfdy); EXP-0016
    if lo == 0x09:
        # float ALU: 2-source (6B) unless the fma/3-source length bit is set.
        # NB: the 10-byte *extended source-modifier* form (abs; EXP-0006) also
        # has low-nibble 9 but is not distinguishable from byte0/byte2 alone --
        # a documented follow-up; the compiler emits it only for fabs sources.
        return 8 if (buf[off + 2] & 0x02) else 6
    if lo == 0x0b:
        return 10                      # float unary (fmov/fneg/fabs) & int bitwise (and/or/xor)
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
        if b1v == 0x07:
            return 8                   # int -> float convert (EXP-0013 HW)
        return 10 if (b1v & 0x01) else 12
    if b0 == 0x27:
        b1v = buf[off + 1]
        if b1v == 0x07:
            return 10                  # float -> int convert (EXP-0013 HW)
        if b1v in (0x00, 0x10):
            return 12                  # bitfield-extract / shift-prep stage
        return 8                       # integer unary (popcount / reduce)
    # ---- HALF-PRECISION float ALU (byte0 0x11, EXP-0013) ----
    # Mirrors the 0x09 float ALU but targets a 16-bit (half) destination; fp32->fp16
    # narrowing convert compiles to this group. Same length bit as 0x09 (byte+2 bit1).
    if b0 == 0x11:
        return 8 if (buf[off + 2] & 0x02) else 6
    # ---- 4-byte move / zero-extend (byte0 0x13, EXP-0013) ----
    # uint->ushort->uint (zero-extend from 16 bits) compiles to a 4-byte move here.
    if b0 == 0x13:
        return 4
    # ---- FLOAT SPECIAL-FUNCTION unary (byte0 0x2f / 0xaf, 10B, EXP-0013) ----
    # exp2 (0xaf), log2 (0x2f) and the round family floor/ceil/trunc/rint (0x2f, with
    # the round-mode in byte+8) are single 10-byte ops in COMPUTE. (NB: in vertex/
    # fragment code 0x2f/0x3f/0xaf are the interp/tex/deriv groups -- different, and
    # not tokenized here; EXP-0008.)
    if b0 in (0x2f, 0xaf):
        return 10
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
    if b0 == 0x0a:
        return 6
    # 0x05 / 0x16: conditional SELECT (branchless if / ternary) d = pred?A:B, 4B.
    #       Cleanly tokenizes gsel4 (0x05) and dsel5 (0x16). The compare feeding
    #       it is byte0 0x02/6B (shares length with iminmax).
    if b0 in (0x05, 0x16):
        return 4
    # 0x0f: control-flow / execution-mask group; sub-opcode in byte+1. The JUMP
    #       (loop back-edge / block skip) is `0f 00 54 <off6> 00` = 10 bytes with a
    #       SIGNED byte-relative offset (EXP-0010 E6, HW-validated: a -44 back-edge
    #       in prodloop; zeroing it -> infinite-loop hang, off-boundary targets
    #       fault). Other 0f sub-ops (mask push/pop/reconverge, mov-under-mask) are
    #       variable-length and a documented follow-up -> left UNKNOWN so they are
    #       never mis-tokenized.
    if b0 == 0x0f:
        if off + 1 < len(buf) and buf[off + 1] == 0x00:
            return 10
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
        "semantics": "d = a*b + c   ; three-source float ALU (fma). op=byte+2 (0x1e), "
                     "dst=byte+1, srcA=byte+3, srcB=byte+4, srcC=byte+5 (each (reg<<1)|size).",
        "provenance": "HW-VALIDATED (EXP-0013): base a*b+c correct across varied a,b,c; "
                      "splicing byte+5 (srcC) to the srcA/srcB descriptor changes the addend "
                      "to a / b respectively -> byte+5 is the 3rd source operand. 8-byte length "
                      "= float-ALU length bit (byte+2 bit1) set. (was inferred EXP-0001 k05_fma.)",
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
        "semantics": "d = fmax(a,b) (byte+4 bit0=0) or fmin(a,b) (bit0=1). NaN: returns the "
                     "non-NaN operand (IEEE minNum/maxNum), NaN only if BOTH are NaN. +-0 not "
                     "ordered (a tie returns srcB). (Float group byte0 0x12; the integer "
                     "min/max is the separate 0x02 group, EXP-0007.)",
        "provenance": "HW-VALIDATED (EXP-0013): fmax base correct; splicing byte+4 0x00->0x01 "
                      "flips max->min; NaN and signed-zero behaviour observed on hardware. "
                      "(was inferred byte-diff, EXP-0005 maxf/minf.)",
    },
    # ---- float unary (fmov with negate/abs modifier) ----------------------
    {
        "mnemonic": "funary",
        "length": 10,
        "match": [(0, 8, 0x0b), (16, 8, 0x0e)],   # byte0 0x0b AND op byte+2 == 0x0e (fmov)
        "fields": [
            {"name": "b1",    "start": 8,  "width": 8,  "type": "raw"},
            {"name": "op",    "start": 16, "width": 8,  "type": "opcode",
             "enum": {0x0e: "fmov"}},
            {"name": "srcA",  "start": 24, "width": 8,  "type": "reg"},
            {"name": "srcmod","start": 32, "width": 8,  "type": "raw"},   # byte+4 src descr (0x02)
            {"name": "mod",   "start": 40, "width": 8,  "type": "enum",   # byte+5 = the modifier
             "enum": {0x00: "mov", 0x02: "abs", 0x0a: "neg"}},
            {"name": "ext",   "start": 48, "width": 32, "type": "raw"},
        ],
        "semantics": "d = mod(a)   ; float source-modifier move. byte+5 selects the modifier: "
                     "0x00 = mov (copy), 0x02 = fabs (|a|), 0x0a = fneg (-a). (bit1 = abs-enable, "
                     "bit3 = negate; negate requires bit1 set -- byte+5=0x08 alone acts as mov.)",
        "provenance": "HW-VALIDATED (EXP-0013): on the fneg base, splicing byte+5 0x0a->0x02 "
                      "gives |a|, ->0x00 gives a (mov), and 0x0a gives -a; observed on hardware. "
                      "(was inferred byte-diff, EXP-0005 neg/absf.)",
    },
    # ==========================================================================
    # INTEGER ALU FAMILY  (EXP-0007, byte0 0x9f group + cousins)
    # ==========================================================================
    # Unlike the float ALU (one falu2 group with an in-byte op-select), the
    # integer ops are spread over several byte0 groups, each its own format --
    # exactly like the float side splits falu2 / fminmax / funary.  Summary of
    # the group -> operation map (see experiments/EXP-0007-integer-alu/RESULTS.md):
    #
    #   group byte0     length   operations                       op-select
    #   ---------------------------------------------------------------------------
    #   0x9f / 0x1f     10       iadd / isub  (a +/- b)            b0 bit7 = srcA-neg
    #   0x9f / 0x1f     12       imul / imad  (a*b [+c])           3-source mul-add
    #   0x0b            10       iand / ior / ixor                 b2[0:4] + b4/b5 srcB-inv
    #   0x02            6        imin/imax/umin/umax               b4[0:3] sel
    #   0xa7            10 / 12  ishr / bitfield-extract           (multi-instr helpers)
    #   0x27            8        popcount / unary reduce           b0
    #   0x12            14       integer compare -> select 0/1     b4 cond, b6 sign
    #
    # ---- integer 2-source add / sub (a +/- b), 10-byte form -----------------
    # HW-VALIDATED (EXP-0007): b3 = dst (reg<<1, dstc relocation sweep); b0 bit7 =
    # srcA negate (clearing 0x9f->0x1f turns a+b into b-a on signed inputs); b1
    # bit0 = the 10/12 length selector (splicing it faults); b2 bit1 = arith/store
    # enable (256-value b2 sweep: a+b iff bit1 set); srcA/srcB register descriptors
    # live in the b7:b9 tail (byte sweeps: b7 gates srcA, b8 gates srcB).
    {
        "mnemonic": "iadd2",
        "length": 10,
        "match": [(0, 7, 0x1f)],       # bits[0:7]=0x1f => integer add/sub group (0x9f/0x1f)
        "fields": [
            {"name": "srcA_neg",  "start": 7,  "width": 1, "type": "mod"},   # HW: 0=neg srcA
            {"name": "lenbit",    "start": 8,  "width": 1, "type": "mod"},   # HW: 1=10B 2-src
            {"name": "b1hi",      "start": 9,  "width": 7, "type": "raw"},
            {"name": "b2lo",      "start": 16, "width": 1, "type": "raw"},
            {"name": "arith_en",  "start": 17, "width": 1, "type": "mod"},   # HW: store enable
            {"name": "b2hi",      "start": 18, "width": 6, "type": "raw"},
            {"name": "dst",       "start": 24, "width": 8, "type": "reg"},   # HW: (reg<<1)|size
            {"name": "opmode",    "start": 32, "width": 8, "type": "mod"},   # 0x02 observed
            {"name": "srcB_imm",  "start": 40, "width": 8, "type": "imm"},   # HW: (imm<<1) in imm mode
            {"name": "b6",        "start": 48, "width": 8, "type": "raw"},   # imm bit8 in bit0
            {"name": "tail",      "start": 56, "width": 24, "type": "raw"},  # srcA/srcB descriptors
        ],
        "semantics": "d = (srcA_neg?-srcA:srcA) + srcB   ; integer 2-source add/sub. "
                     "dst=b3 (reg<<1). subtract = srcA-negate (b0 bit7) + operand commute. "
                     "srcB may be an 8-bit inline immediate K in [0,255] encoded as (K<<1) "
                     "at b5:b6bit0 (NOT a minifloat -- EXP-0007).",
        "provenance": "HW-VALIDATED (EXP-0007): dst field (dstc b3 sweep relocates result), "
                      "srcA-negate (a+b->b-a signed), length bit b1 (splice faults), b2 arith "
                      "enable (256-sweep), integer immediate (K<<1) for K in 0..255. srcA/srcB "
                      "reg bit-packing in the tail located but not fully bit-decoded (follow-up).",
    },
    # ---- integer 3-source multiply-add (a*b[+c]), 12-byte form --------------
    # imul compiles to this mul-add form with addend 0 (imul==umul byte-identical);
    # imad (a*b+c) shares it with the third-operand slot populated.
    {
        "mnemonic": "imad",
        "length": 12,
        "match": [(0, 7, 0x1f)],       # same group id as iadd2; length (b1 bit0==0) selects
        "fields": [
            {"name": "srcA_neg",  "start": 7,  "width": 1, "type": "mod"},
            {"name": "lenbit",    "start": 8,  "width": 1, "type": "mod"},   # =0 => 12B 3-src
            {"name": "b1hi",      "start": 9,  "width": 7, "type": "raw"},
            {"name": "b2",        "start": 16, "width": 8, "type": "raw"},
            {"name": "dst",       "start": 24, "width": 8, "type": "reg"},
            {"name": "opmode",    "start": 32, "width": 8, "type": "mod"},
            {"name": "srcB",      "start": 40, "width": 8, "type": "raw"},
            {"name": "srcC_body", "start": 48, "width": 48, "type": "raw"},  # srcA/srcB/srcC descs
        ],
        "semantics": "d = srcA*srcB (+ srcC)  ; integer multiply-add (imul is this with c=0). "
                     "unsigned/signed imul byte-identical (low 32 bits are sign-agnostic).",
        "provenance": "HW-VALIDATED behaviour (EXP-0007 smoke: imul/umul/imad correct); "
                      "12-byte length = b1 bit0==0 (HW). field bit-packing inferred (byte-diff).",
    },
    # ---- integer min / max (signed & unsigned), 6-byte form -----------------
    # HW-VALIDATED (EXP-0007): sel = b4[0:3]: bit0 = min(1)/max(0), bit1 = signed(1)/
    # unsigned(0), bit2 = 1 (integer-enable; the same byte with bit2==0 is float
    # fmin/fmax).  imin=0x07 imax=0x06 umin=0x05 umax=0x04; all four validated,
    # plus splicing imin b4 bit1 -> unsigned min on hardware.
    {
        "mnemonic": "iminmax",
        "length": 6,
        "match": [(0, 8, 0x02)],
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8, "type": "raw"},
            {"name": "op",   "start": 16, "width": 8, "type": "opcode",
             "enum": {0x1e: "iminmax"}},
            {"name": "srcA", "start": 24, "width": 8, "type": "reg"},
            {"name": "sel",  "start": 32, "width": 3, "type": "enum",
             "enum": {0x4: "umax", 0x5: "umin", 0x6: "imax", 0x7: "imin"}},
            {"name": "selhi", "start": 35, "width": 5, "type": "mod"},
            {"name": "srcB", "start": 40, "width": 8, "type": "reg"},
        ],
        "semantics": "d = {min,max}(srcA, srcB)  ; sel bit0=min/max, bit1=signed/unsigned, "
                     "bit2=1 integer (bit2=0 => float fmin/fmax, byte0 0x12).",
        "provenance": "HW-VALIDATED (EXP-0007): all four imin/imax/umin/umax outputs on "
                      "mixed-sign inputs, plus imin->umin splice of sel bit1.",
    },
    # ---- integer unary: popcount / reduce (8-byte form) --------------------
    {
        "mnemonic": "iunary",
        "length": 8,
        "match": [(0, 8, 0x27)],
        "fields": [{"name": "body", "start": 8, "width": 56, "type": "raw"}],
        "semantics": "d = unary_int(srcA)  ; popcount observed (also clz/ctz/reduce cousins)",
        "provenance": "inferred (byte-diff, EXP-0007 popcount); 8-byte length HW (tokenizes).",
    },
    # ---- arithmetic shift-right, immediate (0xa7, 10-byte) ----------------
    {
        "mnemonic": "ishift",
        "length": 10,
        "match": [(0, 8, 0xa7), (8, 1, 1)],   # 0xa7 AND b1 bit0==1 (10-byte ashr form)
        "fields": [
            {"name": "b1",    "start": 8,  "width": 8,  "type": "raw"},
            {"name": "b2",    "start": 16, "width": 8,  "type": "raw"},
            {"name": "srcdst","start": 24, "width": 16, "type": "raw"},   # byte+3:4
            {"name": "shamt", "start": 48, "width": 8,  "type": "imm"},   # byte+6 = shift<<2
            {"name": "tail",  "start": 56, "width": 24, "type": "raw"},
        ],
        "semantics": "d = a >> shamt  ; ARITHMETIC (sign-preserving) shift-right by an "
                     "immediate. Shift amount at byte+6 encoded as (shamt<<2): 0x04->1, "
                     "0x08->2, 0x10->4, 0x20->8. (Logical >> by immediate uses the 12-byte "
                     "bitfield-extract form below; register-operand shifts are multi-instr "
                     "with a 0x2b prep stage.)",
        "provenance": "HW-VALIDATED (EXP-0013): a>>2 on [-16,16,-64,255] = [-4,4,-16,63] "
                      "(sign-extending); sweeping byte+6 through 0x04/08/10/20 gives shift "
                      "amounts 1/2/4/8 exactly. (was byte-diff EXP-0007 iashr.)",
    },
    {
        "mnemonic": "ibfe",
        "length": 12,
        "match": [(0, 8, 0xa7), (8, 1, 0)],   # 0xa7 AND b1 bit0==0 (12-byte bfe / lshr form)
        "fields": [{"name": "body", "start": 8, "width": 88, "type": "raw"}],
        "semantics": "bitfield-extract extract_bits(a, off, cnt) (3-operand 12-byte form). "
                     "Also the lowering for LOGICAL (unsigned) shift-right by an immediate: "
                     "a>>k = extract_bits(a, k, 32-k).",
        "provenance": "HW-VALIDATED (EXP-0013): extract_bits(a,4,8) correct on several inputs; "
                      "unsigned a>>2 uses this 12-byte form and reads back the exact logical "
                      "shift. (was byte-diff EXP-0007 ibfe.)",
    },
    # ---- compare -> select 0/1 (14-byte, byte0 0x12): FULL condition codes ---
    # EXP-0013 HW-validated the condition-code encoding by sweeping byte+6 on the
    # icmp_lt base and running all 18 int/uint/float compare kernels:
    #   byte+4 (cmpmode): 0x22 = ORDERED relational (lt/gt), 0x26 = EQUALity
    #   byte+6 (cond)   : bits[1:3] = operand type {0b01=float,0b10=uint,0b11=sint},
    #                     bit0 = direction lt(1)/gt(0).  Enumerated:
    #        0x02 f>   0x03 f<   0x04 u>   0x05 u<   0x06 s>   0x07 s<
    #        (equality via byte+4=0x26: float-eq byte+6=0x00, int-eq byte+6=0x07)
    #   byte+5 bit0 AND byte+9 bit0 = RESULT NEGATE (lt->ge, gt->le, eq->ne).
    # Handles float, signed-int and unsigned-int compares in one 14-byte op.
    # Distinguished from float min/max (also byte0 0x12) by length: byte+2
    # low-nibble 0x0d => 14B compare.
    {
        "mnemonic": "icmpsel",
        "length": 14,
        "match": [(0, 8, 0x12)],
        "fields": [
            {"name": "b1",      "start": 8,  "width": 8, "type": "raw"},
            {"name": "op",      "start": 16, "width": 8, "type": "opcode",
             "enum": {0x1d: "icmpsel"}},
            {"name": "srcA",    "start": 24, "width": 8, "type": "reg"},
            {"name": "cmpmode", "start": 32, "width": 8, "type": "enum",     # byte+4
             "enum": {0x22: "ordered(lt/gt)", 0x26: "equal"}},
            {"name": "neg_lo",  "start": 40, "width": 8, "type": "mod"},     # byte+5, bit0=negate
            {"name": "cond",    "start": 48, "width": 8, "type": "enum",     # byte+6 condition code
             "enum": {0x02: "f_gt", 0x03: "f_lt", 0x04: "u_gt", 0x05: "u_lt",
                      0x06: "s_gt", 0x07: "s_lt", 0x00: "f_eq"}},
            {"name": "body",    "start": 56, "width": 56, "type": "raw"},    # byte+7..+13 (incl byte+9 negate, 0/1 consts)
        ],
        "semantics": "d = (srcA <cond> srcB) ? 1 : 0  ; fused compare-and-select. cmpmode "
                     "(byte+4): 0x22 ordered relational, 0x26 equality. cond (byte+6) = "
                     "[type:float/uint/sint][dir:lt/gt]. Result negate (ge/le/ne) = byte+5 "
                     "bit0 + byte+9 bit0. One op covers float & signed/unsigned int compares.",
        "provenance": "HW-VALIDATED (EXP-0013): all 18 compare kernels (eq/ne/lt/le/gt/ge x "
                      "int/uint/float) produce correct 0/1; sweeping byte+6 on the icmp_lt "
                      "base with signed inputs maps each code (0x02..0x07) to its predicate, "
                      "and byte+4 0x22<->0x26 switches relational<->equality. (was byte-diff EXP-0007.)",
    },
    # ==========================================================================
    # CONVERSIONS, BITWISE-LUT & SPECIAL FUNCTIONS  (EXP-0013)
    # ==========================================================================
    # NUMERIC CONVERSIONS are explicit convert instructions in a broad
    # unary/convert family, NOT just the ALU size bit:
    #   float->int / float->uint / half->int : byte0 0x27, 10-byte
    #   int->float / uint->float / int->half : byte0 0xa7,  8-byte
    #   fp32->fp16 (narrow)                  : byte0 0x11 (half ALU), 6-byte
    #   fp16->fp32 (widen)                   : the ordinary float ALU (falu2) with a
    #                                          16-bit srcA (byte1 bit0 = 0)  -- reuses size bit
    #   int<->uint / bitcast (as_type)       : NO instruction (free reinterpret)
    #   int narrow+sign-extend (int->short)  : 0x9f group;  zero-extend-16 (u->ushort): 0x13 (4B);
    #                                          zero-extend-8 (u->uchar): 0x0b AND-with-0xff
    # In every convert the SIGNEDNESS lives at byte+7 bit6 (0x40): set = signed
    # (f2i / i2f), clear = unsigned (f2u / u2f) -- HW-validated by splice. float->int
    # rounds toward zero (C truncation).
    # ---- float/half -> int/uint convert (0x27, 10-byte) --------------------
    {
        "mnemonic": "cvt_f2i",
        "length": 10,
        "match": [(0, 8, 0x27), (8, 8, 0x07)],
        "fields": [
            {"name": "b2",      "start": 16, "width": 8,  "type": "raw"},   # 0x56
            {"name": "src",     "start": 24, "width": 16, "type": "raw"},   # byte+3:4 source descr
            {"name": "b5",      "start": 40, "width": 8,  "type": "raw"},
            {"name": "cvtop",   "start": 48, "width": 8,  "type": "opcode", # byte+6
             "enum": {0xb4: "f2int"}},
            {"name": "signflag","start": 56, "width": 8,  "type": "mod"},   # byte+7, bit6=signed
            {"name": "tail",    "start": 64, "width": 16, "type": "raw"},   # byte+8:9
        ],
        "semantics": "d = (int|uint)(a)  ; float/half -> integer convert, round toward zero "
                     "(truncation). byte+7 bit6 (0x40) = signed (int) vs unsigned (uint).",
        "provenance": "HW-VALIDATED (EXP-0013): int(3.9)/int(-3.9)/int(2.5) = 3/-3/2 (trunc); "
                      "splicing byte+7 0x48->0x08 turns the signed f2i into the unsigned f2u "
                      "convert on hardware.",
    },
    # ---- int/uint -> float/half convert (0xa7, 8-byte) ---------------------
    {
        "mnemonic": "cvt_i2f",
        "length": 8,
        "match": [(0, 8, 0xa7), (8, 8, 0x07)],
        "fields": [
            {"name": "b2",      "start": 16, "width": 8,  "type": "raw"},   # 0x56
            {"name": "src",     "start": 24, "width": 16, "type": "raw"},   # byte+3:4
            {"name": "b5",      "start": 40, "width": 8,  "type": "raw"},
            {"name": "cvtop",   "start": 48, "width": 8,  "type": "opcode", # byte+6
             "enum": {0xac: "int2f"}},
            {"name": "signflag","start": 56, "width": 8,  "type": "mod"},   # byte+7, bit6=signed
        ],
        "semantics": "d = float(a)  ; integer/uint -> float convert (round to nearest even). "
                     "byte+7 bit6 (0x40) = signed source (i2f) vs unsigned (u2f).",
        "provenance": "HW-VALIDATED (EXP-0013): float(-3)/float(1000000) exact; splicing byte+7 "
                      "0x60->0x20 converts -1 as unsigned (4294967295 -> ~4.29e9) on hardware.",
    },
    # ---- fp32 -> fp16 narrowing convert (half ALU, 0x11, 6-byte) -----------
    {
        "mnemonic": "cvt_f2h",
        "length": 6,
        "match": [(0, 8, 0x11)],
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8, "type": "raw"},   # 0x03
            {"name": "op",   "start": 16, "width": 8, "type": "raw"},   # 0x1c (fadd/fmov-like)
            {"name": "src",  "start": 24, "width": 8, "type": "raw"},   # byte+3 source (0x81)
            {"name": "b4",   "start": 32, "width": 8, "type": "raw"},
            {"name": "tail", "start": 40, "width": 8, "type": "raw"},   # 0xc2
        ],
        "semantics": "d(half) = half(a)  ; fp32 -> fp16 narrowing convert. byte0 0x11 is the "
                     "16-bit-destination (native half) analogue of the 0x09 float ALU group "
                     "(same 6/8-byte length rule on byte+2 bit1). The reverse (fp16->fp32) is "
                     "the ordinary falu2 with a 16-bit srcA (byte1 bit0 = 0) -- reuses the size bit.",
        "provenance": "HW-VALIDATED (EXP-0013): half(3.5)/half(65504)/half(0.1) round-trip to "
                      "the exact IEEE fp16 values on hardware.",
    },
    # ---- 16-bit zero-extend / narrow move (0x13, 4-byte) -------------------
    {
        "mnemonic": "mov_zext16",
        "length": 4,
        "match": [(0, 8, 0x13)],
        "fields": [{"name": "body", "start": 8, "width": 24, "type": "raw"}],
        "semantics": "d = a & 0xFFFF  ; 16-bit zero-extend / narrow move "
                     "(uint -> ushort -> uint keeps the low halfword).",
        "provenance": "HW-VALIDATED (EXP-0013): u2us zero-extends the low 16 bits "
                      "(0xFFFFFFFF -> 0xFFFF, 0x18000 -> 0x8000).",
    },
    # ---- BITWISE 2-input LUT (0x0b, 10-byte): all 16 boolean functions -----
    # The 0x0b group (shared with the float source-modifier move) is a configurable
    # 2-input boolean unit: (byte+2, byte+4, byte+5 bit3) select ANY of the 16 LUT2
    # functions. HW-validated by sweeping a=0xAAAAAAAA,b=0xCCCCCCCC (all four input
    # bit-pairs) and reading the output LUT. Named ops (LUT over (b_bit,a_bit)):
    #   AND  b2=0x1f b4=0x00           OR   b2=0x1f b4=0x02 b5|=8
    #   XOR  b2=0x1e b4=0x02 b5|=8     XNOR b2=0x1f b4=0x01
    #   NAND b2=0x1e b4=0x03 b5|=8     NOR  b2=0x1e b4=0x01
    #   ANDN a&~b b2=0x1e b4=0x00 b5|=8  ORN a|~b b2=0x1f b4=0x01 b5|=8
    # (byte+2 low bit: 0x1e = xor-base, 0x1f = and/or-base; byte+4 low 2 bits + byte+5
    # bit3 = per-source / output invert -> the full LUT). Covers all Vulkan/GL logic ops.
    {
        "mnemonic": "ilogic",
        "length": 10,
        "match": [(0, 8, 0x0b), (17, 7, 0x0f)],   # byte0 0x0b AND byte+2[1:8]==0x0f (0x1e/0x1f)
        "fields": [
            {"name": "b1",      "start": 8,  "width": 8,  "type": "raw"},   # srcA descriptor
            {"name": "op_base", "start": 16, "width": 1,  "type": "enum",   # byte+2 bit0
             "enum": {0: "xor-base", 1: "and/or-base"}},
            {"name": "srcB",    "start": 24, "width": 8,  "type": "raw"},   # byte+3
            {"name": "lut_a",   "start": 32, "width": 8,  "type": "mod"},   # byte+4 invert low
            {"name": "lut_b",   "start": 40, "width": 8,  "type": "mod"},   # byte+5 (bit3 invert)
            {"name": "ext",     "start": 48, "width": 32, "type": "raw"},   # byte+6..9
        ],
        "semantics": "d = LUT2(a, b)  ; 2-input bitwise logic. op_base (byte+2 bit0) picks the "
                     "xor vs and/or base; byte+4[0:2] and byte+5 bit3 are per-source/output "
                     "inverts -> any of the 16 boolean functions (and/or/xor/nand/nor/xnor/"
                     "andn/orn/...). ~a is the fmov(0x0e) op with an invert (byte+4 bit0).",
        "provenance": "HW-VALIDATED (EXP-0013): all 8 named kernels (and/or/xor/andn/orn/xnor/"
                      "nand/nor) produce the correct LUT on a=0xAAAAAAAA,b=0xCCCCCCCC; the "
                      "byte+2 x byte+4 x byte+5 sweep enumerates all 16 LUT2 functions.",
    },
    # ---- float special-function unary (0x2f / 0xaf, 10-byte) ---------------
    # Single-op special functions in COMPUTE: exp2 (byte0 0xaf), log2 (0x2f), and the
    # round family floor/ceil/trunc/rint (0x2f, round-mode in byte+8). frcp/frsqrt/
    # fsqrt/fsin/fcos are NOT single ops -- they are multi-instruction Newton-Raphson
    # refinement sequences seeded by a 0x29-group estimate (byte+3 0x09=rcp/0x0b=rsqrt/
    # 0x0d=sqrt). (NB: 0x2f/0x3f/0xaf are the interp/tex/deriv groups in vertex/fragment
    # stages -- distinct, EXP-0008; this descriptor is compute-only.)
    {
        "mnemonic": "fspecial",
        "length": 10,
        "match": [(0, 7, 0x2f)],       # matches 0x2f AND 0xaf (low 7 bits); bit7 = fn_hi
        "fields": [
            {"name": "fn_hi",     "start": 7,  "width": 1, "type": "enum",   # byte0 bit7
             "enum": {0: "log2/round", 1: "exp2"}},
            {"name": "fnclass",   "start": 8,  "width": 8, "type": "enum",   # byte+1
             "enum": {0x00: "round", 0x02: "transcendental"}},
            {"name": "b2",        "start": 16, "width": 8, "type": "raw"},   # 0x56
            {"name": "src",       "start": 24, "width": 16,"type": "raw"},   # byte+3:4
            {"name": "b5",        "start": 40, "width": 8, "type": "raw"},
            {"name": "b6",        "start": 48, "width": 8, "type": "raw"},   # 0xb0
            {"name": "b7",        "start": 56, "width": 8, "type": "raw"},   # 0x40
            {"name": "roundmode", "start": 64, "width": 8, "type": "enum",   # byte+8
             "enum": {0x00: "nearest", 0x02: "floor", 0x04: "ceil", 0x06: "trunc"}},
            {"name": "b9",        "start": 72, "width": 8, "type": "raw"},
        ],
        "semantics": "d = special(a). Function = (byte0 bit7, byte+1): exp2 (0xaf, fnclass=2), "
                     "log2 (0x2f, fnclass=2); round family (0x2f, fnclass=0) with byte+8 = "
                     "round-mode 0x00 nearest-even / 0x02 floor / 0x04 ceil / 0x06 trunc.",
        "provenance": "HW-VALIDATED (EXP-0013): exp2/log2 exact on powers of two; floor/ceil/"
                      "trunc/rint correct; sweeping byte+8 (0x00/02/04/06) on the round base "
                      "selects nearest/floor/ceil/trunc exactly on +-2.4/2.6.",
    },
    # ==========================================================================
    # CONTROL FLOW  (EXP-0010, byte0 0x0a / 0x05 / 0x16 / 0x0f)
    # ==========================================================================
    # G17P uses PREDICATION for simple divergent if/else/ternary/early-return (a
    # per-lane execution mask -- no jump), and a JUMP only for loops (backward
    # edge) and larger block skips.  A compare (0x0a for control predicates, 0x02
    # for select-feeding) sets the predicate/mask; a SELECT (0x05/0x16) does the
    # branchless choose; a JUMP (0x0f sub 0x00) does the loop back-edge.
    #
    # ---- integer compare -> execution predicate (0x0a, 6-byte) -------------
    # HW-VALIDATED (EXP-0010 E2): in `if(gid>=K) return; out=7`, the immediate at
    # byte+3 sets K (0x80->2, 0x82->4, 0x84->6, 0x8e->all; monotone control of
    # which lanes store); splicing byte0 0x0a->0x02 INVERTS the condition
    # (out [7,7,7,7,0,0,0,0] -> [0,0,0,0,7,7,7,7]).  So this compare drives the
    # execution mask; the subsequent store executes only on active lanes.
    {
        "mnemonic": "icmp_pred",
        "length": 6,
        "match": [(0, 8, 0x0a)],
        "fields": [
            {"name": "sub",  "start": 8,  "width": 16, "type": "raw"},   # sense/regs
            {"name": "imm",  "start": 24, "width": 8,  "type": "imm"},   # HW: compare bound K (byte+3)
            {"name": "tail", "start": 32, "width": 16, "type": "raw"},
        ],
        "semantics": "predicate = (srcA cond imm/srcB) ; integer compare that sets the "
                     "per-lane execution mask for a predicated block (early return / "
                     "break / continue). Compare bound at byte+3; condition sense in "
                     "byte0/byte+1 (0x0a<->0x02 inverts).",
        "provenance": "HW-VALIDATED (EXP-0010 E2): byte+3 immediate moves the active-lane "
                      "boundary; byte0 0x0a->0x02 inverts the condition (splice-and-observe).",
    },
    # ---- conditional select (branchless if / ternary), 4-byte --------------
    # d = pred ? A : B.  gsel (grid select, byte0 0x05) and dsel (data select,
    # byte0 0x16) both tokenize cleanly as compare(0x02,6B)+sel(4B).  HW-VALIDATED
    # behaviour (EXP-0010 E3): moving the feeding compare's immediate monotonically
    # flips the selected value -> no branch is taken (pure predication).
    {
        "mnemonic": "sel",         # data-operand select
        "length": 4,
        "match": [(0, 8, 0x16)],
        "fields": [{"name": "body", "start": 8, "width": 24, "type": "raw"}],
        "semantics": "d = pred ? A : B  ; branchless conditional select (data operands).",
        "provenance": "HW-VALIDATED behaviour (EXP-0010 E3 dsel: compare-imm splice flips "
                      "the chosen value, no jump). clean tokenization; fields byte-diff.",
    },
    {
        "mnemonic": "psel",        # grid/immediate select variant
        "length": 4,
        "match": [(0, 8, 0x05)],
        "fields": [{"name": "body", "start": 8, "width": 24, "type": "raw"}],
        "semantics": "d = pred ? A : B  ; branchless conditional select (variant used "
                     "for grid-position ternaries).",
        "provenance": "HW-VALIDATED behaviour (EXP-0010 E3 gsel). clean tokenization; "
                      "fields byte-diff.",
    },
    # ---- jump / loop back-edge (0x0f control-flow group, sub 0x00), 10-byte -
    # `0f 00 54 <off6> 00`.  off6 = signed little-endian byte-relative offset.
    # HW-VALIDATED (EXP-0010 E6): prodloop's backward edge has off6 = 0xffffffffffd4
    # (= -44); zeroing off6 makes the jump target itself -> contained infinite-loop
    # hang; a non-boundary target -> contained CMDBUF fault.  Other 0x0f sub-ops
    # (execution-mask push/pop/reconverge) are variable and a documented follow-up.
    {
        "mnemonic": "jump",
        "length": 10,
        "match": [(0, 8, 0x0f), (8, 8, 0x00)],
        "fields": [
            {"name": "mid",    "start": 16, "width": 8,  "type": "raw"},   # 0x54 observed
            {"name": "offset", "start": 24, "width": 48, "type": "imm"},   # HW: signed byte-relative
            {"name": "tail",   "start": 72, "width": 8,  "type": "raw"},
        ],
        "semantics": "PC-relative jump; offset is a signed 48-bit little-endian "
                     "byte displacement (backward for loop back-edges). Taken while "
                     "lanes remain active (execution-mask loop).",
        "provenance": "HW-VALIDATED (EXP-0010 E6): -44 back-edge in prodloop; zeroing the "
                      "offset -> infinite-loop hang, off-boundary offsets -> fault.",
    },
    # ==========================================================================
    # MEMORY ACCESS FAMILY  (EXP-0012, device / threadgroup / constant)
    # ==========================================================================
    # ONE opcode pair covers device, threadgroup AND constant address spaces:
    #   0x67 = load, 0xe7 = store, both 14 bytes.  Byte-aligned field map below
    #   (each field = one instruction byte; the load-bearing bits within a byte
    #   are named in the semantics).  HW-VALIDATED bytes: +1(space), +4(base_slot),
    #   +5(count), +8(data width), +12(element size).  EXP-0012 splice-and-observe.
    #
    #   +0  opcode (0x67 load / 0xe7 store)                                  match
    #   +1  address space + index-register bits.  bit1 (0x02) = THREADGROUP    HW(M5)
    #       (device=0x00/0x10, threadgroup=0x02). higher bits = index GPR.
    #   +2  addressing-mode byte (0x44/0x54 device, 0x54 threadgroup)         inferred
    #   +3  bit1 (0x02) = unsigned/zero-extend load variant (sub-32)          inferred(M3)
    #   +4  BASE_SLOT: preloaded buffer-base uniform slot (0=buf0,1=buf1,..). HW(E7,M6)
    #       device & constant use it identically; threadgroup uses 0x08 (local, not a buf).
    #   +5  COUNT: number of consecutive 32-bit words moved = vector width     HW(M4)
    #       (1=scalar,2=.2/64b,3=.3,4=.4). low 3 bits; bit7 (0x80)=index-GPR-high.
    #   +6..+7 addressing / index                                             inferred
    #   +8  destination(load)/data(store) register descriptor + DATA WIDTH     HW(M2)/inf
    #       (0x51=32b,0x41=16b,0x61=8b,0x59=64b/2reg; controls bits landed).
    #   +9..+11 address/register tail                                         inferred
    #   +12 ELEMENT SIZE for address scaling: bits[1:4] size-class k -> 2^(k-1)  HW(M2)
    #       bytes (0x42=1B/8b,0x44=2B/16b,0x46=4B/32b,0x48=8B/64b). Element addressing.
    #   +13 0x00                                                              inferred
    #
    # ADDRESSING MODEL (HW-VALIDATED, EXP-0012 M1/M2): element addressing --
    # effective byte address = index_GPR * element_size(+12).  There is NO
    # immediate offset / displacement / scale field in the instruction; any
    # a[i+k] / a[i*s] is computed by a PRIOR integer ALU op on the index (in
    # ELEMENT units: the iadd immediate for a[gid+1] is (1<<1), EXP-0007 K<<1),
    # and its result GPR is consumed as the index.  a[gid+1/+2/+4], a[gid*2/*4]
    # all share a BYTE-IDENTICAL 0x67 load (only the prior ALU differs).
    {
        "mnemonic": "device_load",
        "length": 14,
        "match": [(0, 8, 0x67)],
        "fields": [
            {"name": "space",     "start": 8,  "width": 8, "type": "mod"},    # HW: bit1(0x02)=threadgroup
            {"name": "amode",     "start": 16, "width": 8, "type": "raw"},    # addressing mode
            {"name": "extmode",   "start": 24, "width": 8, "type": "mod"},    # bit1=unsigned/zero-ext
            {"name": "base_slot", "start": 32, "width": 8, "type": "imm"},    # HW: buffer base slot (+4)
            {"name": "count",     "start": 40, "width": 8, "type": "imm"},    # HW: low3=word/vector count (+5)
            {"name": "addr_lo",   "start": 48, "width": 8, "type": "raw"},
            {"name": "addr_hi",   "start": 56, "width": 8, "type": "raw"},
            {"name": "dst_width", "start": 64, "width": 8, "type": "reg"},    # HW: dst reg + data width (+8)
            {"name": "tail9",     "start": 72, "width": 8, "type": "raw"},
            {"name": "tail10",    "start": 80, "width": 8, "type": "raw"},
            {"name": "tail11",    "start": 88, "width": 8, "type": "raw"},
            {"name": "elem_size", "start": 96, "width": 8, "type": "imm"},    # HW: bits[1:4]=size-class (+12)
            {"name": "tail13",    "start": 104,"width": 8, "type": "raw"},
        ],
        "semantics": "load `count` consecutive 32-bit words (vector width, +5 low3) of "
                     "`elem_size` bytes each (+12 bits[1:4]: k->2^(k-1) B) from the "
                     "address space selected by `space` (+1 bit1: 0=device/constant, "
                     "1=threadgroup) at index_GPR * elem_size, base = buffer[base_slot] "
                     "(+4). Element addressing; NO immediate offset (a[i+k] is a prior "
                     "ALU add on the index). Sub-32 signed types are sign-extended by a "
                     "following ALU shift; unsigned use the zero-extend load variant (+3).",
        "provenance": "HW-VALIDATED (EXP-0012): base_slot (M6/E7), count/vector-width (M4 "
                      "splice 4->1 truncates the copy), element-size/address-scale (M2 "
                      "splice 46->42/44/48 changes the byte stride to 1/2/8), data width "
                      "(M2 +8=61,+12=42 -> true 8-bit byte load), element addressing / "
                      "no-offset-field (M1 iadd-imm splice shifts the read). space bit "
                      "(M5). amode/extmode/register-tail bit-packing inferred (byte-diff).",
    },
    # ---- store: identical 14-byte layout, base_slot at +4 (HW M4/M5/E7) -----
    {
        "mnemonic": "device_store",
        "length": 14,
        "match": [(0, 8, 0xe7)],
        "fields": [
            {"name": "space",     "start": 8,  "width": 8, "type": "mod"},    # HW: bit1(0x02)=threadgroup
            {"name": "amode",     "start": 16, "width": 8, "type": "raw"},
            {"name": "extmode",   "start": 24, "width": 8, "type": "mod"},
            {"name": "base_slot", "start": 32, "width": 8, "type": "imm"},    # HW: buffer base slot (+4)
            {"name": "count",     "start": 40, "width": 8, "type": "imm"},    # HW: low3=word/vector count (+5)
            {"name": "addr_lo",   "start": 48, "width": 8, "type": "raw"},
            {"name": "addr_hi",   "start": 56, "width": 8, "type": "raw"},
            {"name": "data_width","start": 64, "width": 8, "type": "reg"},    # data reg + width (+8)
            {"name": "tail9",     "start": 72, "width": 8, "type": "raw"},
            {"name": "tail10",    "start": 80, "width": 8, "type": "raw"},
            {"name": "tail11",    "start": 88, "width": 8, "type": "raw"},
            {"name": "elem_size", "start": 96, "width": 8, "type": "imm"},    # (+12) size-class
            {"name": "tail13",    "start": 104,"width": 8, "type": "raw"},
        ],
        "semantics": "store `count` 32-bit words (vector width, +5) to the address space "
                     "in `space` (+1 bit1: 1=threadgroup) at index_GPR*elem_size, base = "
                     "buffer[base_slot] (+4). Same field layout & element addressing as "
                     "device_load. Narrowing stores (char/short) set elem_size (+12).",
        "provenance": "HW-VALIDATED (EXP-0012): count/vector-width (M4 store +5 4->1 stores "
                      "fewer words), space bit (M5 threadgroup store +1 0x02->0x00 -> the "
                      "roundtrip reads back zeros), base_slot by symmetry+M5. register/"
                      "addressing tail inferred (byte-diff).",
    },
    # ---- preamble / get_special_register (HW-validated role, EXP-0010) -----
    # First instruction of every non-empty _agc.main. HW-VALIDATED (EXP-0010 E1):
    # in `out=gid` the preamble materializes thread_position_in_grid into a GPR
    # (baseline out=[0..7]); zeroing byte0 or corrupting bytes 1-2 zeroes/faults
    # the result, and the byte0 select nibble picks WHICH special register
    # (0x0c->global id; 0x1c/0x2c/0x3c read a different SR, =0 for a 1-group grid).
    {
        "mnemonic": "get_sr",
        "length": 4,
        "match": [(0, 4, 0x0c)],       # low nibble == 0xC  (0x0C/0x1C/0x2C observed)
        "fields": [
            {"name": "sr_sel", "start": 4,  "width": 4,  "type": "mod"},   # SR select (0=grid id)
            {"name": "body",   "start": 8,  "width": 24, "type": "raw"},   # dest reg / SR index
        ],
        "semantics": "d = special_register[sr_sel]  ; program preamble reads a lane SR "
                     "(thread_position_in_grid at sr_sel=0) into a GPR.",
        "provenance": "HW-VALIDATED (EXP-0010 E1): corrupting it zeroes/faults the gid "
                      "output; sr_sel nibble changes the value. (mnemonic was 'preamble'.)",
    },
    # ---- stop / end -------------------------------------------------------
    # EXP-0010 E4: the trailing 0e000000 is NOT a required terminator -- splicing
    # its opcode (even to a load opcode) or payload is a NO-OP on the output and
    # never faults. Program extent is bounded by pipeline metadata (the _agc.main
    # region length); the final device_store is the last effective instruction.
    {
        "mnemonic": "stop",
        "length": 4,
        "match": [(0, 8, 0x0e)],
        "fields": [{"name": "body", "start": 8, "width": 24, "type": "raw"}],
        "semantics": "conventional program-end word (whole body of an empty kernel). "
                     "NOT a strictly-enforced terminator: corrupting it is a no-op "
                     "(EXP-0003/EXP-0010 E4); the true end-of-program is out-of-band "
                     "(the metadata code length), not this in-band token.",
        "provenance": "HW-confirmed non-required (EXP-0003; EXP-0010 E4 splice = no-op).",
    },
    # ---- TEXTURE / SAMPLE family (EXP-0016, HW-validated) --------------------
    # A texture SAMPLE / texture.read is a 14-byte bundle: a 4-byte coordinate/result
    # "companion" (byte0 low-nibble 5, byte+1=0x80, byte+2=0x0c) directly followed by
    # the 10-byte sampler op (byte0 low-nibble 0 = the 0xb0/0x90 group). The same op
    # serves BOTH implicit/explicit sample AND texture.read (read = variant 0x17,
    # unfiltered, no sampler). Field offsets are within the 14-byte bundle.
    {
        "mnemonic": "tex_sample",
        "length": 14,
        "match": [(0, 4, 5), (8, 8, 0x80), (16, 8, 0x0c)],
        "fields": [
            {"name": "chain", "start": 4, "width": 4, "type": "mod"},        # byte0 hi: 0=first, 2=chained 2nd tex op
            {"name": "rescomp", "start": 24, "width": 8, "type": "mod"},     # byte+3 result-width / gather component
            {"name": "result_sel", "start": 32, "width": 8, "type": "reg"},  # byte+4: op-group(lo=0)+dst(hi nibble)
            {"name": "coord", "start": 40, "width": 8, "type": "reg"},       # byte+5 coordinate register
            {"name": "variant", "start": 48, "width": 8, "type": "opcode",   # byte+6 op/LOD mode
             "enum": {"0": "sample", "4": "sample_grad", "7": "sample_bias",
                      "9": "sample_lod", "23": "read"}},
            {"name": "b7", "start": 56, "width": 8, "type": "raw"},
            {"name": "tex_slot", "start": 64, "width": 8, "type": "imm"},     # byte+8 TEXTURE slot ref (bit7=index, HW)
            {"name": "samp_slot", "start": 72, "width": 8, "type": "imm"},    # byte+9 SAMPLER slot ref (HW)
            {"name": "filter", "start": 80, "width": 8, "type": "mod"},       # byte+10 bit4=filtered (sampler LOD)
            {"name": "lodmode", "start": 88, "width": 8, "type": "mod"},      # byte+11 bit2=explicit LOD/bias operand
            {"name": "tail", "start": 96, "width": 16, "type": "raw"},        # byte+12..+13
        ],
        "semantics": "r_result = texture[tex_slot].sample/read(sampler[samp_slot], coord, "
                     "variant). variant (byte+6): 0x00 sample(implicit-LOD), 0x04 grad, "
                     "0x07 bias, 0x09 level(explicit-LOD), 0x17 read(integer coord, no "
                     "sampler). tex_slot = byte+4 (bit7 = the texture-index bit), samp_slot "
                     "= byte+5. filter (byte+6 of the op = bundle byte+10) bit4 set for "
                     "filtered sampling, clear for gather/read. LOD/bias/grad operand "
                     "present flagged by bundle byte+11 bit2 (0x04); the operand register(s) "
                     "are set up by preceding ALU. Result (4 comps for a full sample) is "
                     "moved out of the texture-result registers by the following 0x97/mov "
                     "ops. Same op in COMPUTE and FRAGMENT; implicit-LOD needs a fragment "
                     "stage (LOD from derivatives).",
        "provenance": "HW-VALIDATED (EXP-0016): tex_slot (byte+4 bit0x80 splice tex1->tex0 "
                      "flipped the sampled colour), samp_slot (byte+5 splice samp1->samp0 "
                      "flipped linear->nearest filtering over 55/64 pixels), sample runs & "
                      "coordinate->texel (4x4 grid maps 1:1 to texels), texture.read variant "
                      "(c_read returns texel[coord]). variant/rescomp/coord/dst bit positions "
                      "byte-diff-localized across sample/bias/lod/grad/gather/read.",
    },
    {
        "mnemonic": "tex_write",
        "length": 16,
        "match": [(0, 8, 0xd7)],
        "fields": [
            {"name": "b1", "start": 8, "width": 8, "type": "raw"},
            {"name": "b2", "start": 16, "width": 8, "type": "raw"},
            {"name": "data", "start": 24, "width": 16, "type": "reg"},   # byte+3/+4 source colour register(s)
            {"name": "body", "start": 40, "width": 88, "type": "raw"},   # coord + texture-state descriptor tail
        ],
        "semantics": "texture[slot].write(color, coord). Memory-family store (byte0 0xd7, "
                     "low-nibble 7, sibling of the 0x67/0xe7 buffer load/store). Distinct "
                     "from the sampler-path read: writes go through the store path, reads "
                     "through the sample op (variant 0x17). Fragment or compute.",
        "provenance": "HW-VALIDATED (EXP-0016): c_write moved buffer colours into texel[coord] "
                      "exactly (read-back matched in[i]); byte+4 = source data register "
                      "(0x00 write vs 0x20 read_write). coord/descriptor tail byte-diff.",
    },
    {
        "mnemonic": "tex_deriv",
        "length": 10,
        "match": [(0, 8, 0x37)],
        "fields": [
            {"name": "b1", "start": 8, "width": 8, "type": "raw"},
            {"name": "dstsrc", "start": 16, "width": 24, "type": "raw"},   # byte+2..+4 dest/source regs
            {"name": "src_comp", "start": 40, "width": 8, "type": "raw"},  # byte+5 source component
            {"name": "axis", "start": 48, "width": 8, "type": "enum",      # byte+6 quad-difference axis
             "enum": {"146": "dfdx", "144": "dfdy"}},
            {"name": "tail", "start": 56, "width": 24, "type": "raw"},     # byte+7..+9 (0x40 const + regs)
        ],
        "semantics": "d = quad-difference derivative of a source varying (dfdx/dfdy/fwidth). "
                     "byte0 0x37, 10 bytes; axis at byte+6 (0x92 = dfdx / X, 0x90 = dfdy / Y). "
                     "Fragment-only (needs 2x2 quad helper lanes). Co-occurs with implicit-LOD "
                     "sampling, which computes LOD from these derivatives internally (an "
                     "explicit 0x37 is emitted only for source-level dfdx/dfdy/fwidth). Full "
                     "fine/coarse decode is a follow-up.",
        "provenance": "inferred (byte-diff, EXP-0016 render_deriv): four 0x37 ops = dfdx.x/"
                      "dfdx.y/dfdy.x/dfdy.y with byte+6 = 0x92 (X) for the two dfdx, 0x90 (Y) "
                      "for the two dfdy. HW: render_deriv produces the correct dfdx+dfdy pixel "
                      "(EXP-0008). Length 10 tokenizes cleanly.",
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
                    "function of byte0 (group) + a per-group length bit. Float 0x09 "
                    "uses byte+2 bit1; integer arithmetic (0x9f/0x1f/0xa7) uses "
                    "byte+1 bit0 (1=10B 2-src, 0=12B 3-src mul-add / bitfield). "
                    "EXP-0007 HW-validated.",
            "byte0_table": {
                "0x0e": 4, "lownibble_0xC": 4,
                "0x67/0xe7": "14  [load/store: device, threadgroup (byte+1 bit1=0x02) "
                             "and constant all share this opcode pair -- EXP-0012]",
                "lownibble_0x9": "6, or 8 if (byte[+2] & 0x02)  [float ALU]",
                "lownibble_0xB": "10  [float unary / integer and/or/xor]",
                "0x02": "6  [integer min/max | compare-for-select]",
                "0x12": "6 float min/max, or 14 if (byte+2 & 0x0f)==0x0d [int compare]",
                "0x9f/0x1f": "10 if (byte+1 & 1) else 12  [integer add/sub | mul-add]",
                "0xa7": "10 if (byte+1 & 1) else 12  [integer shift-r | bitfield]",
                "0x27": "8  [integer unary / popcount]",
                "0x0a": "6  [integer compare -> execution predicate (branch/return)]",
                "0x05/0x16": "4  [conditional select (branchless if/ternary)]",
                "0x0f": "10 if byte+1==0x00 (JUMP: 0f 00 54 <off6> 00, signed byte-rel); "
                        "other sub-ops (mask push/pop/reconverge) variable = follow-up",
                "lownibble_0x5 + byte+1==0x80 + byte+2==0x0c":
                        "14  [TEXTURE sample / read: 4B coord/result companion + 10B "
                        "sampler op (0xb0/0x90). EXP-0016 HW-validated]",
                "0xd7": "16  [TEXTURE write (memory-family store). EXP-0016 HW-validated]",
                "0x37": "10  [derivative / quad-difference dfdx/dfdy/fwidth. EXP-0016]",
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
