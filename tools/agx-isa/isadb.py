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
    # ---- SFU range-reduction 2-byte operand-WORDS (EXP-M4-12 S1, sin/cos) ----------
    # The transcendental argument range-reduction (sin/cos) injects little-endian
    # immediate/coefficient WORDS between the SFU ops. Each is 2 bytes, cleanly
    # bracketed between known-length ops; tightly gated on (byte0, byte+1) so it can
    # never mis-length a real op. Operands are intentionally NOT bit-decoded -- doing so
    # would reconstruct the range-reduction sequence, which clean-room rule 5 forbids.
    # Every gate is anchored by an isolated OWN-SHADER compile (S1 evidence table).
    _b1 = buf[off + 1] if off + 1 < len(buf) else -1
    _b2 = buf[off + 2] if off + 2 < len(buf) else -1
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
    # Fragment sample-position / sample-id preamble reads (centroid/sample only).
    if b0 == 0x04 and off + 1 < len(buf) and buf[off+1] != 0xea:
        return 8                       # centroid-position read
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
    if b0 == 0x07 and off + 2 < len(buf) and buf[off + 2] in (0x00, 0x02, 0x20):
        return 4                       # compute memory / scoreboard fence (RT-ISA-FIX HW).
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
    # ---- SPILL/FRAME-SETUP MARKER (byte0 0x60, RT-1a-FIX item 4) --------------
    # `60 00 00 00` appears instruction-aligned right after the entry get_sr in
    # high-register-pressure / spilling kernels (big.bin). No prior length rule ->
    # tokenization halted here. RT-1a-FIX HW-validated the length is 4: with 0x60->4
    # the following 10-byte iadd2 (`9f 11 54 ...`) aligns cleanly, and splicing the
    # op's byte+3 (=+7) to 0xff FAULTS (it is this instruction's last, live byte)
    # while byte0/+1/+2 are runtime-inert for the computation. 4 bytes.
    if b0 == 0x60:
        # RT-1a-FIX HW: `60 00 00 00` spill_frame_marker is 4B (byte+3 live). EXP-M4-01
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

DB = [
    # ---- float 2-source ALU: fadd / fmul (reg-reg form) --------------------
    # EXP-0006 fully mapped, HW-VALIDATED, the operand encoding (little-endian
    # 48-bit instruction; bit b == byte (b//8) bit (b%8)):
    #   [0:4]   group id = 0x9                                   (match)
    #   [4:8]   dst register number (b0 high nibble)   HW-VALIDATED (dstc sweep)
    #   [8]     srcA size: 1 = 32-bit, 0 = 16-bit (reads low half) HW-VALIDATED
    #   [9:16]  srcA register number (7-bit field, r0..r127)      HW-VALIDATED
    #     NB (EXP-0020): the GPR file holds up to 96 addressable 32-bit registers
    #     (compiler footprint caps at 96, then spills to scratch). EXP-0006's "64
    #     GPRs" was an artifact of a tiny-footprint test shader (index bit6 folded
    #     back to r0..r63 only because that shader declared few registers); high-
    #     pressure kernels use r0..r95 with no aliasing (HW: 93 live regs, no spill,
    #     computed correctly). 16-bit halves pack 2-per-GPR (independently
    #     addressable via the native-half 0x10/0x11 groups); the 0x09 size bit here
    #     only reaches the LOW half of a 32-bit reg.
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
                     "byte = (reg<<1)|is32 (bit0=size; 7-bit reg field, GPR file = up "
                     "to 96 addressable 32-bit regs, EXP-0020). dst here is the compact "
                     "b0[4:8] nibble (r0..r15 only); a high GPR dst uses the 8-byte falu3 "
                     "form (dst=byte+1, 7-bit) -- HW seen writing r64. srcB negate = "
                     "bit43. srcB-immediate mode = bit39 (see falu2i). When bit39=1, srcB is "
                     "NOT a GPR: byte+1's exponent nibble (bits[12:16], = instr bit15 = the "
                     "8s bit) SPLITS the two overloads -- exp>=8 (bit15=1) => packed minifloat "
                     "immediate (falu2i), exp<8 (bit15=0) => UNIFORM-REGISTER source (falu2_uni). "
                     "RT-1a-FIX HW-validated (supersedes the earlier `byte+2 bit4 / byte+5 bit1` "
                     "guess, which was wrong).",
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
    # ---- float 2-source ALU: srcB UNIFORM-REGISTER source (a + uniform) -----
    # RT-1a-FIX (item 3), HW-RE-VALIDATED. Same 6-byte length & bit39-imm-mode as
    # falu2i, but the srcB operand is a UNIFORM register, not a packed minifloat.
    # `a[gid] + p.k` (p.k a `constant T&` scalar uniform) compiles to
    # `09 0d 14 01 80 c0`: byte-identical to `a+1.0`'s `09 b1 14 01 80 c0` EXCEPT
    # byte+1 (0x0d vs 0xb1) and bit39 set for both. Runtime (a=10): p.k=7 -> 17,
    # p.k=100 -> 110, p.k=0.5 -> 10.5 -- it adds the *runtime uniform value*, NOT an
    # immediate (an immediate could not change with the bound buffer). The DB
    # previously mis-decoded this as falu2i imm=imm_decode(0x0d) ~= 0.00085.
    # DISAMBIGUATION (both forms have bit39=1): byte+1's exponent nibble (bits
    # [12:16]) -- exp>=8 => minifloat (falu2i), exp<8 => uniform. exp>=8 <=> the top
    # exponent bit (instruction bit 15 = byte+1 bit7) is set, so bit15 is the single
    # fixed match bit that separates them (cadd 0xb1 bit15=1 -> minifloat; uni 0x0d
    # bit15=0 -> uniform; splicing cadd's byte+1 0xb1->0x0d made it read an UNBOUND
    # uniform register = 0, i.e. a+0, NOT a+imm_decode(0x0d) -- proving the split).
    # uniform-register index = byte+1 as (ureg<<1)|size32 (same convention as GPR
    # operands); the observed p.k0 uniform is byte+1=0x0d (ureg 6, size 32b).
    {
        "mnemonic": "falu2_uni",
        "length": 6,
        # low-nibble 9 + srcB-imm mode (bit39=1) + exp-top-bit CLEAR (bit15=0) => uniform src
        "match": [(0, 4, 0x9), (39, 1, 1), (15, 1, 0)],
        "fields": [
            {"name": "dst",       "start": 4,  "width": 4, "type": "reg"},    # HW-VALIDATED
            {"name": "usrc",      "start": 8,  "width": 8, "type": "reg"},    # byte+1 = UNIFORM src (ureg<<1)|size
            {"name": "opsel",     "start": 16, "width": 3, "type": "opcode",
             "enum": FALU2_OPSEL_ENUM},                                       # HW-VALIDATED (fadd/fmul)
            {"name": "opflags",   "start": 19, "width": 5, "type": "mod"},    # inferred
            {"name": "srcA_size", "start": 24, "width": 1, "type": "enum",
             "enum": {1: "b32", 0: "b16"}},                                   # HW-VALIDATED
            {"name": "srcA_reg",  "start": 25, "width": 7, "type": "reg"},    # HW-VALIDATED (GPR srcA)
            {"name": "ctrl_lo",   "start": 32, "width": 7, "type": "mod"},    # inferred (bit39=imm/uni marker)
            {"name": "uni_mode",  "start": 39, "width": 1, "type": "enum",
             "enum": {1: "srcB_not_gpr"}},                                    # matched =1
            {"name": "mods",      "start": 40, "width": 8, "type": "mod"},    # inferred
        ],
        "semantics": "d = op(srcA_gpr, uniform_reg[usrc>>1])  ; srcB is a UNIFORM (thread-"
                     "invariant) register, not a GPR and not an immediate. Selected when "
                     "bit39=1 AND byte+1's exponent nibble < 8 (bit15=0); the minifloat "
                     "immediate (falu2i) uses exp>=8 (bit15=1). uniform index = byte+1 = "
                     "(ureg<<1)|size32. The uniform value is preloaded by the driver / the "
                     "constant (uniform) program (EXP-0010/EXP-0020). RT-1a-FIX HW-VALIDATED.",
        "provenance": "HW-RE-VALIDATED (RT-1a-FIX item 3): uni.metal `a[gid]+p.k` runtime "
                      "output tracks the runtime uniform (a=10: p.k=7->17, 100->110, 0.5->10.5, "
                      "2->12), which an immediate cannot. Disambiguation splice-proven: cadd "
                      "byte+1 0xb1(exp11)->minifloat a+1; ->0x0d(exp0) reads an unbound uniform "
                      "(=0), NOT a+imm_decode(0x0d). raw/uniform_src.log.",
    },
    # ---- float 3-source ALU: fma (8-byte extended form) -------------------
    {
        "mnemonic": "falu3",
        "length": 8,
        "match": [(0, 4, 0x9), (17, 1, 1)],   # low-nibble 0x9 AND length bit (+2,bit1)
        "fields": [
            # EXP-M4-13 R2 (fix_falu3_ishift / n9_falu): dst_lo = byte0 high nibble
            # MIRRORS the destination register's low 4 bits. Previously UNCOVERED, so any
            # fma whose dst was >= r1 lost its byte0 high nibble on re-assembly.
            {"name": "dst_lo", "start": 4, "width": 4, "type": "reg"},
            {"name": "dst",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "op",   "start": 16, "width": 8, "type": "opcode",
             # op-select byte+2, opsel low-3 == 0b110 (fma). 0x1e/0x36/0x66/0x62/0x3e = fma;
             # 0x26/0x2e/0x46/0x4e/0x6e/0x8e/0xae = fused mul-add COORDINATE forms (VS/tess).
             "enum": {0x1e: "fma", 0x36: "fma", 0x26: "fma_coord", 0x2e: "fma_coord",
                      0x66: "fma", 0x6e: "fma_coord", 0x46: "fma_coord", 0x4e: "fma_coord",
                      0x8e: "fma_coord", 0xae: "fma_coord", 0x62: "fma", 0x3e: "fma"}},
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
    # ---- EXTENDED 2-source float ALU (saturate / source-modifier), 8-byte (EXP-M4-13 R2 n9) --
    {
        "mnemonic": "falu2_ext",
        "length": 8,
        # bit17==0 keeps it distinct from the 8-byte fma (falu3, bit17==1); bit18==1 = arith-enable.
        "match": [(0, 4, 0x9), (17, 1, 0), (18, 1, 1)],
        "fields": [
            {"name": "dst",       "start": 4,  "width": 4, "type": "reg"},
            {"name": "srcA_size", "start": 8,  "width": 1, "type": "enum", "enum": {1: "b32", 0: "b16"}},
            {"name": "srcA_reg",  "start": 9,  "width": 7, "type": "reg"},
            {"name": "opsel",     "start": 16, "width": 3, "type": "opcode", "enum": FALU2_OPSEL_ENUM},
            {"name": "opflags",   "start": 19, "width": 5, "type": "mod"},
            {"name": "srcB_size", "start": 24, "width": 1, "type": "enum", "enum": {1: "b32", 0: "b16"}},
            {"name": "srcB_reg",  "start": 25, "width": 7, "type": "reg"},
            {"name": "ext",       "start": 32, "width": 32, "type": "raw"},   # byte+4..+7 (length selector + saturate tail)
        ],
        "semantics": "d = saturate?( op(srcA,[mod]srcB) )  ; the 8-byte EXTENDED 2-source float ALU. "
                     "op = opsel (0b100 fadd / 0b101 fmul), identical to the 6-byte falu2; bit17==0 keeps "
                     "it distinct from the 8-byte fma (falu3, bit17==1). byte+4 low 2 bits = the length "
                     "selector (01 -> this 8-byte form). SATURATE (clamp to [0,1]) sets byte+7 bit1 (the "
                     "0x82 tail on saturate(a+b)/saturate(a*b)); other tail bytes carry source-slot "
                     "modifiers. The `ext` field captures byte+4..+7 verbatim for round-trip.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): k_satadd `09 05 1c 01 01 00 00 82` / k_satmul "
                      "`09 05 1d 01 01 00 00 82` differ from the 6-byte fadd/fmul only by the byte+4=0x01 "
                      "length selector + the byte+7=0x82 saturate tail. Length from the HW-splice EXP-M4-10 "
                      "rule. Tail bit semantics beyond the saturate marker INFERRED; NOT HW-dispatch validated.",
    },
    # ---- EXTENDED 3-source float ALU (saturate-fma), 10-byte (EXP-M4-13 R2 n9) ---------------
    {
        "mnemonic": "falu3_ext",
        "length": 10,
        "match": [(0, 4, 0x9), (17, 1, 1)],
        "fields": [
            {"name": "dst_lo", "start": 4,  "width": 4, "type": "reg"},
            {"name": "dst",    "start": 8,  "width": 8, "type": "reg"},
            {"name": "op",     "start": 16, "width": 8, "type": "opcode",
             "enum": {0x1e: "fma", 0x36: "fma", 0x26: "fma_coord", 0x2e: "fma_coord",
                      0x66: "fma", 0x6e: "fma_coord", 0x3e: "fma"}},
            {"name": "srcA",   "start": 24, "width": 8, "type": "reg"},
            {"name": "srcB",   "start": 32, "width": 8, "type": "reg"},
            {"name": "srcC",   "start": 40, "width": 8, "type": "reg"},
            {"name": "ext",    "start": 48, "width": 32, "type": "raw"},   # byte+6..+9 saturate / source mod
        ],
        "semantics": "d = saturate?( a*b + c )  ; the 10-byte EXTENDED fma. Same op-select as the 8-byte "
                     "falu3 (opsel 0b110; dst=byte+1, srcA=byte+3, srcB=byte+4, srcC=byte+5). The 2-byte "
                     "tail (byte+6..+9) carries the saturate / source modifier; length = EXP-M4-10 "
                     "`6 + 2*(byte+4 & 3)` with byte+4 low2 == 10. op-select 0x26/0x2e/0x6e are the fused "
                     "mul-add COORDINATE forms.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): saturate(fma) `09 01 1e 05 82 08 02 00 00 82` "
                      "extends the 8-byte fma by the byte+4=0x82 length selector + a 0x82 saturate tail; "
                      "op-select byte+2=0x1e unchanged. Base fma semantics inherit EXP-0013 HW; the extended "
                      "tail is raw-captured (INFERRED), NOT HW-dispatch validated.",
    },
    # ---- float min/max: UNIFIED into the low-nibble-2 `iminmax` (n2_intalu, EXP-M4-13 R2).
    # The former `fminmax` (byte0 0x12, dst r1) was byte-for-byte a low-nibble-2 min/max with
    # sel byte+4 -- it is now decoded by `iminmax` (byte0 0x12 => dst nibble 1, sel 0=fmax/1=fmin).
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
    #   0x9f / 0x1f     10       iadd / isub  (a +/- b)            b0 bit7 = add(1)/sub(0)
    #   0x9f / 0x1f     12       imul / imad  (a*b [+c])           3-source mul-add
    #   0x0b            10       iand / ior / ixor                 b2[0:4] + b4/b5 srcB-inv
    #   0x02            6        imin/imax/umin/umax               b4[0:3] sel
    #   0xa7            10 / 12  ishr / bitfield-extract           (multi-instr helpers)
    #   0x27            8        popcount / unary reduce           b0
    #   0x12            14       integer compare -> select 0/1     b4 cond, b6 sign
    #
    # ---- integer 2-source add / sub (a +/- b), 10-byte form -----------------
    # HW-VALIDATED (EXP-0007 + RT-1a-FIX): b3 = dst (reg<<1, dstc relocation sweep);
    # b0 bit7 = ADD/SUB select (RT-1a-FIX corrected the polarity: 0x9f/bit7=1 = plain
    # ADD, 0x1f/bit7=0 = SUBTRACT -- the DB previously had it INVERTED, labelling every
    # real add "srcA_neg=1" and giving 0x1f the semantics d=srcA+srcB although 0x1f
    # subtracts); b1 bit0 = the 10/12 length selector (splicing it faults); b2 bit1 =
    # arith/store enable (256-value b2 sweep: a+b iff bit1 set); srcA/srcB register
    # descriptors live in the b7:b9 tail (byte sweeps: b7 gates srcA, b8 gates srcB).
    {
        "mnemonic": "iadd2",
        "length": 10,
        "match": [(0, 7, 0x1f)],       # bits[0:7]=0x1f => integer add/sub group (0x9f/0x1f)
        "fields": [
            {"name": "addsub",    "start": 7,  "width": 1, "type": "opcode",
             "enum": {1: "iadd", 0: "isub"}},                                # HW (RT-1a-FIX): b0 bit7 1=add(0x9f) 0=sub(0x1f)
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
        "semantics": "d = srcA + srcB (addsub=1, byte0 0x9f) | d = srcA - srcB (addsub=0, "
                     "byte0 0x1f)  ; integer 2-source add/sub. byte0 bit7 (addsub) is the "
                     "ADD/SUBTRACT selector: the compiler emits 0x9f for + and 0x1f for -, and "
                     "splicing a real add's byte0 0x9f->0x1f turns 10+20 into 10-20=-10 on "
                     "hardware (RT-1a-FIX -- corrects the earlier INVERTED `srcA_neg`/semantics). "
                     "dst=b3 (reg<<1)|size, a full 8-bit byte -> 7-bit reg (r0..r127), so unlike "
                     "the 6-byte falu2's 4-bit dst nibble the integer dst reaches the whole GPR "
                     "file (up to 96 regs, EXP-0020). srcB may be an 8-bit inline immediate K in "
                     "[0,255] encoded as (K<<1) at b5:b6bit0 (NOT a minifloat -- EXP-0007). A "
                     "source may name a UNIFORM register: uniform srcB sets byte+5 bit4 (0x10), "
                     "uniform srcA sets byte+6 (0x30) -- HW byte-diff EXP-0020.",
        "provenance": "HW-VALIDATED (EXP-0007 + RT-1a-FIX): dst field (dstc b3 sweep relocates "
                      "result), ADD/SUB polarity (RT-1a-FIX: iaddbank p.x+p.y is byte0 0x9f=30; "
                      "splice 0x9f->0x1f -> 10-20=-10=4294967286; raw/iadd_polarity.log), length "
                      "bit b1 (splice faults), b2 arith enable (256-sweep), integer immediate "
                      "(K<<1) for K in 0..255. srcA/srcB reg bit-packing in the tail located but "
                      "not fully bit-decoded (follow-up).",
    },
    # ---- integer 3-source multiply-add (a*b[+c]), 12-byte form --------------
    # imul compiles to this mul-add form with addend 0 (imul==umul byte-identical);
    # imad (a*b+c) shares it with the third-operand slot populated.
    {
        "mnemonic": "imad",
        "length": 12,
        "match": [(0, 7, 0x1f)],       # same group id as iadd2; length (b1 bit0==0) selects
        "fields": [
            {"name": "b0bit7",    "start": 7,  "width": 1, "type": "mod"},   # byte0 bit7 (the iadd2 add/sub bit; polarity for multiply not separately characterized)
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
        # EXP-M4-13 R2 (n2_intalu): UNIFIED dst-agnostic 32-bit int / float min/max.
        # byte0 low-nibble 2 = family; byte0 HIGH nibble = dst reg (r0..r15, PROVEN by an
        # 8-register sweep). The former dst-pinned iminmax(0x02)/fminmax(0x12)/iminmax_chain
        # (0x22) were the SAME 6-byte min/max op at dst r0/r1/r2 -> unified here. The
        # OP-SELECT lives in byte+4 (sel), NOT byte+2 (byte+2 is a source-format marker).
        # match (16,3,6): byte+2 low-3-bits == 0b110 (the 32-bit min/max markers 0x1e/0x2e/
        # 0x3e/0x26/0x36/0x0e). bit16 is covered by the match (=0) so odd-byte+2 forms
        # (low3==7) fall through to n2_op6 and still round-trip byte-exact.
        "mnemonic": "iminmax",
        "length": 6,
        "match": [(0, 4, 2), (16, 3, 6)],
        "fields": [
            {"name": "dst",      "start": 4,  "width": 4, "type": "reg"},
            {"name": "dst_full", "start": 8,  "width": 8, "type": "reg"},
            {"name": "fmt",      "start": 19, "width": 5, "type": "mod"},   # byte+2 upper bits (source-format)
            {"name": "srcA",     "start": 24, "width": 8, "type": "reg"},
            {"name": "sel",      "start": 32, "width": 3, "type": "opcode",
             "enum": {0: "fmax", 1: "fmin", 4: "umax", 5: "umin", 6: "imax", 7: "imin"}},
            {"name": "selhi",    "start": 35, "width": 5, "type": "mod"},   # srcB-immediate-mode flag
            {"name": "srcB",     "start": 40, "width": 8, "type": "reg"},
        ],
        "semantics": "d = min/max(a,b) by TYPE (32-bit int signed/unsigned, or float). byte0 hi "
                     "nibble = dst r0..r15. byte1 = (dst<<1)|size. byte+2 = source-format marker "
                     "(bits[16:19]==0b110). byte+3 = srcA. byte+4 = OP-SELECT (sel low 3 bits): "
                     "0=fmax 1=fmin 4=umax 5=umin 6=imax 7=imin. byte+5 = srcB.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): dst=byte0-hi PROVEN by an 8-reg sweep "
                      "(8 live imin ops, byte0 hi nibbles e,d,b,9,7,5,3,1). op-select=byte+4 PROVEN "
                      "(imin/imax/umin/umax/fmin/fmax differ only in byte+4 07/06/05/04/01/00). "
                      "srcA/srcB/sel inherit EXP-0007 HW validation; fmt/selhi upper bits INFERRED. "
                      "NOT HW-dispatch validated (M4 compile-only).",
    },
    {
        "mnemonic": "hminmax",
        "length": 6,
        "match": [(0, 4, 2), (16, 8, 28)],   # byte+2 == 0x1c (16-bit half/half2 min/max marker)
        "fields": [
            {"name": "dst",      "start": 4,  "width": 4, "type": "reg"},
            {"name": "dst_full", "start": 8,  "width": 8, "type": "reg"},
            {"name": "srcA",     "start": 24, "width": 8, "type": "reg"},
            {"name": "sel",      "start": 32, "width": 3, "type": "opcode",
             "enum": {0: "hmax", 1: "hmin"}},
            {"name": "selhi",    "start": 35, "width": 5, "type": "mod"},
            {"name": "srcB",     "start": 40, "width": 8, "type": "reg"},
        ],
        "semantics": "d = min/max(a,b), 16-bit (half/half2). Identical layout to iminmax but "
                     "byte+2==0x1c. byte+4 low 3 bits = op-select (0=hmax 1=hmin).",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): k_hmin/k_hmax differ only in byte+4 "
                      "(0x11 min vs 0x10 max); byte+2==0x1c is the 16-bit marker. dst=byte0-hi. "
                      "NOT HW-dispatch validated.",
    },
    {
        "mnemonic": "isel_reg",
        "length": 10,
        "match": [(0, 4, 2), (16, 8, 47)],   # byte+2 == 0x2f register-operand select (10B)
        "fields": [
            {"name": "dst",      "start": 4,  "width": 4,  "type": "reg"},
            {"name": "dst_full", "start": 8,  "width": 8,  "type": "reg"},
            {"name": "srcA",     "start": 24, "width": 8,  "type": "reg"},
            {"name": "body",     "start": 32, "width": 48, "type": "raw"},
        ],
        "semantics": "d = (predicate) ? a : b ; register-operand compare-select, 10-byte form "
                     "(byte+2 0x2f). Emitted in integer division/modulo correction. dst=byte0 hi "
                     "nibble, srcA=byte+3, body = 2nd operand + compare descriptor.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): byte+2 0x2f 10-byte reg-select in "
                      "u_div/s_div/s_mod. dst+srcA from the family model; body raw. NOT HW-dispatch "
                      "validated. Clean-room: the division algorithm is NOT reconstructed.",
    },
    {
        "mnemonic": "isel_reg8",
        "length": 8,
        "match": [(0, 4, 2), (16, 8, 37)],   # byte+2 == 0x25 register-operand select (8B)
        "fields": [
            {"name": "dst",      "start": 4,  "width": 4,  "type": "reg"},
            {"name": "dst_full", "start": 8,  "width": 8,  "type": "reg"},
            {"name": "srcA",     "start": 24, "width": 8,  "type": "reg"},
            {"name": "body",     "start": 32, "width": 32, "type": "raw"},
        ],
        "semantics": "d = (predicate) ? a : b ; register-operand select, 8-byte form (byte+2 0x25, "
                     "register srcC). dst=byte0 hi nibble, srcA=byte+3, body = 2nd operand + compare.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): byte+2 0x25 8-byte reg-select (k_int64 "
                      "`92 8f 25 8b 85 19 07 00`). dst+srcA from family model; body raw. NOT HW-"
                      "dispatch validated.",
    },
    {
        "mnemonic": "n2_op6",
        "length": 6,
        "match": [(0, 4, 2)],
        "fields": [
            {"name": "dst", "start": 4,  "width": 4, "type": "reg"},
            {"name": "b1",  "start": 8,  "width": 8, "type": "raw"},
            {"name": "op",  "start": 16, "width": 8, "type": "raw"},
            {"name": "b3",  "start": 24, "width": 8, "type": "raw"},
            {"name": "b4",  "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",  "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "Generic 6-byte low-nibble-2 op (dst = byte0 high nibble). Catch-all for the "
                     "compact select/predicate helpers and the SFU polynomial / range-reduction "
                     "SELECT steps (byte+2 op-selects 0x21/0x23/0x2b/0x03/0x3d/0x3f and compact "
                     "0x00/0x18/0x09 forms) that are NOT the min/max, carry, or compare-select ops. "
                     "Byte-level fields only; per-op-select semantics UNRESOLVED (and, for the "
                     "transcendental range-reduction selects, deliberately NOT reconstructed, rule 5).",
        "provenance": "byte-diff EXP-M4-13 R2 catch-all. dst=byte0-hi from the family sweep. "
                      "Generalises the byte0-only iminmax/fminmax/iminmax_chain catch-all of the base "
                      "DB to all dst regs WITHOUT asserting a min/max op-select for non-min/max forms. "
                      "Byte fields captured for clean tokenization + round-trip; op semantics UNRESOLVED.",
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
            # EXP-M4-13 R2 (fix_falu3_ishift / n7_fence): WIDENED byte+3:4 -> byte+3:4:5.
            # byte+5 carries source/dest register-addressing bits that vary with the dst
            # register; previously an un-captured hole so any shift with byte+5 != 0 failed
            # to re-encode (raw a7115402020408... -> reasm a7115402020008...).
            {"name": "srcdst","start": 24, "width": 24, "type": "raw"},   # byte+3:4:5
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
        # EXP-M4-13 R2 (n2_intalu): WIDENED from byte0==0x12 (dst r1) to low-nibble-2 all dst
        # (byte+2 low-nibble 0xd = compare-select marker; fmt = upper nibble for 0x0d/0x1d/0x2d).
        "mnemonic": "icmpsel",
        "length": 14,
        "match": [(0, 4, 2), (16, 4, 13)],
        "fields": [
            {"name": "dst",      "start": 4,  "width": 4, "type": "reg"},
            {"name": "dst_full", "start": 8,  "width": 8, "type": "reg"},
            {"name": "fmt",      "start": 20, "width": 4, "type": "mod"},    # byte+2 hi nibble (0x0d/0x1d/0x2d)
            {"name": "srcA",     "start": 24, "width": 8, "type": "reg"},
            {"name": "cmpmode",  "start": 32, "width": 8, "type": "enum",    # byte+4
             "enum": {0x22: "ordered(lt/gt)", 0x26: "equal"}},
            {"name": "neg_lo",   "start": 40, "width": 8, "type": "mod"},    # byte+5, bit0=negate
            {"name": "cond",     "start": 48, "width": 8, "type": "enum",    # byte+6 condition code
             "enum": {0x02: "f_gt", 0x03: "f_lt", 0x04: "u_gt", 0x05: "u_lt",
                      0x06: "s_gt", 0x07: "s_lt", 0x00: "f_eq"}},
            {"name": "body",     "start": 56, "width": 56, "type": "raw"},   # byte+7..+13 (incl byte+9 negate, 0/1 consts)
        ],
        "semantics": "d = (a <cond> b) ? K1 : K0  ; integer/float compare feeding a 0/1 select, "
                     "14-byte form. dst = byte0 high nibble. byte1 = (dst<<1)|size. byte+2 low "
                     "nibble 0xd = compare-select marker. byte+3 = srcA. cmpmode (byte+4): 0x22 "
                     "ordered relational, 0x26 equality. cond (byte+6) = [type:float/uint/sint]"
                     "[dir:lt/gt]. Result negate (ge/le/ne) = byte+5 bit0 + byte+9 bit0. One op "
                     "covers float & signed/unsigned int compares.",
        "provenance": "Generalises HW-VALIDATED icmpsel (EXP-0013: 18 compare kernels correct; "
                      "byte+6 predicate map + byte+4 relational<->equality splice). Widened EXP-M4-13 "
                      "R2 from byte0==0x12 (dst r1) to low-nibble-2 all dst. k_icmp01 reproduces the "
                      "r1 form byte-exact. NOT independently HW-dispatch validated in R2.",
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
            {"name": "cvtop",   "start": 48, "width": 8,  "type": "opcode", # byte+6 source/dest WIDTH descriptor
             # EXP-M4-13 R2 (n7_fence): byte+6 width map from byte-diff of our i/u {8,16,32}->f{16,32} kernels.
             "enum": {0xac: "int2f[32->32]", 0xa0: "i2f[16->16]", 0xa4: "i2f[16->32]",
                      0xa8: "i2f[32->16]", 0xb4: "i2f[8->32]", 0x8e: "i2f[sibling]"}},
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
        "semantics": "d(half) = half(a)  ; fp32 -> fp16 narrowing convert. byte0 0x11 is length-"
                     "polymorphic on byte+1: byte+1 == 0x03 = this 6-byte convert; byte+1 in {0x02,0x04} = "
                     "the 8/10-byte NATIVE bfloat ALU (bf_alu) below. The reverse (fp16->fp32) is the "
                     "ordinary falu2 with a 16-bit srcA (byte1 bit0 = 0) -- reuses the size bit.",
        "provenance": "HW-VALIDATED (EXP-0013): half(3.5)/half(65504)/half(0.1) round-trip to "
                      "the exact IEEE fp16 values on hardware.",
    },
    # ---- NATIVE bfloat (brain-float16) general ALU (0x11, byte+1 0x02/0x04, 8B) --------
    # The bfloat sibling of the 0x10 native-fp16 ALU group and the 0x11 fp32->fp16 convert
    # group -- reusing the SAME opsel byte+2 (0x1c add / 0x1d mul / 0x1e fma) as the 0x10/0x09
    # float groups. Disambiguated from cvt_f2h by byte+1 (0x02 scalar bfloat vs 0x03 convert).
    {
        "mnemonic": "bf_alu",
        "length": 8,
        "match": [(0, 8, 0x11), (8, 8, 0x02)],
        "fields": [
            {"name": "opsel", "start": 16, "width": 8, "type": "opcode",
             "enum": {0x1c: "bf_add", 0x1d: "bf_mul", 0x1e: "bf_fma(10B)"}},  # byte+2 op-select
            {"name": "srcA",  "start": 24, "width": 8, "type": "reg"},        # byte+3
            {"name": "srcB",  "start": 32, "width": 8, "type": "reg"},        # byte+4
            {"name": "tail",  "start": 40, "width": 24, "type": "raw"},       # byte+5..+7
        ],
        "semantics": "d(bfloat) = op(a,b)  ; NATIVE bfloat (brain-float16) general ALU. byte0 0x11 is a "
                     "DISTINCT group -- the bfloat sibling of the 0x10 native-fp16 ALU group and the 0x11 "
                     "fp32->fp16 convert group -- reusing the SAME opsel byte+2 (0x1c add / 0x1d mul / "
                     "0x1e fma, the 10-byte form) as the 0x10/0x09 float groups. NOT lowered to fp32 (a "
                     "single 0x11 op does the add; no widen-add-narrow sequence) and NOT the 0x10 fp16 "
                     "group (byte0 differs). byte+1 = 0x02 scalar bfloat, 0x04 bfloat2 (each packed lane a "
                     "separate 0x11 op). bfloat carries fp32 range (bf16 = top 16 bits of fp32), so "
                     "bfloat->float is a free 0x03 widen and float->bfloat is a 0x11 byte+1==0x03 rounding "
                     "convert. This descriptor names the 8-byte scalar (byte+1==0x02) add/mul; the "
                     "bfloat2-packed (byte+1==0x04) and 10-byte fma (opsel 0x1e) forms tokenize by the "
                     "length rule but are not separately named.",
        "provenance": "HW-VALIDATED (EXP-O2D): splicing opsel byte+2 0x1c->0x1d turned bfloat(1.0)+bfloat(2.0) "
                      "= 3.0 (bits 0x4040) into bfloat(1.0)*bfloat(2.0) = 2.0 (bits 0x4000). byte0/opsel/byte+1 "
                      "scalar-vs-bf2 from byte-diff of our own bf_add/bf_mul/bf_fma/bf2_add vs h_add(0x10)/"
                      "f_add(0x09). fma 10B + tail bytes byte-diff-inferred.",
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
    # ---- float SPECIAL-FUNCTION UNIT (SFU): 0x2f / 0xaf, 10-byte -----------
    # A single hardware SFU op computes a family of unary functions, selected by
    # (byte0 bit7, byte+1):  fn_hi bit (0x2f=0 / 0xaf=1) x fnclass (byte+1):
    #     (0x2f, 0x00) = ROUND family  floor/ceil/trunc/rint (round-mode byte+8)
    #     (0x2f, 0x01) = SQRT   (sqrt(x); fast-math emits this + a small fixup)
    #     (0x2f, 0x02) = LOG2   (log2(x))
    #     (0xaf, 0x00) = RCP    (reciprocal 1/x; fast-math & the seed for a/b)
    #     (0xaf, 0x01) = RSQRT  (1/sqrt(x))
    #     (0xaf, 0x02) = EXP2   (2^x)
    # byte+6/+7 carry a secondary function/operand code (rcp: 0x10/0x48; sqrt:
    # 0x92/0x40; exp2/log2/rsqrt/round: 0xb0/0x40). EXP-0026: under FAST-MATH each
    # of rcp/rsqrt/sqrt is a SINGLE SFU op (~0-1 ULP for nice inputs; sqrt ~1 ULP,
    # exp2/log2 ~1 ULP). exp/exp10 = exp2(x*k), log/log10 = log2(x)*k, pow(a,b) =
    # exp2(b*log2(a)), a/b = a*rcp(b) (all HW-validated). Under PRECISE math the
    # correctly-rounded 1/x, a/b and sqrt use a Newton-Raphson refinement (seed =
    # the 0x29 estimate below for 1/x, or the SFU rcp above for a/b). (NB: in
    # vertex/fragment stages 0x2f/0x3f/0xaf are the interp/tex/deriv groups --
    # distinct, EXP-0008; this descriptor is compute-only.)
    {
        "mnemonic": "fspecial",
        "length": 10,
        "match": [(0, 7, 0x2f)],       # matches 0x2f AND 0xaf (low 7 bits); bit7 = fn_hi
        "fields": [
            {"name": "fn_hi",     "start": 7,  "width": 1, "type": "enum",   # byte0 bit7
             "enum": {0: "0x2f(round/sqrt/log2)", 1: "0xaf(rcp/rsqrt/exp2)"}},
            {"name": "fnclass",   "start": 8,  "width": 8, "type": "enum",   # byte+1 fn select
             "enum": {0x00: "rcp|round", 0x01: "rsqrt|sqrt", 0x02: "exp2|log2"}},
            {"name": "b2",        "start": 16, "width": 8, "type": "raw"},   # 0x56
            {"name": "src",       "start": 24, "width": 16,"type": "raw"},   # byte+3:4
            {"name": "b5",        "start": 40, "width": 8, "type": "raw"},
            {"name": "b6",        "start": 48, "width": 8, "type": "raw"},   # secondary fn code
            {"name": "b7",        "start": 56, "width": 8, "type": "raw"},   # secondary fn code
            {"name": "roundmode", "start": 64, "width": 8, "type": "enum",   # byte+8 (round family only)
             "enum": {0x00: "nearest", 0x02: "floor", 0x04: "ceil", 0x06: "trunc"}},
            {"name": "b9",        "start": 72, "width": 8, "type": "raw"},
        ],
        "semantics": "d = SFU(a). Function = (byte0 bit7 fn_hi, byte+1 fnclass): "
                     "(0x2f,0x00)=round[floor/ceil/trunc/rint via byte+8], (0x2f,0x01)=sqrt, "
                     "(0x2f,0x02)=log2, (0xaf,0x00)=rcp(1/x), (0xaf,0x01)=rsqrt(1/sqrt x), "
                     "(0xaf,0x02)=exp2(2^x). byte+6/+7 = secondary fn code. One hardware "
                     "special-function op; fast-math emits it directly (~1 ULP). exp/exp10 = "
                     "exp2(x*k); log/log10 = log2(x)*k; pow = exp2(b*log2(a)); a/b = a*rcp(b).",
        "provenance": "HW-VALIDATED (EXP-0013 exp2/log2/round; EXP-0026 rcp/rsqrt/sqrt): exp2/log2 "
                      "exact on powers of two, 1 ULP elsewhere; floor/ceil/trunc/rint via byte+8 "
                      "round-mode; under fast-math 1/x,rsqrt,sqrt each compile to a single op of "
                      "this group (byte0/byte+1 as tabulated) at ~0-1 ULP, and a/b=a*rcp(b), "
                      "pow=exp2(b*log2(a)) confirmed by disassembly+HW readback.",
    },
    # ---- transcendental ESTIMATE seed (0x29, 6-byte): rcp/rsqrt/sqrt --------
    # EXP-0026. The PRECISE (correctly-rounded) 1/x / rsqrt / sqrt lowerings begin
    # with a low-precision hardware ESTIMATE op, then refine it with a software
    # Newton-Raphson iteration sequence (fmul/fma) to full fp32. The estimate op is
    # a distinct opcode (byte0 0x29, low-nibble-9 so it shares the 6-byte float-ALU
    # length) identified by byte+2 == 0x25; the function is byte+3:
    #     0x09 = reciprocal estimate  (~1/x)
    #     0x0b = reciprocal-sqrt estimate (~1/sqrt x)
    #     0x0d = sqrt estimate (~sqrt x)
    # HW-MEASURED PRECISION (dense single-binade sweep, reading the raw estimate
    # register before refinement): worst-case relative error ~2^-7.5..2^-8, i.e.
    # ~7.5-8 good mantissa bits (rcp ~8.0, rsqrt ~7.9, sqrt ~7.5). A compiler
    # refines this to fp32 with 2 Newton-Raphson iterations (rcp: y=y*(2-x*y);
    # rsqrt: y=y*(1.5-0.5*x*y*y)) plus final rounding -- STANDARD technique, not
    # lifted from the compiler's exact schedule.
    {
        "mnemonic": "fspecial_est",
        "length": 6,
        # EXP-M4-13 R2 (n9_falu): TIGHTENED match -- byte+2==0x25 alone over-matched every 0x25
        # form (98 plain fmuls decoded as estimate). Pin byte+3 (subop) to {0x09,0x0b,0x0d}:
        # bit24==1 AND bit27==1 AND bits[28:32]==0 selects exactly rcp/rsqrt/sqrt estimate.
        "match": [(0, 4, 0x9), (16, 8, 0x25), (28, 4, 0), (24, 1, 1), (27, 1, 1)],
        "fields": [
            {"name": "dst",   "start": 4,  "width": 4, "type": "reg"},    # byte0 hi nibble (falu2-style dst)
            {"name": "srcA",  "start": 8,  "width": 8, "type": "raw"},    # byte+1 source descriptor
            {"name": "subop", "start": 24, "width": 8, "type": "opcode",  # byte+3 = function select
             "enum": {0x09: "rcp_estimate", 0x0b: "rsqrt_estimate", 0x0d: "sqrt_estimate"}},
            {"name": "b4",    "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",    "start": 40, "width": 8, "type": "raw"},     # 0xc2
        ],
        "semantics": "d = estimate(a) ; low-precision (~7.5-8 mantissa bit) hardware seed for the "
                     "Newton-Raphson lowering of the correctly-rounded 1/x (subop 0x09), rsqrt "
                     "(0x0b) and sqrt (0x0d). byte0 0x29, 6 bytes, byte+2==0x25 discriminator, "
                     "byte+3 = function. Appears ONLY in the precise (non-fast-math) reciprocal/"
                     "root lowerings; fast-math uses the single-op SFU (fspecial 0xaf/0x2f) instead.",
        "provenance": "HW-VALIDATED (EXP-0026): byte+3 0x09/0x0b/0x0d appear in precise 1/x / rsqrt "
                      "/ sqrt; reading the raw estimate register (redirect the final store) over a "
                      "dense x-sweep gives coarse 1/x, 1/sqrt x, sqrt x with worst-case relerr "
                      "~2^-7.5..2^-8 (rcp 8.0, rsqrt 7.9, sqrt 7.5 good bits). Operand bit-fields "
                      "(dst/srcA) inferred by falu2-analogy (byte-diff); function+precision HW-proven.",
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
        # byte0 LOW nibble == 0xa identifies the op; byte0 HIGH nibble is the destination
        # (predicate) register -- HW-VALIDATED (EXP-M4-01): in k_iso_icmp2, splicing byte0
        # 0x2a->0x0a moved the loop-guard predicate from p2 to p0 (out 4/25/110/110 ->
        # 133/25/133/133) and 0x2a->0x4a moved it to p4 (-> 4/389/9989), both STATUS OK --
        # i.e. the high nibble selects which predicate register the compare writes, exactly
        # like the low-nibble-2 icmp/select family. The old (0,8,0x0a) match named only p0.
        "match": [(0, 4, 0x0a)],
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4,  "type": "raw"},   # predicate reg (byte0 hi nibble)
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
    # ---- CONDITIONAL jump / else-skip / loop guard (0x0f sub 0x01), 10-byte ----
    # `0f 01 54 <off6> 00` -- identical shape to the 0f 00 jump but MASKED: taken
    # only while lanes are active. Implements the `else`-block skip (branch over the
    # then-block), the `while`/`for` loop-exit guard (branch past the body when the
    # condition is false), and the forward skip of a `continue`/`break` tail.
    {
        "mnemonic": "jump_cond",
        "length": 10,
        "match": [(0, 8, 0x0f), (8, 8, 0x01)],
        "fields": [
            {"name": "mid",    "start": 16, "width": 8,  "type": "raw"},   # 0x54 observed
            {"name": "offset", "start": 24, "width": 48, "type": "imm"},   # signed byte-relative target
            {"name": "tail",   "start": 72, "width": 8,  "type": "raw"},
        ],
        "semantics": "CONDITIONAL PC-relative jump (masked branch). offset = signed 48-bit "
                     "little-endian byte displacement; target = jump_addr + 4 + offset (same "
                     "convention as 0f 00). Taken while the divergent execution mask still has "
                     "active lanes; used for if/else forward skips and while/for loop-exit guards.",
        "provenance": "HW-VALIDATED (RT-ISA-FIX): appears as the loop-entry guard in our for/while/"
                     "nested-CF kernels; splicing byte+1 0x01->0x00 (conditional->unconditional) makes "
                     "every lane skip the loop body -> all-zero output (cf_for [0,0,1,3,6,10,15,21] -> "
                     "all 0). Clean tokenization of the whole kernel; offset field byte-diff-localized.",
    },
    # ---- execution-mask PUSH / if-enter (0x0f sub 0x05), 4-byte -----------------
    # `0f 05 54 <lvl>` -- pushes a reconvergence entry and narrows the active mask on
    # entering a divergent region (an `if`, a loop body). The 14-byte direct CALL
    # (0f 05 .. byte+4==0x8f) is a *different* op sharing byte+1; disambiguated by
    # length (call=14) so they never collide in decode_one.
    {
        "mnemonic": "if_push",
        "length": 4,
        # length 4 already isolates the push from the 14-byte direct CALL (0f 05 .. 8f);
        # byte+2 is 0x54 (outer scope) OR 0x04 (inner nested scope, cf_big) -- captured as
        # a field, not gated, so both decode.
        "match": [(0, 8, 0x0f), (8, 8, 0x05)],
        "fields": [
            {"name": "scope", "start": 16, "width": 8, "type": "raw"},   # byte+2: 0x54 outer / 0x04 inner
            {"name": "level", "start": 24, "width": 8, "type": "raw"},   # reconverge stack level / mask id
        ],
        "semantics": "execution-mask PUSH: enters a divergent region, saving the reconvergence "
                     "point and narrowing the active-lane mask. byte+2 = scope (0x54 outer / 0x04 inner "
                     "nested), byte+3 = nesting level / mask id (0x01, 0x1a, 0x05, 0x25 observed at "
                     "successive nesting depths). Paired with a later 0f 06 pop_reconverge. Reuses the "
                     "same 0f 05 machinery as the direct CALL (which carries the 0x8f link register at "
                     "byte+4 and is 14 bytes; disambiguated by length).",
        "provenance": "HW-VALIDATED (RT-ISA-FIX): the 4-byte push is required for clean tokenization of "
                     "our for/while/nested divergence kernels (they run correct on HW -- cf_for/cf_nested "
                     "match the CPU reference). The old 8-byte length desynced the loop head. byte+3 "
                     "level byte-diff-localized across nesting depths.",
    },
    # ---- execution-mask POP / reconverge (0x0f sub 0x06), 6-byte ----------------
    # `0f 06 <b2> <lvl> 00 00` -- pops a reconvergence entry, re-widening the active
    # mask at a block/loop end. byte+2 0x04 / 0x24 observed; byte+3 = the level popped.
    {
        "mnemonic": "pop_reconverge",
        "length": 6,
        "match": [(0, 8, 0x0f), (8, 8, 0x06)],
        "fields": [
            {"name": "b2",    "start": 16, "width": 8, "type": "raw"},   # 0x04 / 0x24 observed
            {"name": "level", "start": 24, "width": 8, "type": "raw"},   # reconverge stack level popped
            {"name": "tail",  "start": 32, "width": 16, "type": "raw"},
        ],
        "semantics": "execution-mask POP / reconverge: re-enables the lanes masked off by the matching "
                     "if_push (0f 05) or loop scope, restoring the active mask at a block/loop end. "
                     "byte+3 = the reconvergence level popped (0x01 innermost, 0x02 next, ... nest levels).",
        "provenance": "HW-VALIDATED (RT-ISA-FIX): terminates every divergent region in our CF kernels; "
                     "corrupting it (byte+1 0x06->0x00) -> contained CMDBUF_ERROR (the reconvergence is "
                     "load-bearing). Nesting level byte-diff-localized (inner pops 0x01, outer 0x02).",
    },
    # ---- inner exec-mask op (0x0f sub 0x04), 4-byte -- INFERRED ----------------
    # `0f 04 04 <lvl>` -- a 4-byte 0x0f-family mask op seen once, immediately before a
    # 0f 01 jump_cond, in the nested while+continue+break body of cf_big. byte+2==0x04
    # (not the 0x54 of if_push), so it is a distinct sub-op -- likely the continue-edge
    # mask narrow / inner-scope re-mask. Length + descriptor added so the shader
    # tokenizes; semantics are INFERRED (not splice-isolated).
    {
        "mnemonic": "mask_op",
        "length": 4,
        "match": [(0, 8, 0x0f), (8, 8, 0x04)],
        "fields": [
            {"name": "b2",    "start": 16, "width": 8, "type": "raw"},   # 0x04 observed
            {"name": "level", "start": 24, "width": 8, "type": "raw"},   # scope / mask level
        ],
        "semantics": "inner execution-mask op (0f 04 04 <lvl>, 4 bytes). Appears inside deeply nested "
                     "divergence (a while-loop with continue+break) just before a 0f 01 jump_cond -- most "
                     "likely the continue-edge mask narrow / inner-scope re-mask, distinct from if_push "
                     "(0f 05, byte+2==0x54) by byte+2==0x04. Role INFERRED.",
        "provenance": "inferred (byte-diff, RT-ISA-FIX): single occurrence in cf_big (nested while+continue), "
                     "4-byte length anchored by the following 0f 01 jump_cond leader. Not splice-isolated.",
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
    #   +5  INDEX_REG: the GPR that supplies the array index a[idx]           HW(RT-1a-FIX)
    #       (RT-1a-FIX corrected: this is NOT `count`. low bits = index register number;
    #       bit7 (0x80) = a scalar/size flag the compiler sets. Sweeping it selects which
    #       GPR feeds the index: 0x00->r0, 0x01->r1, ... The apparent count=1/2/3/4 for
    #       uintN a[gid] loads was a CONFOUND -- the N-word dst occupies r0..r(N-1) so gid
    #       lands at rN. The true VECTOR WIDTH/count is at +8 (dst_width) / +12 (elem_size).)
    #   +6  INERT (HW-proven padding, RT-1a-FIX): sweeping 0x00..0xff never changes the
    #       loaded value -- NOT an address byte.
    #   +7  addressing / index tail                                           inferred
    #   +8  destination(load)/data(store) register descriptor + DATA WIDTH     HW(M2)/inf
    #       (0x51=32b,0x41=16b,0x61=8b,0x59=64b/2reg; controls bits landed).
    #   +9bit7 / +10 / +11  IMMEDIATE INDEX-OFFSET field (RT-1a-FIX, HW-validated)
    #   +12 ELEMENT SIZE for address scaling: bits[1:4] size-class k -> 2^(k-1)  HW(M2)
    #       bytes (0x42=1B/8b,0x44=2B/16b,0x46=4B/32b,0x48=8B/64b). Element addressing.
    #   +13 0x00                                                              inferred
    #
    # ADDRESSING MODEL (HW-VALIDATED, EXP-0012 + RT-1a-FIX): element addressing --
    # effective byte address = (index_GPR(+5) + idx_off) * element_size(+12).
    # RT-1a-FIX: there DOES exist an in-instruction additive IMMEDIATE index-offset
    # (an 11-bit element offset starting at byte+9 bit7): byte+9 bit7 = +1, byte+10 =
    # +2 per unit, byte+11 low bits = +512 per unit (HW: idxbuf i0=40 -> byte+9=0x81
    # -> a[41]; byte+10=0x01 -> a[42], 0x08 -> a[56]; byte+11=0x41 -> a[552]). The
    # COMPILER leaves it 0 and instead computes a[i+k]/a[i*s] via a PRIOR integer ALU
    # op on the index (EXP-0012), so all such loads still share a byte-identical 0x67 --
    # but the hardware field exists and a driver may use it.
    {
        "mnemonic": "device_load",
        "length": 14,
        "match": [(0, 8, 0x67)],
        "fields": [
            {"name": "space",     "start": 8,  "width": 8, "type": "mod"},    # HW: bit1(0x02)=threadgroup
            {"name": "amode",     "start": 16, "width": 8, "type": "raw"},    # addressing mode
            {"name": "extmode",   "start": 24, "width": 8, "type": "mod"},    # bit1=unsigned/zero-ext
            {"name": "base_slot", "start": 32, "width": 8, "type": "imm"},    # HW: buffer base slot (+4)
            {"name": "index_reg", "start": 40, "width": 8, "type": "reg"},    # HW(RT-1a-FIX): +5 = index GPR (low bits=reg#, bit7=scalar flag)
            {"name": "inert6",    "start": 48, "width": 8, "type": "raw"},    # HW(RT-1a-FIX): +6 INERT padding (sweep is a no-op)
            {"name": "tail7",     "start": 56, "width": 8, "type": "raw"},
            {"name": "dst_width", "start": 64, "width": 8, "type": "reg"},    # HW: dst reg + data width (+8)
            {"name": "tail9lo",   "start": 72, "width": 7, "type": "raw"},    # +9 bits[0:7]
            {"name": "idx_off",   "start": 79, "width": 11, "type": "imm"},   # HW(RT-1a-FIX): +9bit7/+10/+11lo additive element index-offset
            {"name": "tail11hi",  "start": 90, "width": 6, "type": "raw"},    # +11 bits[2:8]
            {"name": "elem_size", "start": 96, "width": 8, "type": "imm"},    # HW: bits[1:4]=size-class (+12)
            {"name": "tail13",    "start": 104,"width": 8, "type": "raw"},
        ],
        "semantics": "load a vector (width from +8 dst_width / +12 elem_size) from the "
                     "address space selected by `space` (+1 bit1: 0=device/constant, "
                     "1=threadgroup) at (index_reg + idx_off) * elem_size, base = "
                     "buffer[base_slot] (+4). ELEMENT addressing: +5 index_reg = the GPR "
                     "holding the array index (RT-1a-FIX: NOT `count` -- sweeping +5 selects "
                     "which GPR feeds the index; +6 is INERT). idx_off = the in-instruction "
                     "additive IMMEDIATE element offset (RT-1a-FIX: +9 bit7=+1, +10=+2/unit, "
                     "+11 low bits=+512/unit); the compiler leaves it 0 and adds a[i+k] via a "
                     "prior ALU op, but the HW field exists. Sub-32 signed types are sign-"
                     "extended by a following ALU shift; unsigned use the zero-extend load (+3).",
        "provenance": "HW-VALIDATED (EXP-0012 + RT-1a-FIX): base_slot (M6/E7), element-size/"
                      "address-scale (M2 splice 46->42/44/48 changes the byte stride), data "
                      "width (M2). RT-1a-FIX re-validated: +5 index_reg (a[i0] load, idxbuf "
                      "{40,3,77,12}, a[j]=100j+3: +5=0x00->a[40],0x01->a[3],0x02->a[77]); +6 "
                      "INERT (0x00..0xff no-op); +1 = address space (0x01/02/03->reads 0); "
                      "idx_off (+9 bit7->+1, +10->+2/unit, +11->+512/unit). raw/mem_index.log.",
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
            {"name": "index_reg", "start": 40, "width": 8, "type": "reg"},    # HW(RT-1a-FIX): +5 = index GPR (as device_load). EXP-M4-10(ISA-1): +5=0xff(r127) -> CMDBUF_ERROR fault (high bits are real reg-select, NOT masked mod-64).
            {"name": "inert6",    "start": 48, "width": 8, "type": "raw"},    # HW(RT-1a-FIX): +6 INERT padding
            {"name": "tail7",     "start": 56, "width": 8, "type": "raw"},
            {"name": "data_width","start": 64, "width": 8, "type": "reg"},    # +8. CAUTION (EXP-M4-10 ISA-1): +8 is HW-INERT under splice for STORE (unlike device_load +8 dst, which IS the reg). Two scalar stores of DISTINCT regs both had +8=0x11 while the stored VALUE tracked byte+2/+3 (amode 0x54: +3 low bits = data GPR). device_store data-reg is NOT +8 and NOT symmetric with device_load dst; exact position is amode-dependent (byte-diff, not fully pinned).
            {"name": "tail9lo",   "start": 72, "width": 7, "type": "raw"},    # +9 bits[0:7]
            {"name": "idx_off",   "start": 79, "width": 11, "type": "imm"},   # HW(RT-1a-FIX): +9bit7/+10/+11lo additive element index-offset
            {"name": "tail11hi",  "start": 90, "width": 6, "type": "raw"},    # +11 bits[2:8]
            {"name": "elem_size", "start": 96, "width": 8, "type": "imm"},    # (+12) size-class
            {"name": "tail13",    "start": 104,"width": 8, "type": "raw"},
        ],
        "semantics": "store a vector to the address space in `space` (+1 bit1: 1=threadgroup) "
                     "at (index_reg + idx_off) * elem_size, base = buffer[base_slot] (+4). "
                     "Same field layout & element addressing as device_load (RT-1a-FIX: +5 = "
                     "index GPR, NOT `count`; +6 INERT; idx_off = the additive immediate "
                     "element offset). Narrowing stores (char/short) set elem_size (+12).",
        "provenance": "HW-VALIDATED (EXP-0012 + RT-1a-FIX): space bit (M5 threadgroup store +1 "
                      "0x02->0x00 -> the roundtrip reads back zeros), base_slot by symmetry+M5. "
                      "Index/offset fields shared with device_load (RT-1a-FIX re-validated). "
                      "register/addressing tail inferred (byte-diff).",
    },
    # ---- preamble / get_special_register (HW-validated role, EXP-0010) -----
    # First instruction of every non-empty _agc.main. HW-VALIDATED (EXP-0010 E1):
    # in `out=gid` the preamble materializes thread_position_in_grid into a GPR
    # (baseline out=[0..7]); zeroing byte0 or corrupting bytes 1-2 zeroes/faults
    # the result, and the byte0 select nibble picks WHICH special register
    # (0x0c->global id; 0x1c/0x2c/0x3c read a different SR, =0 for a 1-group grid).
    # ---- get_special_register (EXP-0031, HW-validated: SR# = byte1, dst = byte0-hi) --
    # Corrects EXP-0010, which mislabelled byte0's high nibble as the SR select: the
    # SR NUMBER is byte1 (splice-proven -- splicing byte1 makes the output become that
    # SR's value), and byte0's high nibble is the DESTINATION GPR. byte0 low-3-bits =
    # 0b100 (the 0xNc preamble form and the 0xN4 datapath form; bit3 is a width/datapath
    # modifier that does not change the SR select). byte+2/+3 = a 32-bit-source suffix.
    {
        "mnemonic": "get_sr",
        "length": 4,
        "match": [(0, 3, 4)],          # low 3 bits == 0b100 (covers 0xNc and 0xN4 forms)
        "fields": [
            {"name": "form",   "start": 3,  "width": 1,  "type": "mod"},   # byte0 bit3: width/datapath (SR-select-invariant, HW)
            {"name": "dst",    "start": 4,  "width": 4,  "type": "reg"},   # byte0 hi nibble = dst GPR (HW)
            {"name": "sr_sel", "start": 8,  "width": 8,  "type": "enum",   # byte1 = SR NUMBER (HW-splice-proven)
             "enum": {0x82: "thread_index_in_simdgroup (simd_lane_id)",
                      0x84: "simd_is_helper_thread (FS)",
                      0x85: "simdgroup_index_in_threadgroup (simd_group_id)",
                      0x88: "base_vertex (VS)", 0x8a: "base_instance (VS)",
                      0x98: "threads_per_threadgroup.x", 0x99: "threads_per_threadgroup.y",
                      0x9a: "threads_per_threadgroup.z",
                      0x9c: "threadgroup_position_in_grid.x", 0x9d: "threadgroup_position_in_grid.y",
                      0x9e: "threadgroup_position_in_grid.z",
                      0xa0: "thread_position_in_grid.x (FS: pixel x)",
                      0xa1: "thread_position_in_grid.y (FS: pixel y)",
                      0xa2: "thread_position_in_grid.z",
                      0xa4: "thread_position_in_threadgroup.x", 0xa5: "thread_position_in_threadgroup.y",
                      0xa6: "thread_position_in_threadgroup.z", 0xa7: "thread_index_in_threadgroup",
                      0xa8: "threadgroups_per_grid.x", 0xa9: "threadgroups_per_grid.y",
                      0xaa: "threadgroups_per_grid.z", 0xc5: "front_facing (FS)",
                      0xd8: "instance_id (VS)", 0xdd: "vertex_id (VS)"}},
            {"name": "suffix", "start": 16, "width": 16, "type": "raw"},   # bytes +2/+3 (datapath; byte+3 lo-nibble==6)
        ],
        "semantics": "d[dst] = special_register[sr_sel]  ; read a built-in/special register "
                     "(thread/threadgroup/simd IDs & dimensions; VS vertex_id/instance_id/base_*; "
                     "FS position/front_facing) into a GPR. sr_sel = BYTE1 is the SR number "
                     "(NOT byte0-hi, which is the dst GPR). byte0 low-3-bits = 0b100; bit3 is a "
                     "datapath/width modifier that does not change the SR select. IDs are read on "
                     "demand -- no stage preloads them into GPRs. Constant-folded builtins (e.g. "
                     "threads_per_simdgroup=32) use the 2-byte mov_imm instead.",
        "provenance": "HW-VALIDATED (EXP-0031): SR# = byte1 splice-proven on dispatched kernels "
                      "(0x82->lane, 0x85->simd_group, 0x98->threads_per_tg=64, 0xa0->pos_in_grid); "
                      "dst = byte0-hi proven by multi-getsr kernels; front_facing (0xc5) both-sided "
                      "via winding flip. VS/FS SR numbers from isolation byte-diff. (Corrects EXP-0010.) "
                      "SR 0x84 = simd_is_helper_thread (FS): the get_sr-family leader `04 84 11 06` read "
                      "then compared, byte-diff-inferred (f_helper vs f_plain fragment, EXP-O2D).",
    },
    # ---- mov_imm: 2-byte small-immediate move (EXP-0031) -------------------
    # Shares byte0 low-nibble 0xC with the 4-byte get_sr; distinguished by length
    # (the get_sr 32-bit-source suffix, byte+3 low-nibble==6, is absent). Used for
    # constant-folded built-ins (threads_per_simdgroup = 32 = 0x20).
    {
        "mnemonic": "mov_imm",
        "length": 2,
        "match": [(0, 4, 0x0c)],       # byte0 low nibble 0xC (2-byte form)
        "fields": [
            {"name": "dst",  "start": 4, "width": 4, "type": "reg"},   # byte0 hi nibble = dst GPR
            {"name": "imm8", "start": 8, "width": 8, "type": "imm"},   # byte1 = 8-bit immediate
        ],
        "semantics": "d[dst] = imm8  ; 2-byte move of a small immediate into a GPR. The compiler "
                     "uses it for constant-folded built-ins (e.g. threads_per_simdgroup = 32 = 0x20).",
        "provenance": "HW-VALIDATED (EXP-0031): out[gid]=threads_per_simdgroup compiles to `0c 20`; "
                      "splicing byte1 0x20->0x21/0x40/0x11 changes the output to 33/64/17 (value == "
                      "byte1 literal, not an SR read). raw/splice_validation_compute.txt.",
    },
    # ---- uniform-register -> GPR move (EXP-0020) --------------------------
    # A source operand can name a UNIFORM register (thread-invariant) instead of a
    # GPR. Scalar `constant T&` uniforms and buffer base pointers are preloaded into
    # the uniform register file; thread-invariant expressions are computed on a
    # separate UNIFORM/SCALAR datapath in the `_agc.main.constant_program` (the
    # "uniform program", which device_loads the uniform buffers and does the uniform
    # ALU) and left in a uniform register. `_agc.main` copies a uniform register into
    # a GPR with this compact 4-byte move: `Xb YY 01 08` -- byte0 hi nibble = dst GPR,
    # byte1 = uniform source register index. In the full 2-source ALU forms, a
    # per-source "uniform" mode bit selects uniform-vs-GPR (integer 0x9f: srcB uniform
    # = byte+5 bit4, srcA uniform = byte+6; float 0x09: byte+2 bit4 / byte+5 bit1).
    {
        "mnemonic": "uniform_mov",
        "length": 4,
        "match": [(0, 4, 0x0b), (16, 8, 0x01), (24, 8, 0x08)],
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},   # byte0 hi nibble = dst GPR (r0..r15 compact)
            {"name": "usrc", "start": 8,  "width": 8, "type": "reg"},   # byte1 = uniform register index ((ureg<<2) form)
        ],
        "semantics": "d(GPR) = uniform_register[usrc]  ; copy a uniform (thread-invariant) "
                     "register into a GPR. byte1 encodes the uniform source register; the "
                     "uniform value was preloaded/precomputed by the driver or by the uniform "
                     "program in _agc.main.constant_program. Compact 4-byte form; the dst "
                     "nibble reaches r0..r15 (higher GPR dst would use a wider move form).",
        "provenance": "byte-diff (EXP-0020): u_each (out[i]=u_i for 6 uniforms) emits six "
                      "`Xb YY 01 08` with byte0 hi nibble = 0..5 (dst GPR 0..5) and byte1 "
                      "stepping by 4 per consecutive uniform (0x1c,0x20,0x24,..). f_uni / "
                      "u_many8 (sum of uniforms) leave the uniform-datapath result in a "
                      "uniform reg and emit one such move. Uniform-vs-GPR select bit located "
                      "by GPR-vs-uniform iadd byte-diff (byte+5 bit4).",
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
    # REFINED by EXP-0034: the 14-byte bundle generalizes to every texture variant via
    # op+2 (variant/dim/LOD/compare/offset), op+6 (mode), companion+3 (result descriptor
    # incl. gather component), and register operands set up by preceding ALU. Companion
    # low-nibble is 0x5 (sample/gather/read) or 0xd (compute sample_compare, carrying a
    # dependent compare-ref reg) -- both match low-3-bits 0b101; byte+1==0x80, byte+2==0x0c
    # gate the bundle.
    {
        "mnemonic": "tex_sample",
        "length": 14,
        # EXP-M4-13 (rare_e5ad): companion byte+1 match RELAXED from ==0x80 to HIGH-NIBBLE==8
        # so the CHAINED-companion forms (byte+1 low-nibble in {2,4,5,6,8,a}, emitted before
        # the 2nd..Nth sample op in a multi-sample kernel) also decode. New field comp_flags
        # (byte+1 low nibble) preserves byte-exact roundtrip. No collision: no other length-14
        # descriptor has byte0 low-3-bits==5 with byte+2==0x0c.
        "match": [(0, 3, 5), (12, 4, 8), (16, 8, 0x0c)],
        "fields": [
            {"name": "kind",  "start": 0, "width": 4, "type": "mod"},         # companion low nibble: 5 sample/gather/read, 0xd sample_compare
            {"name": "chain", "start": 4, "width": 4, "type": "mod"},         # companion hi nibble; bit5(0x20)=a chained 2nd tex op follows
            {"name": "comp_flags", "start": 8, "width": 4, "type": "mod"},    # companion byte+1 low nibble (chained-companion form selector)
            {"name": "result_desc", "start": 24, "width": 8, "type": "mod",   # companion byte+3 = result descriptor
             "enum": {184: "vec4 (full sample/read 0xb8)", 160: "scalar/compare/clamped-LOD (0xa0)",
                      168: "unclamped-LOD (0xa8)", 164: "gather comp0=r (0xa4)", 172: "gather comp1=g (0xac)",
                      180: "gather comp2=b (0xb4)", 188: "gather comp3=a (0xbc)"}},
            {"name": "result_sel", "start": 32, "width": 8, "type": "reg"},   # sampler-op byte+0: hi nibble = result-reg selector
            {"name": "coord", "start": 40, "width": 8, "type": "reg"},        # sampler-op byte+1: coordinate register base
            {"name": "variant", "start": 48, "width": 8, "type": "opcode",    # op+2 = operation / dimension / LOD-mode
             "enum": {0: "sample|gather", 1: "sample|gather+offset", 4: "sample_grad", 7: "sample_bias",
                      9: "sample_lod|array-sample", 0x13: "cube sample", 0x17: "read 2D", 0x1b: "sample_lod+offset",
                      0x20: "sample_compare|gather_compare", 0x21: "sample_compare+offset", 0x29: "sample_compare level",
                      0x39: "3D sample", 0x3b: "sample_compare_lod+offset", 0x53: "cube-array sample",
                      0x79: "read 3D", 0x80: "read MSAA", 0x97: "read 2D-array (bit7=array)",
                      # EXP-M4-10 (ISA-6) HW-splice-confirmed READ-path dim codes:
                      0x03: "read 2D-array (const layer; op+3=(layer<<3)|3)",
                      0x37: "read cube (face=coord imm (face<<1)@main+0x09)",
                      0xc3: "read cube-array (face imm; op+3=(array<<3)|3)",
                      # EXP-M4-13 (rare_e5ad) own-MSL-observed variant codes (semantics inferred, NOT HW-spliced):
                      0x05: "sample 2D (implicit-LOD / bias base)", 0x33: "sample_compare (gradient/deriv-LOD)",
                      0x9c: "read 3D (coord-register addressing)", 0xa0: "read 1D (tex1d)",
                      0xd9: "read MSAA (per-sample index)"}},
            {"name": "extra_coord", "start": 56, "width": 8, "type": "reg"},  # sampler-op byte+3: array-slice/cube-face/3D-w/MSAA-sample/compare-ref reg (or 0)
            {"name": "tex_slot", "start": 64, "width": 8, "type": "imm"},     # sampler-op byte+4: texture slot; bit7(0x80)=texture-index bit (HW)
            {"name": "samp_slot_offset", "start": 72, "width": 8, "type": "imm"}, # sampler-op byte+5: sampler slot (low) + const texel offset (HW)
            {"name": "mode",  "start": 80, "width": 8, "type": "mod",          # sampler-op byte+6
             "enum": {16: "filtered sample", 0: "gather/read/sample_compare", 32: "LOD query"}},
            {"name": "lod_present", "start": 88, "width": 8, "type": "mod"},  # sampler-op byte+7: bit2 set when explicit LOD/bias operand present
            {"name": "tail",  "start": 96, "width": 16, "type": "raw"},       # sampler-op byte+8/+9
        ],
        "semantics": "Texture sample/gather/read/compare/LOD-query bundle: a 4-byte companion "
                     "(low-nibble 5 sample/gather/read, 0xd compute sample_compare) + a 10-byte sampler op. "
                     "variant (op+2) selects operation/dimension/LOD-mode; op+2 bit5(0x20)=DEPTH-COMPARE "
                     "(compareValue CMP sampledDepth; all 8 compareFuncs HW-validated; linear filter => "
                     "native 2x2 hardware PCF), bit0(0x01)=const texel offset present. companion byte+3 = "
                     "result descriptor: bit2(0x04)=GATHER, bits[3:5]=gather component r/g/b/a. op+6 = "
                     "mode (0x10 filtered / 0x00 gather/read/compare / 0x20 LOD-query). tex_slot=op+4 "
                     "(bit7=index bit), sampler slot + const offset in op+5. LOD/bias/grad and the "
                     "depth-compare reference are register operands set up by preceding ALU. Same op in "
                     "compute and fragment; implicit LOD needs a fragment stage.",
        "provenance": "HW-VALIDATED (EXP-0016 + EXP-0034): tex_slot/samp_slot (splice flips texture/filter, "
                      "EXP-0016); sample_compare (op+2 0x20/0x29, companion 0xa0) -- all 8 compareFuncs give "
                      "the exact shadow pattern, dynamic per-thread ref proves a register operand, LINEAR "
                      "filter yields fractional PCF (true 2x2 hardware PCF); gather component (companion+3 "
                      "bits[3:5]) HW-validated r/g/b/a; gather const offset (op+5) HW-validated; LOD-query "
                      "(op+6=0x20) HW-runs. Remaining op+2 dimension codes and op+3/op+5 offset sub-bits "
                      "byte-diff-localized (EXP-0016/EXP-0034 mains).",
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
    # ======================================================================
    # SUBGROUP / QUAD FAMILY  (EXP-0018, HW-validated)
    # ======================================================================
    # SIMD-group & quad-group REDUCE / PREFIX-SCAN. 8-byte op, byte+2 == 0x56.
    #   byte0 bits: [0:3]=0b111, [4:6]=0b11 (const); bit3 = scope (1=SIMD-group,
    #   0=quad); bit7 = op-class-hi. byte+1 = op-within-class. byte+7 = data
    #   type / reduction-shape (0x03 int add/logic reduce, 0x07 int min/max,
    #   0x12 float add, 0x0b exclusive-prefix-scan, 0x09 inclusive-scan). The
    #   operation is (bit7, byte+1): (1,00)=or (0,00)=and (1,01)=add/sum
    #   (0,01)=xor (1,02)=max (0,02)=min (0,06)=fadd. SIMD width = 32 (HW).
    {
        "mnemonic": "simd_reduce",
        "length": 8,
        # EXP-0038: byte+2 bit1 (instr bit17) is a source CACHE / LAST-USE hint, not an
        # op change -- the SAME reduce comes out 0x56 standalone but 0x54 as a later
        # consumer. Make bit17 a don't-care (accept 0x54 and 0x56) and capture it in the
        # `cache` field so the codec round-trips both variants byte-exact.
        "match": [(0, 3, 0b111), (4, 2, 0b11), (16, 1, 0), (18, 6, 0x15)],
        "fields": [
            {"name": "scope",   "start": 3,  "width": 1, "type": "enum",
             "enum": {1: "simd", 0: "quad"}},          # HW-VALIDATED (bf/3f simd, b7/37 quad)
            {"name": "b0hi",    "start": 6,  "width": 1, "type": "raw"},
            {"name": "opcls",   "start": 7,  "width": 1, "type": "mod"},   # HW-VALIDATED (bf<->3f or<->and)
            {"name": "cache",   "start": 17, "width": 1, "type": "mod"},   # byte+2 bit1 = source cache/last-use hint (EXP-0038)
            {"name": "op",      "start": 8,  "width": 8, "type": "opcode",
             # EXP-M4-13 R2 (nf_simd): op-select is JOINT (byte+1 + byte0.bit7). names below
             # give both opcls forms where the reduce byte0 bit7 selects within the pair.
             "enum": {0x00: "ior/iand", 0x01: "isum/ixor", 0x02: "smax/smin", 0x03: "umax/umin",
                      0x04: "f16prod/f16sum", 0x05: "fmin", 0x06: "f32prod/f32sum", 0x07: "fmax"}},
            {"name": "b3",      "start": 24, "width": 8, "type": "raw"},
            {"name": "src",     "start": 32, "width": 8, "type": "reg"},   # byte+4 = source reg desc
            {"name": "b5",      "start": 40, "width": 8, "type": "raw"},
            {"name": "shape",   "start": 48, "width": 8, "type": "mod"},   # byte+6 (0x14 reduce / 0x16 scan)
            {"name": "dtype",   "start": 56, "width": 8, "type": "enum",
             # EXP-M4-13 R2 (nf_simd): added the f16 dtypes 0x08/0x13/0x10/0x18.
             "enum": {0x03: "i32_reduce", 0x07: "s32_minmax", 0x09: "i32_incl_scan",
                      0x0b: "i32_excl_scan", 0x12: "f32_reduce", 0x22: "f32_incl_scan",
                      0x32: "f32_excl_scan", 0x08: "f16_reduce", 0x13: "f16_minmax",
                      0x10: "f16_incl_scan", 0x18: "f16_excl_scan"}},
        ],
        "semantics": "d = simd/quad reduce or prefix-scan of src over the SIMD-group "
                     "(scope=1, width 32) or 2x2 quad (scope=0). Operation = (byte0 bit7, byte+1): "
                     "byte+1=0x00 {and(bit7=0), or(1)}; 0x01 {xor(0), add/iadd(1)}; 0x03 {?, umax(1)}; "
                     "0x05 {?, fmin(1)}; 0x06 {FADD/simd_sum(0), FMUL/simd_product(1) -- NEW EXP-O2D, "
                     "HW-splice byte0 0xbf->0x3f flips product 1.0 -> sum 32.0}; 0x07 {?, fmax(1)}; "
                     "0x02 {max/min}. byte+7 = datatype/shape: 0x03 int add|and|or|xor reduce, 0x07 int "
                     "min|max, 0x12 float reduce, 0x0b int exclusive-scan, 0x09 int inclusive-scan, 0x32 "
                     "FLOAT exclusive-scan (NEW), float inclusive-scan = the exclusive-scan followed by a "
                     "0x09 float op of the lane's own value. NB INTEGER simd_product / prefix-product have "
                     "NO native reduce op -- they LOWER to a log2(32)-step shuffle(0x47)+multiply(0x9f) "
                     "tree (only FLOAT product/prefix-product use this native op; the reduce unit has a "
                     "float-mul mode but no int-mul mode).",
        "provenance": "HW-VALIDATED (EXP-0018 + EXP-O2D): all ops run with a distinct per-lane value and "
                      "read back per-lane (sum/min/max/and/or/xor/prod/fsum/prefix all exact, width 32). "
                      "Splice-proven op-select: byte0 bf->3f flips or->and; byte+1 01->02 & byte+7 03->07 "
                      "flips sum->max; byte+7 0b->03 flips exclusive-scan->full-reduce; EXP-O2D byte0 "
                      "0xbf->0x3f flips 32-lane float product 1.0 -> sum 32.0 (byte+1=0x06 bit7=1 = "
                      "simd_product). quad byte0 b7/37 (bit3=0) proven by q_* semantics.",
    },
    # SIMD-group & quad SHUFFLE / BROADCAST. 10-byte op, byte+2 == 0x56.
    #   byte0 0x47 (broadcast / shuffle-up) / 0xc7 (shuffle-xor / down): bit7 =
    #   direction/xor. byte+1 = 0x04 (SIMD) / 0x00 (quad) / 0x06 (rotate).
    #   byte+6 = lane index or xor mask, encoded (value << 1). Quad masks the
    #   index into the 2x2 group.
    {
        "mnemonic": "simd_shuffle",
        "length": 10,
        # RT-ISA-FIX: relax byte+2 bit1 (instr bit17) to a don't-care -- it is the SAME
        # source cache/last-use hint as on simd_reduce, NOT an op change. A real compiled
        # simd_broadcast / simd_shuffle_xor carries byte+2==0x54 (bit17=0); the EXP-0018
        # corpus captured the 0x56 (bit17=1) variant. The old exact (16,8,0x56) gate made
        # every real 0x54 shuffle fail to decode ("no descriptor matches"). Accept both;
        # the `cache` field round-trips bit17 byte-exact. (Gate stays byte0 low-7==0x47, so
        # the 0x37 derivative-vs-quad-reduce disambiguation in instr_length is untouched.)
        "match": [(0, 7, 0x47), (16, 1, 0), (18, 6, 0x15)],
        "fields": [
            {"name": "dir",   "start": 7,  "width": 1, "type": "enum",
             "enum": {0: "bcast/up", 1: "xor/down"}},   # HW-VALIDATED (47 vs c7)
            {"name": "mode",  "start": 8,  "width": 8, "type": "enum",
             # EXP-M4-13 R2 (nf_simd): low nibble = op class, bit4(0x10)=dynamic index/delta,
             # bit3(0x08)=fragment quad; byte0 bit7 (dir) picks bcast/up vs xor/down.
             "enum": {0x00: "quad", 0x01: "quad_updown", 0x04: "simd", 0x05: "simd_updown",
                      0x06: "simd_rotate/fill", 0x08: "quad_frag", 0x10: "quad_dyn",
                      0x14: "simd_dyn", 0x15: "simd_updown_dyn"}},   # HW-VALIDATED (0x04/0x00/0x06)
            {"name": "cache", "start": 17, "width": 1, "type": "mod"},   # byte+2 bit1 = source cache/last-use hint
            {"name": "b3",    "start": 24, "width": 8, "type": "raw"},
            {"name": "src",   "start": 32, "width": 8, "type": "reg"},
            {"name": "b5",    "start": 40, "width": 8, "type": "raw"},
            {"name": "lane",  "start": 48, "width": 8, "type": "imm"},    # (index<<1) HW-VALIDATED
            {"name": "tail",  "start": 56, "width": 24, "type": "raw"},
        ],
        "semantics": "d = src from another lane. byte0 0x47 = broadcast / shuffle-up / fill_up, 0xc7 = "
                     "shuffle-xor / shuffle-down / fill_down (bit7 = direction). byte+1 mode: 0x04 "
                     "SIMD-group shuffle, 0x00 quad, 0x06 rotate / shuffle_and_fill (NEW EXP-O2D). "
                     "byte+6 = source lane index (broadcast) or xor mask (shuffle_xor), encoded "
                     "(value<<1). simd_broadcast_first & dynamic simd_shuffle(v,lane) use the same op "
                     "with the lane index in a register. NEW (EXP-O2D): simd_shuffle_and_fill_up/down = "
                     "byte+1==0x06; the FILL DATA is a SEPARATE operand loaded by a preceding 0x67 "
                     "device_load before the shuffle. The modulo/rotate variant (v, fill, delta, modulo) "
                     "is the same byte+1==0x06 op with byte+6 changed (fill 0x4a -> modulo 0x42) plus a "
                     "tail byte (0x20 -> 0x30) carrying the modulo. simd_shuffle_up/down add edge-handling "
                     "predication (0f80/0f9e) around the core op; simd_shuffle_xor is a single clean op.",
        "provenance": "HW-VALIDATED (EXP-0018 + RT-ISA-FIX): broadcast(0/5), broadcast_first, shuffle_xor(1), "
                      "shuffle(dyn), shuffle_up/down, rotate_up/down and the quad equivalents all "
                      "run with distinct per-lane inputs and read back exactly. byte+6=(lane<<1) "
                      "proven (bcast5 -> 0x0a, bcast lane2 quad -> 0x04, xor1 -> 0x02). mode/dir "
                      "byte-diff-localized (simd 0x04 vs quad 0x00; 0x47 vs 0xc7). RT-ISA-FIX re-proved on "
                      "HW: `simd_broadcast(lane*10+5,3)`=35 all lanes (bytes 47 04 54 ..) and "
                      "`simd_shuffle_xor(v,3)`=(lane^3)*10+5 (c7 04 54 ..) -- both carry byte+2==0x54, which "
                      "the old 0x56-only gate rejected; the relaxed match now decodes them.",
    },
    # SIMD BALLOT / VOTE mask source. 10-byte op (byte0 0x17). Produces the active
    # per-lane predicate mask consumed by simd_ballot / simd_active_threads_mask /
    # simd_all / simd_any.
    {
        "mnemonic": "simd_ballot",
        "length": 10,
        # RT-ISA-FIX: match byte+1 LOW NIBBLE == 0x7 so BOTH ballot forms decode:
        #   byte+1 0x07 = simd_active_threads_mask / simd_any / simd_all (the EXP-0018 form),
        #   byte+1 0x17 = simd_ballot(predicate)   (bit4 set = predicated ballot).
        # The old exact (8,8,0x07) matched only the active-mask form, so a real
        # simd_ballot(pred) (byte+1==0x17) fell through and MIS-DECODED as unpack_convert.
        # Now mutually exclusive with unpack_convert, which is gated on byte+1 low nibble
        # == 0x4 (unpack byte+1==0x04) -- ballot(low-nib 7) and unpack(low-nib 4) never both match.
        "match": [(0, 8, 0x17), (8, 4, 0x07)],
        "fields": [
            {"name": "pred", "start": 12, "width": 4, "type": "enum",
             "enum": {0x0: "active_mask/any/all", 0x1: "ballot(predicate)"}},  # byte+1 hi nibble: 0x07 vs 0x17
            {"name": "body", "start": 16, "width": 64, "type": "raw"},         # byte+2 (0x54/0x56 cache hint) .. byte+9
        ],
        "semantics": "produces the SIMD-group ballot / vote mask (per-lane boolean -> bitmask). "
                     "byte+1 low nibble 0x7 identifies the family; the high nibble selects the form: "
                     "0x07 = simd_active_threads_mask / simd_any / simd_all (unconditional active mask), "
                     "0x17 = simd_ballot(predicate) (the 32-bit active-lane mask OF a predicate). "
                     "SIMD width 32 -> low 32 bits are the mask (all-ones when all 32 active). byte+2 "
                     "carries the 0x54/0x56 source cache/last-use hint (like simd_reduce/simd_shuffle).",
        "provenance": "HW-VALIDATED (EXP-0018 + RT-ISA-FIX): simd_ballot(v>0) = 0xFFFFFFFF with all lanes >0, "
                      "and the correct even-lane mask (0x55555555) with alternating predicate; "
                      "simd_active_threads_mask = 0xFFFFFFFF; simd_all/any correct. RT-ISA-FIX re-proved: "
                      "`simd_ballot(lane<5)` = 0x1F (=31) all lanes, compiled bytes `17 17 54 ..` (byte+1==0x17) "
                      "-- which the old byte+1==0x07 gate mis-decoded as unpack_convert; the low-nibble match "
                      "now names it correctly. Field bit layout inferred (byte-diff).",
    },
    # ======================================================================
    # ATOMICS  (EXP-0018, HW-validated)  -- memory-family (byte0 0x67), NOT a
    # CAS/retry loop. Device atomics with a uniform address are optimized to a
    # SIMD-group reduce (simd_reduce) + elect-one-lane (0f05/0f06 mask) + ONE
    # native RMW; the RMW itself is a single instruction.
    # ======================================================================
    # Device atomic RMW, elected-lane (reduced) form: byte0 0x67, byte+1 0x11.
    # Operation selector at byte+12 (HW splice-proven). base_slot at byte+4.
    {
        "mnemonic": "atomic_rmw",
        "length": 14,
        "match": [(0, 8, 0x67), (8, 8, 0x11)],
        "fields": [
            {"name": "b2",        "start": 16, "width": 8, "type": "raw"},
            {"name": "b3",        "start": 24, "width": 8, "type": "raw"},
            {"name": "base_slot", "start": 32, "width": 8, "type": "imm"},   # buffer slot (=loads)
            {"name": "mid",       "start": 40, "width": 56, "type": "raw"},  # addr/data regs
            {"name": "op",        "start": 96, "width": 8, "type": "opcode",
             "enum": {0x20: "add", 0x36: "sub", 0x22: "and", 0x2c: "or", 0x3e: "xor",
                      0x28: "smax", 0x2a: "smin", 0x38: "umax", 0x3a: "umin", 0x26: "fadd"}},
            {"name": "b13",       "start": 104, "width": 8, "type": "raw"},
        ],
        "semantics": "atomic read-modify-write to buffer[base_slot] (byte+4, same slot model as "
                     "loads). Operation at byte+12: 0x20 add 0x36 sub 0x22 and 0x2c or 0x3e xor "
                     "0x28 smax 0x2a smin 0x38 umax 0x3a umin 0x26 fadd (float add). This is the "
                     "single native RMW the compiler emits AFTER a SIMD-group simd_reduce pre-"
                     "combines the per-lane operands and elects one lane (simd_is_first via "
                     "0f05/0f06 mask). NOT a CAS/retry loop. Device address space (byte+1 bit1=0).",
        "provenance": "HW-VALIDATED (EXP-0018): aggregate add (1024 threads -> counter 1024); "
                      "byte+12 splice add(0x20)->max(0x28) makes the aggregate = SIMD width (32), "
                      "add->or(0x2c) = 32 -- proves byte+12 is the operation selector; da_add_r "
                      "final counter = sum(inputs) and per-lane returns form the exact exclusive "
                      "prefix. Op codes read from the compiler's fetch_{add,sub,min,max,and,or,"
                      "xor}(+signed/unsigned) & fetch_add(float) kernels. base_slot = byte+4.",
    },
    # Standalone atomic memory op (exchange / store / compare-exchange / indexed):
    # byte0 0x67, byte+1 0x01 (device) -- no SIMD pre-reduction (per-lane distinct
    # address, or exchange/cmpxchg which cannot be reduced). Single native op.
    {
        "mnemonic": "atomic_mem",
        "length": 14,
        "match": [(0, 8, 0x67), (8, 8, 0x01)],
        "fields": [
            {"name": "b2",   "start": 16, "width": 8, "type": "raw"},
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
            {"name": "base_slot", "start": 32, "width": 8, "type": "imm"},
            {"name": "mid",  "start": 40, "width": 56, "type": "raw"},
            {"name": "op",   "start": 96, "width": 8, "type": "opcode",
             "enum": {0x3c: "exchange", 0x24: "cmpxchg", 0x60: "add_indexed"}},
            {"name": "b13",  "start": 104, "width": 8, "type": "raw"},
        ],
        "semantics": "standalone atomic memory op (single native instruction, no retry loop). "
                     "byte+12: 0x3c exchange (also atomic_store, which discards the result), "
                     "0x24 compare-exchange (the returned old value feeds a following icmp that "
                     "computes the weak-cmpxchg bool; NO hardware retry loop), 0x60 = per-lane "
                     "indexed atomic add. Device space (byte+1 bit1=0); threadgroup sets the "
                     "byte+1 threadgroup bit (0x02), base_slot 0x08 -- same address-space model "
                     "as EXP-0012 memory ops.",
        "provenance": "HW-VALIDATED behaviour (EXP-0018): atomic_exchange / atomic_store lower to "
                      "byte+12=0x3c; compare_exchange_weak to 0x24 with a following compare and NO "
                      "backward jump; da_add_idx (distinct per-lane address) emits a single 0x67 "
                      "op with no simd_reduce. Threadgroup atomics use byte+1 bit1 (0x02) + "
                      "base_slot 0x08. Full field bit-packing inferred (byte-diff).",
    },
    # SIMD-group cooperative-MATRIX multiply-accumulate (DEDICATED matrix HW).
    # byte0 0xcf, 12 bytes. ONE 0xcf executes a full 8x8-by-8x8 tile MAC across
    # the 32-lane SIMD-group: d = a*b (+ c). Proven dedicated (not FMA/shuffle
    # emulation) by diff vs a hand-written FMA matmul (EXP-0022): the simdgroup
    # kernel contains this novel 0xcf group; the FMA control contains ZERO. The
    # MPP tensor matmul2d lowers to the SAME 0xcf (259 of them for 32x32x32).
    # simdgroup_load / simdgroup_store are ordinary 0x67 / 0xe7 memory ops (each
    # lane load/stores its 2 of the 64 tile elements as a 64-bit reg pair), NOT
    # matrix instructions; make_filled is 0x2c/0x3c constant splats.
    {
        "mnemonic": "matrix_mac",
        "length": 12,
        "match": [(0, 8, 0xcf)],
        "fields": [
            {"name": "dtype",    "start": 8,  "width": 8, "type": "enum",
             "enum": {0x00: "f16(16-bit)", 0x02: "f32/bf16(32-bit)"}},         # byte+1 (HW: 0x02->0x00 garbles fp32)
            {"name": "mode",     "start": 16, "width": 8, "type": "enum",
             "enum": {0x56: "standalone", 0x54: "tiled/MPP"}},                 # byte+2 (HW: 0x56->0x54 zeroes standalone)
            {"name": "a_desc",   "start": 24, "width": 8, "type": "raw"},      # byte+3 A-operand sub-descriptor (HW: corrupt -> ZERO)
            {"name": "pad4",     "start": 32, "width": 8, "type": "raw"},      # byte+4 splice-inert (padding)
            {"name": "a_reg",    "start": 40, "width": 8, "type": "reg"},      # byte+5 A (LEFT) multiply operand (HW splice)
            {"name": "b_reg",    "start": 48, "width": 8, "type": "reg"},      # byte+6 B (RIGHT) multiply operand (HW splice)
            {"name": "c_src",    "start": 56, "width": 8, "type": "reg"},      # byte+7 C accumulator source (HW)
            {"name": "dst",      "start": 64, "width": 8, "type": "reg"},      # byte+8 destination fragment reg (HW splice)
            {"name": "dst_desc", "start": 72, "width": 8, "type": "raw"},      # byte+9 dst sub-descriptor (bit1 splice-inert)
            {"name": "op_enable","start": 80, "width": 8, "type": "opcode"},   # byte+10 op-enable marker 0x24 (HW: corrupt -> C passthrough)
            {"name": "acc_en",   "start": 88, "width": 1, "type": "enum",
             "enum": {0: "multiply", 1: "multiply_accumulate"}},              # byte+11 bit0 (HW-proven)
            {"name": "b11hi",    "start": 89, "width": 7, "type": "raw"},      # byte+11 hi bits
        ],
        "semantics": "d = a*b (+ c)  ; DEDICATED 8x8 cooperative-matrix multiply-accumulate over the "
                     "32-lane SIMD-group. One 0xcf = one full 8x8x8 tile MAC (r[i][j] += sum_k "
                     "a[i][k]*b[k][j], row-major). OPERAND SELECTORS (all HW-splice-validated, EXP-O2C, "
                     "on mad_f32 read back over one 32-lane simdgroup): byte+5 = A (LEFT) multiply-operand "
                     "fragment register (splice +5 to B's reg -> B*B; swap +5/+6 -> B*A -- matmul is "
                     "non-commutative so all A*B/B*A/A*A/B*B distinguishable); byte+6 = B (RIGHT) operand "
                     "register; byte+7 = C accumulator source register; byte+8 = destination fragment "
                     "register; byte+3 = an A-operand sub-descriptor (corrupting -> ZERO result: "
                     "load-bearing); byte+10 = op-enable marker 0x24 (corrupting -> C passthrough, the "
                     "multiply drops out); byte+4 and byte+9 bit1 splice-inert (padding). dtype (byte+1): "
                     "0x00 = 16-bit (half), 0x02 = 32-bit (float; bfloat shares the 32-bit datapath with "
                     "input conversion; splicing 0x02->0x00 garbles fp32). mode (byte+2): 0x56 standalone, "
                     "0x54 tiled (MPP matmul2d) -- SEMANTIC, not a hint: splicing standalone 0x56->0x54 "
                     "ZEROES the result (tiled mode sources its accumulator from the MPP tile context). "
                     "ACCUMULATE-ENABLE = byte+11 bit0 (1 -> a*b+c, 0 -> a*b; simdgroup_multiply clears it). "
                     "MSL element types: half, float, bfloat (incl. mixed half/bfloat -> float accumulate); "
                     "integer matrices REJECTED (no int8 cooperative matrix). Only 8x8 exposed. ALL MPP "
                     "tensor ops (matmul2d multiply/multiply_accumulate/transpose/f32/16x16x16/2-simdgroup) "
                     "lower to THIS SAME op -- no new tensor opcode; transpose adds 4-byte data-move ops "
                     "(ray_move family), not a new op; simdgroup_load/store (incl. transpose=true) are "
                     "ordinary 0x67/0xe7 memory ops.",
        "provenance": "HW-VALIDATED (EXP-0022 core + EXP-O2C operand decode): known 8x8 A,B,C -> correct "
                      "A*B+C for float AND half (numpy-exact, EXP-0022). EXP-O2C splice-and-observe on "
                      "mad_f32 over one 32-lane simdgroup, classifying the read-back against every candidate "
                      "product: byte+5=A operand (04->08 => B*B+C), byte+6=B operand (08->04 => A*A+C), "
                      "+5/+6 swap => B*A+C; byte+7=C src (garbage on redirect), byte+8=dst (relocates the "
                      "result), byte+3=A sub-descriptor (=> zero), byte+10=op-enable 0x24 (=> C passthrough), "
                      "byte+1=dtype (0x02->0x00 garbles fp32), byte+2=mode (standalone 0x56->0x54 => zero), "
                      "byte+11 bit0=accumulate-enable (01->00 => a*b). All-MPP-tensor-lower-to-0xcf and "
                      "transpose=moves confirmed by 0xcf-count + move-op diff across 7 matmul2d kernels.",
    },
    # ==========================================================================
    # HARDWARE RAY TRACING  (EXP-0023, byte0 low-nibble 0x4 + 0xdf)
    # ==========================================================================
    # Apple9 ray tracing is a HYBRID: dedicated hardware ray-intersection + AS-data-load
    # instructions drive a COMPILER-GENERATED (software) BVH traversal loop in the shader.
    # A hand-written Moller-Trumbore ray/triangle loop (the software control) contains
    # ZERO of these opcodes; every raytracing:: intersector / intersection_query kernel
    # contains them -> they are dedicated ray-tracing HW. The end-to-end trace was
    # HW-validated (rtval.m: known ray vs known triangle in a real acceleration structure
    # returns the correct t / primitive_id / barycentrics).
    #
    # ---- the dedicated ray-intersect op (rt_intersect, 8 bytes) --------------
    # Signature: byte0 low-nibble 0x4, byte+1 == 0xea. Appears EXACTLY TWICE per RT
    # kernel: op#1 = set up ray + kick traversal, op#2 (byte+2==0x10/0x11, trailing
    # `26 9f`) = read/commit the intersection result. Operand/mode fields byte-diffed
    # across ray/AS/function-table variants (EXP-0023 raw/intersect_diff.txt).
    {
        "mnemonic": "rt_intersect",
        "length": 8,
        "match": [(0, 4, 0x4), (8, 8, 0xea)],
        "fields": [
            {"name": "dst",   "start": 4,  "width": 4, "type": "reg"},       # byte0 hi nibble = result reg
            {"name": "subop", "start": 8,  "width": 8, "type": "opcode",
             "enum": {0xea: "trace"}},                                        # byte+1 constant intersect sub-op
            {"name": "mode",  "start": 16, "width": 8, "type": "enum",        # byte+2 mode/flags
             "enum": {0x10: "dyn_origin/motion", 0x90: "const_origin",
                      0xd0: "const_origin+fntable", 0x11: "result_read"}},
            {"name": "ray_param", "start": 24, "width": 8, "type": "reg"},    # byte+3 ray/param reg; also the MOTION TIME (0x46 device / 0x26 const)
            {"name": "as_type",   "start": 32, "width": 8, "type": "enum",    # byte+4 acceleration-structure type selector
             "enum": {0x8b: "primitive_AS", 0x1b: "instance_AS", 0xbb: "primitive_motion_AS"}},
            {"name": "b5",    "start": 40, "width": 8, "type": "raw"},        # byte+5 (0x00 observed)
            {"name": "flags", "start": 48, "width": 8, "type": "mod"},        # byte+6 bit7 = intersection-function-table present
            {"name": "b7",    "start": 56, "width": 8, "type": "raw"},        # byte+7 (0x00 observed)
        ],
        "semantics": "DEDICATED ray-intersection instruction (the raytracing:: intersect primitive). "
                     "byte0 low-nibble 0x4 = group; byte0 HIGH nibble = result/destination register; "
                     "byte+1 == 0xea = intersect sub-opcode (constant). byte+2 = mode: 0x90 const origin, "
                     "0x10 dynamic-origin OR primitive-MOTION (the time-parameterised form -- motion sets "
                     "0x10 even with a const origin), 0xd0 const-origin + intersection-function-table present "
                     "(bit7=const-origin, bit6=fn-table), 0x11 result-read. byte+3 = ray/parameter operand "
                     "register, and also carries the MOTION TIME (device-loaded time 0x46 vs folded-constant "
                     "0x26). byte+4 = AS-type selector: 0x8b primitive AS, 0x1b instance AS, 0xbb "
                     "primitive-MOTION AS (HW-validated end-to-end: motion-AS trace interpolates the hit "
                     "distance LINEARLY with the time parameter). byte+6 bit7 set when an "
                     "intersection_function_table is bound. Emitted twice: op#1 traverse, op#2 (byte+2 "
                     "0x10/0x11, trailing `26 9f`) result-read. The BVH TRAVERSAL itself is a "
                     "compiler-generated shader loop (one -88-byte back-edge per intersector) using this op "
                     "+ the 0xdf AS-loads + the 0x5f ray-data ops -- NOT a fire-and-forget trace. PRIMITIVE "
                     "TAG does not change the op (bounding_box op#1 == triangle op#1 byte-for-byte; curve "
                     "differs only in the dst-reg nibble): tag discrimination lives in the AS + "
                     "intersection-function-table. Works IDENTICALLY from a FRAGMENT shader "
                     "(supportsRaytracingFromRender, HW-validated) -- only the bind stage differs.",
        "provenance": "HW-VALIDATED role + end-to-end (EXP-0023 trace correctness of a known ray vs a known "
                      "triangle -> correct t / primitive_id / barycentrics; ZERO occurrences in a hand-written "
                      "Moller-Trumbore loop; EXP-O2C RT-from-render silhouette + motion-blur time "
                      "interpolation {t=0,.25,.5,.75,1} -> hit distances {3,3.5,4,4.5,5} exact). Field "
                      "semantics byte-diff-inferred across 8 intersector-tag + motion + payload variants: "
                      "byte+4 AS-type (8b/1b/bb), byte+2 motion=0x10, byte+3 device-vs-const time (46 vs 26), "
                      "byte+6 fn-table. Operand register bit-packing not individually splice-validated "
                      "(needs an AS-aware splice testbed).",
    },
    # ---- dedicated acceleration-structure / ray-data load (rt_as_load, 14 bytes) ----
    {
        "mnemonic": "rt_as_load",
        "length": 14,
        "match": [(0, 8, 0xdf)],
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8,  "type": "raw"},        # 0x02 observed
            {"name": "mode", "start": 16, "width": 8,  "type": "raw"},        # 0x54 (memory-family mode, cf 0x67)
            {"name": "body", "start": 24, "width": 88, "type": "raw"},        # addr / dst-reg / stride tail
        ],
        "semantics": "Dedicated acceleration-structure / ray-data load used during BVH traversal "
                     "(byte0 0xdf, a memory-family sibling of the 0x67/0xe7 buffer load/store: byte+2 == "
                     "0x54 like the memory ops). Fetches BVH node / ray / traversal-stack data. 14-17 per "
                     "intersector kernel, ~37 in an inline intersection_query. Field bit-packing inferred "
                     "(byte-diff); not individually splice-validated.",
        "provenance": "inferred (byte-diff, EXP-0023): byte0 0xdf group present in every raytracing:: "
                      "kernel and ABSENT from the hand-written software triangle loop; 14-byte length "
                      "tokenizes the RT streams cleanly. Memory-family shape (byte+2==0x54) mirrors the "
                      "HW-validated 0x67/0xe7 loads (EXP-0012).",
    },
    # ---- ray-data / traversal-stack memory op (rt_ray_mem, 14 bytes, EXP-O2C) --------
    {
        "mnemonic": "rt_ray_mem",
        "length": 14,
        "match": [(0, 8, 0x5f), (8, 8, 0x02)],   # EXP-M4-13 R4: re-keyed byte+2==0x54 -> byte+1==0x02
        "fields": [
            {"name": "mode", "start": 16, "width": 8, "type": "enum",
             "enum": {0x54: "mem_54", 0x56: "mem_56", 0x04: "mode_04", 0x64: "mode_64"}},
            {"name": "body", "start": 24, "width": 88, "type": "raw"},        # addr / dst-reg / stride tail
        ],
        "semantics": "RAY-TRACING ray-data / traversal-stack memory op. byte0 0x5f (low-nibble 0xf, the "
                     "memory-family low nibble, sibling of the 0xdf AS-load and the 0x67/0xe7 buffer "
                     "load/store), byte+2 == 0x54 (memory-op marker). The store/spill-side companion of the "
                     "0xdf AS-data load: fetches/spills the ray struct + per-node BVH traversal-stack state "
                     "during the (software) traversal loop, and carries the ray_data PAYLOAD copy-in/out for "
                     "custom intersection functions (its count scales with payload size: float2 -> 13, "
                     "8-float -> 15, no payload -> 12; instance-motion -> 28). byte+1 = sub-op / addressing "
                     "form (0x00/0x02/0x10/0x11; 0x10/0x11 mirror the 0x67 load space+index byte). Confirms "
                     "ray_data is a distinct address space backed by RT scratch (RT kernels emit zero "
                     "threadgroup ops and only one device store = the output).",
        "provenance": "inferred (byte-diff, EXP-O2C): byte0 0x5f present in every raytracing:: kernel "
                      "(12-28 per kernel) and ABSENT from a hand-written software triangle loop (EXP-0023 "
                      "control). 14-byte length + byte+2==0x54 tokenizes the RT streams (memory-family shape "
                      "mirrors the HW-validated 0x67/0xe7/0xdf). Payload-size correlation from "
                      "call_p2/call_pbig/call_pnone diff. Field bit-packing not splice-validated.",
    },
    # ---- rt_ray_mem load-INDEX variant (12B) and SHORT form (6B), EXP-M4-13 R4 ----
    {
        "mnemonic": "rt_ray_mem_ldidx",
        "length": 12,
        "match": [(0, 8, 0x5f), (8, 8, 0x10), (16, 8, 0x54)],
        "fields": [
            {"name": "body", "start": 24, "width": 72, "type": "raw"},
        ],
        "semantics": "RAY-TRACING ray-data memory op, load-INDEX variant (12B). byte0 0x5f, byte+1 == 0x10, "
                     "byte+2 == 0x54. Mirrors the 0x67 device-load space+index addressing byte (byte+1 low "
                     "nibble 0 = indexed). 12 bytes (NOT 14): all 32 corpus occurrences sit back-to-back at "
                     "gap 12. The old blunt byte+2-only rule wrongly gave it 14.",
        "provenance": "byte-diff EXP-M4-13 R4 (own-MSL): back-to-back spacing = 12 across 32 occurrences "
                     "(rq_pred / RT-query kernels). Length bracketed by the next 0x5f leader; body raw. Not "
                     "splice-validated.",
    },
    {
        "mnemonic": "rt_ray_mem_short",
        "length": 6,
        "match": [(0, 8, 0x5f), (8, 8, 0x11), (16, 8, 0x54)],
        "fields": [
            {"name": "b3",   "start": 24, "width": 8,  "type": "raw"},
            {"name": "tail", "start": 32, "width": 16, "type": "raw"},
        ],
        "semantics": "RAY-TRACING ray-data memory op, SHORT form (6B). byte0 0x5f, byte+1 == 0x11 (the 0x67 "
                     "load index+1 addressing byte), byte+2 == 0x54, body `<b3> 00 00`. 6 bytes: ALL 92 corpus "
                     "occurrences sit back-to-back at gap 6. The old blunt byte+2-only rule wrongly gave it 14.",
        "provenance": "byte-diff EXP-M4-13 R4 (own-MSL): back-to-back spacing = 6 across 92 occurrences "
                     "(rq_pred / RT-query kernels). Length bracketed by the immediately-following 0x5f leader. "
                     "Not splice-validated.",
    },
    # ---- ray-vs-node transform / box-test companion (rt_transform_test, 10 bytes, EXP-O2C) ----
    {
        "mnemonic": "rt_transform_test",
        "length": 10,
        "match": [(0, 4, 0x2), (16, 8, 0x27), (24, 8, 0x81), (32, 8, 0x22)],
        "fields": [
            {"name": "dst",     "start": 4,  "width": 4,  "type": "reg"},     # byte0 hi nibble = dst reg
            {"name": "src",     "start": 8,  "width": 8,  "type": "reg"},     # byte+1 source reg
            {"name": "marker",  "start": 16, "width": 8,  "type": "raw"},     # byte+2 == 0x27 marker
            {"name": "b3",      "start": 24, "width": 8,  "type": "raw"},     # byte+3 == 0x81
            {"name": "cmpmode", "start": 32, "width": 8,  "type": "raw"},     # byte+4 == 0x22 ordered-compare-like mode
            {"name": "body",    "start": 40, "width": 40, "type": "raw"},     # byte+5..+9 transform/test tail
        ],
        "semantics": "RAY-TRACING transform / box-test companion op. byte0 low-nibble 0x2 (high nibble = dst "
                     "reg), byte+2 == 0x27 (marker), byte+3 == 0x81, byte+4 == 0x22 (an ordered-compare-like "
                     "mode). ~4-5 per intersector kernel; the ray-vs-node coordinate transform / AABB "
                     "slab-test arithmetic executed inside the (software) traversal loop, distinct from the "
                     "dedicated rt_intersect primitive. Gate on byte+2 == 0x27 to distinguish from the other "
                     "low-nibble-2 ops (0x02 iminmax byte+2 0x1e, 0x12 icmpsel, 0x32 carry-gen byte+2 0x35). "
                     "In motion kernels the tail differs (time-blended transform).",
        "provenance": "inferred (byte-diff, EXP-O2C): the '0x?2 byte+2==0x27 transform/test op' flagged as a "
                      "follow-up in EXP-0023; present 4-5x in every intersector and absent from the software "
                      "control. Length 10 tokenizes the RT streams. Not splice-validated.",
    },
    # ---- ray register-marshalling MOVE (ray_move, 4 bytes, EXP-O2C) ------------------
    {
        "mnemonic": "ray_move",
        "length": 4,
        "match": [(0, 4, 0xb), (16, 8, 0x81)],
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},         # byte0 hi nibble = dst reg
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},         # byte+1 source reg
            {"name": "form", "start": 16, "width": 8, "type": "enum",
             "enum": {0x81: "copy_reg(b3=0x08)", 0x80: "zero_init(b3=0x00)"}}, # byte+2 form
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},         # byte+3 (0x08 copy / 0x00 zero)
        ],
        "semantics": "RAY register-marshalling MOVE (4 bytes). byte0 low-nibble 0xb, HIGH nibble = "
                     "destination register; byte+1 = source register. Marshals the ray fields "
                     "(origin.xyz / direction.xyz / min_distance / max_distance, and the ray_data payload) "
                     "into the contiguous register block the rt_intersect op consumes, and moves results out. "
                     "byte+2 == 0x81 (byte+3 == 0x08) = copy a computed source register; byte+2 == 0x80 "
                     "(byte+1 == 0x00, byte+3 == 0x00) = zero-initialise a component (e.g. a const origin "
                     "float3(0,0,0)). A compact move in the 0xNb family (sibling of the compact "
                     "call-argument move / uniform_mov); disambiguated by byte+2 in {0x80,0x81}. The SAME op "
                     "is reused (35-38 per kernel) to marshal MPP matmul2d TRANSPOSE tile data -- i.e. matrix "
                     "transpose is data movement, not a matrix opcode.",
        "provenance": "inferred (byte-diff, EXP-O2C): the 'RT-specific 4-byte moves in the 0x?b group, "
                      "byte+2 0x81/0x80' flagged in EXP-0023. Present in every RT kernel marshalling the ray "
                      "struct (zero-init 0x80 for const origins, copy 0x81 for device-loaded direction), and "
                      "35-38x in the matmul2d transpose kernels. Not splice-validated.",
    },
    # ==========================================================================
    # SCOREBOARD / ASYNC-WAIT MODEL  (EXP-0025)
    # ==========================================================================
    # HEADLINE (HW-validated, EXP-0025): G17P has NO explicit per-op scoreboard WAIT
    # instruction in the compute stream. Device load/store, atomics and texture
    # sample/read feed their consumers DIRECTLY -- there is no wait/barrier op between
    # the async op and the instruction that reads its result. This is a fundamental
    # departure from G13 (Mesa `agx_insert_waits.c`: a 2-byte `wait` op + a 2-slot
    # software scoreboard, AGX_MAX_PENDING=8). On G17P completion is enforced by a
    # HARDWARE register interlock: an async op marks its destination register pending;
    # a consumer that reads that register stalls in HW until the op retires.
    # PROOF: add2 (a+b, fadd immediately after 2 loads), gather (a[idx[i]] -- load2's
    # ADDRESS depends on load1's result), loaduse (v*v+3), and manyload20 (TWENTY
    # independent device loads outstanding, summed) ALL return correct results with
    # zero scheduling slack and ZERO wait ops -- impossible without a HW interlock.
    # 20 in-flight >> G13's 8, so "max in flight" is a HW resource (bounded by the
    # register file), NOT a compiler-emitted AGX_MAX_PENDING constant.
    #
    # The ONE explicit ordering primitive the compute compiler emits is the
    # threadgroup / execution BARRIER below -- for CROSS-LANE threadgroup-memory
    # visibility, which a per-lane register interlock cannot provide.
    {
        "mnemonic": "threadgroup_barrier",
        "length": 6,
        "match": [(0, 8, 0x07), (16, 8, 0x54)],   # byte0 0x07, byte+2 0x54
        "fields": [
            {"name": "sub",       "start": 8,  "width": 8, "type": "raw"},   # byte+1 = 0x04
            {"name": "mem_scope", "start": 24, "width": 8, "type": "enum",   # byte+3 = fenced memory scope
             "enum": {0x61: "threadgroup", 0x85: "device"}},
            {"name": "flags",     "start": 32, "width": 8, "type": "mod"},   # byte+4 (0x09 tg / 0x08 dev)
            {"name": "b5",        "start": 40, "width": 8, "type": "raw"},   # byte+5 = 0x00
        ],
        "semantics": "threadgroup_barrier(mem_flags) -- execution barrier + memory fence. 6 bytes: "
                     "07 04 54 <mem_scope> <flags> 00. byte+3 = fenced memory scope: 0x61 = threadgroup "
                     "(mem_threadgroup), 0x85 = device (mem_device). Makes threadgroup-memory stores by "
                     "OTHER lanes visible before the barrier returns; the compiler emits it between a "
                     "threadgroup store and a cross-lane threadgroup load. It is the ONLY explicit "
                     "ordering/'wait' op in the compute stream (device load/store/atomic/texture are "
                     "HW-register-interlocked, not scoreboard-waited). simdgroup_barrier emits no 0x07 "
                     "op (a 32-lane SIMD-group is lockstep). Removing/neutralising the fence -> silent "
                     "stale threadgroup reads (no fault).",
        "provenance": "HW-VALIDATED (EXP-0025): tgbar vs tgbar_none differ by EXACTLY these 6 bytes "
                     "(threadgroup_barrier presence); tgbar_dev (mem_device) has byte+3=0x85/byte+4=0x08 "
                     "vs threadgroup 0x61/0x09 -> byte+3 is the memory-scope field. SPLICE-PROVEN: on a "
                     "256-thread divergent-writer kernel, splicing byte+3 0x61->0x00 neutralises the "
                     "threadgroup fence and 128/256 lanes read STALE ZEROS (STATUS OK, no fault), exactly "
                     "reproducing the compiler's barrier-less race; the intact barrier reads 0 stale. "
                     "byte+4 (0x09->0x00) splice was benign. byte+1/byte+5 inferred (byte-diff).",
    },
    # ---- atomic_thread_fence device memory fence (mem_fence, 6 bytes, EXP-O2D) --------
    # Same 0x07 fence family as threadgroup_barrier / pixel_order, but WITHOUT the added
    # execution barrier: atomic_thread_fence(mem_flags::mem_device, seq_cst) = a pure memory
    # fence. Distinguished from threadgroup_barrier by byte+3 == 0x84 (device-memory FENCE;
    # cf. the barrier's byte+3 0x85 device = 0x84|0x01, the 0x01 bit = the execution barrier)
    # + byte+4 == 0x0a (device memory-class flag). More-specific match wins over the barrier.
    {
        "mnemonic": "mem_fence",
        "length": 6,
        "match": [(0, 8, 0x07), (16, 8, 0x54), (24, 8, 0x84)],   # byte0 0x07, byte+2 0x54, byte+3 0x84
        "fields": [
            {"name": "sub",      "start": 8,  "width": 8, "type": "raw"},   # byte+1 = 0x04
            {"name": "memclass", "start": 32, "width": 8, "type": "mod"},   # byte+4 = 0x0a device memory-class flag
            {"name": "b5",       "start": 40, "width": 8, "type": "raw"},   # byte+5 = 0x00
        ],
        "semantics": "atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst[, thread_scope_device]) "
                     "-- a standalone DEVICE-memory ordering fence with no execution barrier. 6 bytes: "
                     "07 04 54 84 0a 00. byte+3 == 0x84 = device-memory fence (vs threadgroup_barrier's 0x85 "
                     "device = 0x84|0x01, the 0x01 being the added EXECUTION barrier); byte+4 == 0x0a = "
                     "device memory-class flag. Ordering is realised by fence PRESENCE, not a bit on the "
                     "0x67 atomic RMW op: memory_order_relaxed emits NO fence, seq_cst emits this fence "
                     "(acquire/release/acq_rel are REJECTED by MSL). Scope GATES emission: thread/simdgroup/"
                     "threadgroup scope emit no device fence; thread_scope_device (default) does. The texture "
                     "fence (mem_texture) is a byte+4==0x06 pair that decodes as pixel_order (same family).",
        "provenance": "inferred (byte-diff, EXP-O2D): byte-diff of the atomic_thread_fence probe "
                      "(flags x order x scope) against the no-fence baseline. Consistent with the "
                      "HW-splice-validated EXP-0025 threadgroup_barrier / EXP-0029 pixel_order 0x07 family; "
                      "the fence-only form is byte-diff-inferred (a fence's effect only manifests under "
                      "contention, so not splice-validated in isolation).",
    },
    # ---- compute memory / SCOREBOARD FENCE (byte0 0x07, byte+2 in {0x00,0x02}, 4B) --
    # A short (4-byte) fence the compiler inserts around out-of-line CALLs and around
    # divergent control flow -- distinct from the 6-byte threadgroup_barrier / mem_fence
    # (which all carry byte+2==0x54). byte+1 varies (0x22 before a call, 0x02/0x00 around
    # break/continue). It orders the register/scoreboard state across the branch, not
    # cross-lane threadgroup memory. Length + descriptor added by RT-ISA-FIX: RT-1b's census
    # halted strict tokenization on `07 22 02 00` (no length rule); this closes that gap.
    {
        "mnemonic": "scoreboard_fence",
        "length": 4,
        # length 4 already isolates this from the 6-byte barrier/fence and 8-byte link_save
        # of the same 0x07 family; byte+2 bit0==0 covers both observed forms (0x00, 0x02).
        "match": [(0, 8, 0x07), (16, 1, 0)],
        "fields": [
            {"name": "sub",  "start": 8,  "width": 8, "type": "raw"},   # byte+1 (0x22 pre-call, 0x02/0x00 CF)
            {"name": "b2",   "start": 16, "width": 8, "type": "raw"},   # byte+2 (0x02 / 0x00)
            {"name": "tail", "start": 24, "width": 8, "type": "raw"},   # byte+3 (0x00)
        ],
        "semantics": "compute memory / scoreboard fence (4 bytes): 07 <sub> <b2> 00. A short ordering fence "
                     "the compiler inserts before an out-of-line CALL (`07 22 02 00`, immediately preceding the "
                     "43 frame marker) and around break/continue divergence (`07 02 00 00` / `07 00 00 00`). "
                     "byte+2 in {0x00,0x02} distinguishes it from the 6-byte threadgroup_barrier / mem_fence / "
                     "pixel_order (byte+2==0x54) of the same 0x07 family. Orders scoreboard/register state "
                     "across the control-flow edge; NOT a cross-lane threadgroup-memory barrier.",
        "provenance": "HW-observed byte-diff (RT-ISA-FIX): `07 22 02 00` precedes every out-of-line call in the "
                     "RT-1b stress census (followed by 43 00 00 01); `07 02 00 00` / `07 00 00 00` appear around "
                     "break/continue in our for/while/nested CF kernels (which run correct on HW). Length 4 "
                     "gives clean whole-kernel tokenization. Fields byte-diff (role not splice-isolated -- a "
                     "fence's effect only manifests under a data hazard).",
    },
    # ---- compact float accumulate (EXP-0025 + RT-1a-FIX): 4-byte float-ALU form
    # NOT a scoreboard wait (byte0 0x38 was the G13 `wait` opcode, so this was the
    # prime suspect). Disproven on hardware: it is a 4-byte float ADD. In an N-value
    # sum the reduction emits exactly N-1 additions = (6-byte 0x3c fadds) + (these
    # 4-byte ops); a byte+3 sweep changes the arithmetic result (byte+3 is a
    # source-register selector), which a wait mask would not do.
    # RT-1a-FIX (item 4): the compact accumulate has TWO byte+2 forms -- 0x38 AND 0x18
    # (they differ only in bit5, 0x20). Both are the SAME op: falubank's a2+..+a7
    # reduction emits both, splicing a 0x18 op's byte+2 0x18<->0x38 leaves out2
    # unchanged (=33), and redirecting a 0x18 op's dst zeros out2 (load-bearing add).
    # The old match `byte+2==0x38` decoded the 0x38 form but the 0x18 form RAISED
    # ("no descriptor matches 190b1809") and halted tokenization. Match now pins the
    # invariant bits [16:21]==0x18 and [22:24]==0 (leaving bit21, the 0x20 bit, as a
    # source-cache/last-use hint field like the 0x54/0x56 reduce bit).
    {
        "mnemonic": "falu_acc",
        "length": 4,
        # EXP-M4-13 R2 (n9_falu): GENERALISED match to cover byte+2 in {0x18,0x19,0x38,0x39} so
        # the compact MUL continuation (0x19/0x39) decodes alongside the add (0x18/0x38). bits
        # [17:21]==0b1100 fix the accumulate class; byte+2 bit0 (op) = add(0)/mul(1), bit5 = cache.
        "match": [(0, 4, 0x9), (17, 4, 12), (22, 2, 0)],
        "fields": [
            {"name": "dst",   "start": 4,  "width": 4, "type": "reg"},   # byte0 hi nibble = dst (accumulator)
            {"name": "srcA",  "start": 8,  "width": 8, "type": "reg"},   # byte+1 = srcA / accumulator descriptor
            {"name": "op",    "start": 16, "width": 1, "type": "opcode",  # byte+2 bit0 = add/mul
             "enum": {0: "fadd_acc", 1: "fmul_acc"}},
            {"name": "cache", "start": 21, "width": 1, "type": "mod"},   # byte+2 bit5 (0x18 vs 0x38) source cache/last-use hint
            {"name": "srcB",  "start": 24, "width": 8, "type": "reg"},   # byte+3 = srcB (reg<<1)|size
        ],
        "semantics": "d = srcA (+) srcB  ; COMPACT 4-byte float accumulate (float-ALU group low-nibble "
                     "9, byte+2 in {0x18,0x38} = opsel with the arithmetic-enable bit clear vs the 6-byte "
                     "0x3c fadd). Omits the byte+4/+5 modifier tail of the 6-byte falu2, so the compiler "
                     "emits it for plain reduction accumulates. byte+3 = srcB register descriptor. byte+2 "
                     "bit5 (`cache`: 0x18 vs 0x38) is a source-cache/last-use hint, NOT an op change "
                     "(RT-1a-FIX: splice 0x18<->0x38 leaves the reduction result unchanged).",
        "provenance": "HW-VALIDATED (EXP-0025 + RT-1a-FIX): in a 10-value sum (manyload) the stream has 6 "
                     "six-byte 0x3c/0x1c fadds + 3 of these ops = 9 adds (exactly N-1), summing correctly "
                     "(1023). RT-1a-FIX re-validated the 0x18 form (falubank a2..a7 reduction): 0x18<->0x38 "
                     "interchangeable (out2=33 either way); redirecting the final 0x18 op's dst zeroes out2 "
                     "(load-bearing add). raw/undecoded.log. Field bit-packing beyond byte+3 inferred.",
    },

    # ========================================================================
    # FRAGMENT STAGE (EXP-0029) — varying interpolation, colour output/epilog,
    # tilebuffer read (programmable blend), depth, and pixel ordering (ROG).
    # These groups are fragment-only; compute never emits them. Where a byte0
    # group is shared with a compute op (0x2f/0xaf, 0x67/0xe7, 0x1f, 0x07) the
    # match/length is gated on a fragment-specific byte signature (byte+2==0x54
    # for the coefficient/attribute forms, byte+1==0x06/0x0e for the tile
    # store/read) so compute decoding is unaffected. See EXP-0029-fragment-isa.
    # ========================================================================
    {
        "mnemonic": "iter",
        "length": 10,
        "match": [(0, 7, 0x2f), (16, 8, 0x54), (56, 8, 0x02)],   # byte0 0x2f/0xaf, byte+2==0x54, byte+7==0x02
        "fields": [
            {"name": "grp",   "start": 0,  "width": 8, "type": "raw"},   # byte0 0x2f/0xaf (bit7 = fn_hi)
            {"name": "lead",  "start": 8,  "width": 8, "type": "raw"},   # byte+1: 0x0d leading op / 0x05 subsequent
            {"name": "dst",   "start": 24, "width": 8, "type": "reg"},   # byte+3 = destination GPR (reg<<1)
            {"name": "c4",    "start": 32, "width": 8, "type": "raw"},   # byte+4 == 0x03 (const)
            {"name": "src_slot", "start": 40, "width": 8, "type": "imm"},# byte+5 = source varying-slot / per-triangle coeff index (slot<<1)  HW-VALIDATED
            {"name": "mode",  "start": 48, "width": 8, "type": "enum",   # byte+6 interpolation-location / coefficient select
             "enum": {"0": "center/linear", "2": "centroid/sample", "4": "perspective-denominator(W)"}},
            {"name": "c7",    "start": 56, "width": 8, "type": "raw"},   # byte+7 == 0x02
            {"name": "tail",  "start": 64, "width": 16, "type": "raw"},  # byte+8/+9 (0x10 center / 0x08 centroid|sample / 0x20 last)
        ],
        "semantics": "r_dst = interpolate(varying_slot=src_slot, mode)  ; per-fragment varying "
                     "interpolation ('iter'). One op per float4 component. byte+5 = the per-triangle "
                     "varying/coefficient slot (slot<<1); byte+3 = destination GPR; byte+6 = interpolation "
                     "location: 0x00 pixel-centre/linear, 0x02 centroid or per-sample (paired with the "
                     "8-byte iter_at setup + a 0x04/0x03 position preamble), 0x04 the perspective "
                     "denominator (W) channel. PERSPECTIVE-CORRECT interpolation is a multi-instruction "
                     "lowering, NOT a single mode bit: linear component iters (byte+6==0x00) + a W-denominator "
                     "iter (byte+6==0x04) + a 0xaf reciprocal (rcp of interpolated 1/w) + a per-component "
                     "fmul. [[flat]] uses the separate 6-byte iter_flat op instead (no barycentric interp). "
                     "The pull-model interpolate_at_center/centroid/sample compile BYTE-IDENTICALLY to the "
                     "matching [[*_perspective]] qualifier.",
        "provenance": "HW-VALIDATED (EXP-0029): splicing byte+5 0x00->0x02 on interp_noperspective switched "
                     "the red output from color.x (x-gradient) to color.y (y-gradient) -> byte+5 selects the "
                     "source varying coefficient (splice-and-render). flat vs interpolated proven behaviourally "
                     "(flat = constant provoking-vertex value at all pixels; interpolated = gradient). "
                     "perspective/no-perspective/centroid/sample all differentiated by differential compilation; "
                     "perspective/linear/flat produce three distinct pixels under w-varying geometry (persp_* "
                     "kernels). byte+6 mode values and the byte+8 last/location bits are byte-diff-localised.",
    },
    {
        "mnemonic": "iter_at",
        "length": 8,
        "match": [(0, 7, 0x2f), (16, 8, 0x54), (48, 8, 0x0a)],   # byte0 0x2f/0xaf, byte+2==0x54, byte+6==0x0a
        "fields": [
            {"name": "grp",   "start": 0,  "width": 8, "type": "raw"},
            {"name": "lead",  "start": 8,  "width": 8, "type": "raw"},   # byte+1 (0x14 centroid / 0x04 sample setup)
            {"name": "dst",   "start": 24, "width": 8, "type": "reg"},
            {"name": "c4",    "start": 32, "width": 8, "type": "raw"},   # byte+4 == 0x03
            {"name": "b5",    "start": 40, "width": 8, "type": "raw"},   # byte+5
            {"name": "loc",   "start": 56, "width": 8, "type": "enum",   # byte+7 = sampling-location kind
             "enum": {"1": "centroid", "3": "sample"}},
        ],
        "semantics": "interpolate-at SETUP: computes the custom barycentric coordinate for centroid / "
                     "per-sample / interpolate_at_* interpolation, consumed by the following iter ops "
                     "(which carry byte+6==0x02). byte+7 = 0x01 centroid, 0x03 sample. Preceded by a "
                     "sample/centroid-position preamble read (byte0 0x04 centroid / 0x03 sample).",
        "provenance": "inferred (byte-diff, EXP-0029): present only in centroid/sample/interpolate_at "
                     "fragments (absent from center/flat); byte+7 = 0x01 (centroid) vs 0x03 (sample) is the "
                     "sole difference between the interp_centroid and interp_sample setup ops. 8-byte length "
                     "tokenises those streams to 0 leftover.",
    },
    {
        "mnemonic": "iter_flat",
        "length": 6,
        "match": [(0, 8, 0x1f), (16, 8, 0x54)],
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8, "type": "raw"},
            {"name": "sel",  "start": 24, "width": 8, "type": "raw"},   # byte+3 = attribute/slot selector
            {"name": "b4",   "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",   "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "flat varying load: reads the provoking-vertex attribute directly (NO barycentric "
                     "interpolation), one 6-byte op per component. Emitted for [[flat]] (nointerpolation). "
                     "Distinct byte0 (0x1f) and length from the 10-byte perspective/linear iter op.",
        "provenance": "HW-VALIDATED behaviour (EXP-0029): the [[flat]] fragment renders a CONSTANT colour "
                     "(the provoking-vertex value 0,0,0.25,1) at all 16 pixels of a 4x4 target while the "
                     "interpolated variants show a gradient. Four 6-byte 0x1f ops (one per float4 lane) "
                     "tokenise interp_flat to 0 leftover. Field bit-packing inferred (byte-diff).",
    },
    {
        "mnemonic": "frag_color_store",
        "length": 12,
        "match": [(0, 8, 0xe7), (8, 8, 0x06)],
        "fields": [
            {"name": "b2",       "start": 16, "width": 8, "type": "raw"},   # 0x54
            {"name": "src",      "start": 24, "width": 8, "type": "reg"},   # byte+3 = source colour register
            {"name": "b4",       "start": 32, "width": 8, "type": "raw"},
            {"name": "rt_index", "start": 40, "width": 8, "type": "imm"},   # byte+5 = render-target index (rt<<1)  HW-VALIDATED
            {"name": "b6",       "start": 48, "width": 8, "type": "raw"},   # 0x01
            {"name": "b7",       "start": 56, "width": 8, "type": "raw"},   # 0x4e
            {"name": "tail",     "start": 64, "width": 32, "type": "raw"},
        ],
        "semantics": "store a fragment colour output to the tilebuffer / colour attachment. Memory-family "
                     "store (byte0 0xe7) with the FRAGMENT variant byte+1==0x06 (compute device store is "
                     "byte+1==0x00, 14 bytes). byte+3 = source colour GPR, byte+5 = render-target index "
                     "(rt<<1): RT0=0x00, RT1=0x02, RT2=0x04. Each RT store is bracketed by 0x87 tile-access "
                     "setup ops. The colour values are packed into GPRs by preceding 0x97 ops. discard_fragment "
                     "suppresses the store (killed fragments write nothing).",
        "provenance": "HW-VALIDATED (EXP-0029): splicing byte+5 0x00->0x02 (store to the absent RT1) leaves "
                     "RT0 at the clear colour -> byte+5 is the render-target index; corrupting byte+1 "
                     "0x06->0x00 neutralises the store (RT0 stays clear) -> byte+1==0x06 is the fragment "
                     "tile-store variant. The 3-target out_mrt kernel emits three such stores with byte+3/"
                     "byte+5 = r2/0x04, r1/0x02, r0/0x00 (per-RT source reg + RT index). discard proven: "
                     "the x<2 half of out_discard2 keeps the clear colour (fragment killed).",
    },
    {
        "mnemonic": "tile_read",
        "length": 12,
        "match": [(0, 8, 0x67), (8, 8, 0x0e)],
        "fields": [
            {"name": "b2",   "start": 16, "width": 8, "type": "raw"},   # 0x54
            {"name": "dst",  "start": 24, "width": 8, "type": "reg"},   # byte+3 = destination GPR
            {"name": "b4",   "start": 32, "width": 8, "type": "raw"},
            {"name": "rt_index", "start": 40, "width": 8, "type": "imm"},
            {"name": "b6",   "start": 48, "width": 8, "type": "raw"},   # 0x01
            {"name": "b7",   "start": 56, "width": 8, "type": "raw"},   # 0xce
            {"name": "tail", "start": 64, "width": 32, "type": "raw"},
        ],
        "semantics": "read the CURRENT tilebuffer / colour-attachment value into a GPR — the ld_tile analogue "
                     "for PROGRAMMABLE BLENDING (a fragment [[color(n)]] INPUT). Load-family op (byte0 0x67) "
                     "with the fragment variant byte+1==0x0e (compute device load uses byte+1 in "
                     "{0x10,0x00,0x11,...}). On Apple TBDR the framebuffer lives in tile memory, so blend is "
                     "done in-shader (EXP-0019): the shader reads the destination colour with this op and "
                     "computes the blend with ordinary float ALU, then stores with frag_color_store.",
        "provenance": "HW-VALIDATED (EXP-0029): rendering blend_read (returns src*src.a + dst*(1-src.a), "
                     "src.a=0.5) over three different clear colours produced out == src*0.5 + clear*0.5 "
                     "exactly (clear 0 -> 0.40,0.10,0.05,0.25; clear 1 -> 0.90,0.60,0.55,0.75; clear "
                     "0.4,0.6,0.8,1 -> 0.60,0.40,0.45,0.75) -> the op read the tilebuffer value and fed the "
                     "in-shader blend. Field bit-packing inferred (byte-diff).",
    },
    # ---- explicit imageblock<T>.write from a TILE / fragment shader (imageblock_store, 12B, EXP-O2D) ----
    # The same memory-family store as frag_color_store (byte0 0xe7), GENERALISED to explicit
    # imageblock<T>. This descriptor names the TILE first-access variant byte+1==0x16 (== 0x06|0x10,
    # the 0x10 bit marking the FIRST store after a 0x87 tile-access setup in a dispatchThreadsPerTile
    # tile shader); the plain byte+1==0x06 form stays named frag_color_store (subsequent / simple-MRT).
    {
        "mnemonic": "imageblock_store",
        "length": 12,
        "match": [(0, 8, 0xe7), (8, 8, 0x16), (16, 8, 0x54)],
        "fields": [
            {"name": "src",       "start": 24, "width": 8, "type": "reg"},   # byte+3 source register
            {"name": "b4",        "start": 32, "width": 8, "type": "raw"},
            {"name": "slice_off", "start": 40, "width": 8, "type": "imm"},   # byte+5 = imageblock field BYTE-OFFSET>>1
            {"name": "b6",        "start": 48, "width": 8, "type": "raw"},
            {"name": "fmt",       "start": 56, "width": 8, "type": "enum",
             "enum": {0x0e: "half4/16b-slot", 0x22: "float/32b-slot"}},      # byte+7 slice data format
            {"name": "tail",      "start": 64, "width": 32, "type": "raw"},
        ],
        "semantics": "imageblock[slice].write(v)  ; EXPLICIT imageblock<T> WRITE from a fragment or TILE "
                     "(dispatchThreadsPerTile) shader. Memory-family store byte0 0xe7 with the tile variant "
                     "byte+1==0x16 (0x16 = 0x06|0x10, the 0x10 bit marking the FIRST store after a 0x87 "
                     "tile-access setup). Same op as frag_color_store, GENERALISED: byte+5 = SLICE ADDRESSING "
                     "= the field's BYTE-OFFSET WITHIN THE IMAGEBLOCK STRUCT, encoded (offset>>1). HW-proven: "
                     "a GB imageblock {half4 albedo@0, half4 normal@8, float depthv@16} stores with byte+5 = "
                     "0x00 / 0x04 / 0x08 (=0,8,16 >>1). byte+7 = slice data format (0x0e half4, 0x22 float). "
                     "This DIFFERS from simple-MRT frag_color_store where byte+5 = render-target index (rt<<1): "
                     "explicit imageblocks address by BYTE-OFFSET, MRT addresses by RT index. img.write(v) "
                     "writes the WHOLE struct (one 0xe7 per field). Bracketed by 0x87 frag_tile_setup + a "
                     "0x07 tile fence.",
        "provenance": "HW-VALIDATED end-to-end (EXP-O2D iotile: a tile kernel imageblock write landed in the "
                      "attachment; readback == the tile-written colour). byte+5 slice-offset & byte+7 format "
                      "from byte-diff of tk_write/tk_rmw/tk_write_slice (3-field GB imageblock); byte+1 "
                      "0x06/0x16 variant byte-diff.",
    },
    # ---- explicit imageblock<T>.read from a TILE / fragment shader (imageblock_load, 12B, EXP-O2D) ----
    # Load-side sibling of imageblock_store; generalises tile_read (byte+1==0x0e). Names the TILE
    # first-access variant byte+1==0x16 (the plain 0x06 read and the 0x0e programmable-blend read
    # tokenize by the length rule; 0x0e stays named tile_read).
    {
        "mnemonic": "imageblock_load",
        "length": 12,
        "match": [(0, 8, 0x67), (8, 8, 0x16), (16, 8, 0x54)],
        "fields": [
            {"name": "dst",       "start": 24, "width": 8, "type": "reg"},   # byte+3 destination register
            {"name": "b4",        "start": 32, "width": 8, "type": "raw"},
            {"name": "slice_off", "start": 40, "width": 8, "type": "imm"},   # byte+5 = imageblock field BYTE-OFFSET>>1
            {"name": "b6",        "start": 48, "width": 8, "type": "raw"},
            {"name": "fmt",       "start": 56, "width": 8, "type": "raw"},   # byte+7 slice data format
            {"name": "tail",      "start": 64, "width": 32, "type": "raw"},
        ],
        "semantics": "v = imageblock[slice].read()  ; EXPLICIT imageblock<T> READ from a fragment/tile shader "
                     "(the load-side sibling of imageblock_store; generalises tile_read's 0x67 byte+1==0x0e). "
                     "byte0 0x67 load with the tile first-access variant byte+1==0x16; byte+5 = slice "
                     "byte-offset>>1 (albedo 0x00 / normal 0x04 / depthv 0x08 for the GB imageblock). Used "
                     "for programmable-blend tile reads and explicit imageblock read-modify-write.",
        "provenance": "byte-diff of tk_rmw / tk_write_slice (our own tile kernels) vs the EXP-0029 tile_read. "
                      "Slice-offset addressing shared with imageblock_store (HW-validated there).",
    },
    {
        "mnemonic": "frag_tile_setup",
        "length": 6,
        "match": [(0, 8, 0x87), (16, 8, 0x54)],
        "fields": [
            {"name": "b1",  "start": 8,  "width": 8, "type": "raw"},   # 0x02
            {"name": "sel", "start": 24, "width": 8, "type": "raw"},   # byte+3 = tile/RT access selector
            {"name": "b4",  "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",  "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "fragment tile / render-target access setup, emitted around each colour store and each "
                     "tilebuffer read (and around raster-order-group ordered accesses). byte+3 = the per-RT / "
                     "per-tile selector (0x0c/0x30/0xc0 for RT0/RT1/RT2 in out_mrt; 0x08 before a tile read).",
        "provenance": "inferred (byte-diff, EXP-0029): brackets every frag_color_store / tile_read; its "
                     "byte+3 steps 0x0c->0x30->0xc0 across the 3 render targets of out_mrt. Length 6 "
                     "tokenises the output epilog to 0 leftover.",
    },
    {
        "mnemonic": "frag_color_pack",
        "length": 10,
        "match": [(0, 8, 0x97)],
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8, "type": "raw"},
            {"name": "b2",   "start": 16, "width": 8, "type": "raw"},   # 0x54 / 0x56
            {"name": "dst",  "start": 24, "width": 8, "type": "reg"},
            {"name": "b4",   "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",   "start": 40, "width": 8, "type": "raw"},
            {"name": "val",  "start": 48, "width": 8, "type": "imm"},   # byte+6 carries a packed colour component
            {"name": "tail", "start": 56, "width": 24, "type": "raw"},
        ],
        "semantics": "pack / move a colour value into an output GPR ahead of the tilebuffer store (converts "
                     "the shader's float/half output to the attachment format). byte+6 carries a colour "
                     "component value.",
        "provenance": "HW-VALIDATED byte (EXP-0008/EXP-0029): splicing byte+6 0x80->0x40 of a constant-colour "
                     "fragment's 0x97 op moved the read-back green 0.502->0.251 (128/255 -> 64/255) -> byte+6 "
                     "holds a colour component. Constant-colour and interpolated fragments both emit these "
                     "before the store; length 10 tokenises the epilog. Full field decode is a follow-up.",
    },
    {
        "mnemonic": "frag_depth_store",
        "length": 6,
        "match": [(0, 8, 0xd7), (8, 8, 0x14), (16, 8, 0x54)],
        "fields": [
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
            {"name": "b4",   "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",   "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "write the shader [[depth]] output to the tile depth buffer. Memory-family store (byte0 "
                     "0xd7) with the fragment depth variant byte+1==0x14, byte+2==0x54, 6 bytes — distinct "
                     "from the 16-byte texture write (also 0xd7). Bracketed by 0x87/0x07 tile-access ops "
                     "whose byte+3==0x01 selects the depth attachment (vs 0x0c for colour RT0).",
        "provenance": "inferred (byte-diff, EXP-0029): appears only in out_depth (a [[depth(any)]] output) "
                     "and not in the colour-only kernels; sits inside a 0x87(byte+3==0x01)/0x07 bracket "
                     "distinct from the colour store's 0x0c bracket. Not individually splice-validated "
                     "(agxrender has no depth attachment to read back).",
    },
    {
        "mnemonic": "pixel_order",
        "length": 6,
        "match": [(0, 8, 0x07), (16, 8, 0x54), (32, 8, 0x06)],   # 0x07 ... byte+4==0x06 (ROG fence flag)
        "fields": [
            {"name": "kind", "start": 8,  "width": 8, "type": "enum",   # byte+1 = acquire/release
             "enum": {"20": "acquire/wait", "4": "release/signal"}},
            {"name": "scope", "start": 24, "width": 8, "type": "raw"},  # byte+3 = ordering scope/mask
            {"name": "flags", "start": 32, "width": 8, "type": "raw"},  # byte+4 == 0x06 (device + ROG fence)
            {"name": "b5",   "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "fragment PIXEL-ORDERING op (raster_order_group / fragment-shader-interlock; the "
                     "wait_pix/signal_pix analogue). Same 0x07 memory-fence family as the compute "
                     "threadgroup_barrier (EXP-0025), but with byte+4==0x06 (the raster-order/device fence "
                     "flag) and byte+1 = 0x14 acquire (wait for prior overlapping fragments) / 0x04 release "
                     "(signal this fragment done). Brackets the ordered read-modify-write of a "
                     "[[raster_order_group]] resource so overlapping fragments serialise. There is NO "
                     "dedicated one-shot pixel wait/signal opcode — ordering is these fence ops.",
        "provenance": "inferred (byte-diff, EXP-0029): rog vs rog_none (identical read_write-texture RMW, "
                     "differing only in the [[raster_order_group(0)]] tag) differ by EXACTLY these ops — rog "
                     "adds `07 14 54 50 06 00` and `07 04 54 d0 06 00` (+ two 0x87 tile-access ops); rog_none "
                     "has neither. Same 0x07 family as the HW-validated threadgroup_barrier. Not "
                     "splice-validated for a stale read (needs overlapping-fragment geometry).",
    },
    # ========================================================================
    # FUNCTION CALL / RETURN / FRAME ABI (EXP-0035) + object/mesh marker (EXP-0030)
    # ========================================================================
    # CALL/RETURN live in the control-flow family (byte0 low-nibble 0xf), NOT a
    # dedicated opcode group. Each direct call is preceded by the 0x43 frame marker
    # and reuses the 0f 05 execution-mask machinery (a masked branch that saves the
    # return context). Args pass in r10,r11,r12..; return value in r10.
    # ---- CALL-SITE / FRAME-SETUP marker (byte0 0x43, 4 bytes) --------------
    # Re-scoped from EXP-0030's mesh-only "obj_mesh_ctrl": 0x43 is the GENERIC call/
    # frame-setup marker -- `43 00 00 01` precedes EVERY out-of-line CALL in plain
    # compute kernels (k_cf_call etc.) as well as the mesh helper-subroutine calls;
    # `43 00 06 xx` is the non-leaf-frame prologue variant. It is the only byte0 group
    # that appears in the object/mesh stages but was proven (EXP-0035) not mesh-unique.
    {
        "mnemonic": "frame_marker",
        "length": 4,
        "match": [(0, 8, 0x43)],
        "fields": [
            {"name": "b1", "start": 8,  "width": 8, "type": "raw"},
            {"name": "b2", "start": 16, "width": 8, "type": "raw"},
            {"name": "b3", "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "call-site / frame-setup marker (byte0 0x43, 4 bytes). `43 00 00 01` is emitted "
                     "immediately before every out-of-line CALL; `43 00 06 xx` is the non-leaf-frame "
                     "prologue. In object/mesh stages it marks the compiler-generated helper-subroutine "
                     "calls (write_childcount / write_uvb) -- NOT a mesh-emit op (set_vertex/index/"
                     "primitive lower to ordinary 0xe7/0xd7 stores, EXP-0030).",
        "provenance": "inferred (byte-diff, EXP-0030 + EXP-0035): present before every out-of-line call "
                     "in plain compute kernels (k_add/k_mul/k_many) and in object/mesh helper regions; "
                     "the `43 00 00 01` operand is invariant across mesh emit variants (a marker, not the "
                     "count store). Role not splice-validated.",
    },
    # ---- direct CALL (byte0 0f 05, 14 bytes) -------------------------------
    {
        "mnemonic": "call",
        "length": 14,
        "match": [(0, 8, 0x0f), (8, 8, 0x05), (16, 8, 0x54), (32, 8, 0x8f)],
        "fields": [
            {"name": "b3",     "start": 24, "width": 8,  "type": "raw"},
            {"name": "b5",     "start": 40, "width": 8,  "type": "raw"},
            {"name": "b6",     "start": 48, "width": 8,  "type": "raw"},   # 0x54/0x56 link/cache marker
            {"name": "offset", "start": 56, "width": 48, "type": "imm"},   # signed LE PC-relative; target = call_addr+4+off
            {"name": "tail",   "start": 104,"width": 8,  "type": "raw"},
        ],
        "semantics": "direct out-of-line CALL: `0f 05 54 1a 8f 00 56 <off40> 00` (14 B). offset = a "
                     "SIGNED little-endian PC-relative byte displacement; branch target = (call_addr + 4) "
                     "+ offset. Reuses the execution-mask push (0f 05) machinery -- a masked branch that "
                     "saves the return context -- so byte+4=0x8f and byte+6=0x56 are the CALL/link signature "
                     "(also the 14-vs-8-byte disambiguator vs a plain predication push). Bracketed by the "
                     "0x43 frame marker (before) and a 0f 06 reconverge (after). Args in r10,r11,r12..; "
                     "return value in r10; return via ret (0x8f).",
        "provenance": "HW-VALIDATED + byte-diff (EXP-0035): offset model exact across 4 varied call-site "
                     "distances (k_add off=-104, k_many -158, k_pressure -552, dynamic-lib -458); direct + "
                     "3-level nested (k_chain) dispatch return correct results from the archived machine code.",
    },
    # ---- function RETURN (byte0 0x8f, 4 bytes) -----------------------------
    {
        "mnemonic": "ret",
        "length": 4,
        "match": [(0, 8, 0x8f), (16, 8, 0x54)],
        "fields": [
            {"name": "linkmode", "start": 8,  "width": 8, "type": "enum",
             "enum": {0x02: "leaf", 0x12: "nonleaf_restore_link",
                      0x04: "cf_merge", 0x05: "cf_merge_push"}},
            {"name": "tail",     "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "function RETURN / CF merge: `8f <lm> 54 <t>` (4 B). byte0 0x8f = the control-flow "
                     "family (low nibble 0xf) with the high bit set; byte+2 0x54 = CF marker. byte+1 selects: "
                     "0x02 = LEAF function return (return address from the hardware link register), 0x12 = "
                     "NON-leaf return (restores its own spilled return address around inner calls); 0x04/0x05 "
                     "= a control-flow MERGE / reconvergence marker emitted at the join of an if/else or loop "
                     "body (NOT a function return -- appears in plain loop kernels with no calls). NO target "
                     "field -- the address is a hardware link register / CF (reconvergence) stack.",
        "provenance": "HW-VALIDATED + byte-diff (EXP-0035 + RT-ISA-FIX): `8f 02 54 00` is byte-identical at the "
                     "tail of every leaf helper (add/mul/sub, float/int/half) regardless of body; non-leaf mid() "
                     "-> `8f 12 54 00`. RT-ISA-FIX: `8f 04 54 ..` / `8f 05 54 ..` appear as the if/else and "
                     "loop-body merge marker in our for/while/nested CF kernels (which run correct on HW), "
                     "preceding the 0f 00 back-edge -- a reconvergence marker, not a return.",
    },
    # ---- INDIRECT CALL leader (byte0 0f 80, 8 bytes) -----------------------
    {
        "mnemonic": "call_indirect",
        "length": 6,
        "match": [(0, 8, 0x0f), (8, 8, 0x80)],
        "fields": [
            {"name": "b2",        "start": 16, "width": 8, "type": "raw"},
            {"name": "target_lo", "start": 24, "width": 8, "type": "raw"},
            {"name": "b4",        "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",        "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "INDIRECT CALL through a function pointer (visible_function_table / "
                     "intersection_function_table). Leader `0f 80 ..`: byte+1 0x80 selects the "
                     "call-to-address variant of the control-flow group (vs 0x00 jump, 0x05 direct call). "
                     "The target is a CODE VA loaded into a register from the function table (entry[i] = "
                     "8-byte code VA of function i's entry point); this op transfers control to it and "
                     "returns via the same ret (0x8f). Per-lane (dynamic) targets are marshalled through a "
                     "run of 0x4b move ops before the 0f 80.",
        "provenance": "HW-VALIDATED behaviour + byte-diff (EXP-0035): visible_function_table dispatch "
                     "(sel=0->vadd, 1->vmul) returns exact A+B / A*B. Exact operand fields are follow-ups "
                     "(need an indirect-call splice testbed).",
    },
    # ========================================================================
    # INTEGER / BITFIELD / HALF / PACK COMPLETENESS (EXP-0033, HW-validated)
    # ========================================================================
    # ---- native-half (fp16) float ALU (byte0 0x10, 6/8 bytes) --------------
    {
        "mnemonic": "half_alu",
        "length": 6,
        "match": [(0, 8, 0x10)],
        "fields": [
            {"name": "dst",     "start": 8,  "width": 8, "type": "reg"},
            {"name": "opsel",   "start": 16, "width": 3, "type": "opcode",
             "enum": {0b100: "hadd", 0b101: "hmul"}},
            {"name": "opflags", "start": 19, "width": 5, "type": "mod"},
            {"name": "srcB",    "start": 24, "width": 8, "type": "reg"},
            {"name": "tail",    "start": 32, "width": 16, "type": "raw"},
        ],
        "semantics": "d(half) = op(a, b)  ; NATIVE half-precision (fp16) float ALU. byte0 0x10 is the "
                     "16-bit-destination sibling of the 0x09 float ALU (and the 0x11 narrow-convert group); "
                     "same op-select (byte+2 low-3 bits: 0b100=hadd/0x1c, 0b101=hmul/0x1d) and same 6/8-byte "
                     "length bit (byte+2 bit1). A half2 (packed 2xfp16) op executes BOTH 16-bit lanes in ONE "
                     "0x10 op, then a 0x18 pack assembles the 32-bit result. (short2/2x-int16 does NOT pack: "
                     "two separate 32-bit 0x9f integer adds.)",
        "provenance": "HW-VALIDATED (EXP-0033): half_add / half2_add / half2_mul read back exact for both "
                     "packed lanes; op-select (0x1c/0x1d) mirrors the HW-validated 0x09 ALU and is the only "
                     "byte differing between half2_add and half2_mul. Operand bit-packing follows the 0x09 model.",
    },
    # ---- bit-count / bit-scan single op (byte0 0x27/0xa7, byte+2 0x56, 8 B) --
    {
        "mnemonic": "ibitcount",
        "length": 8,
        # EXP-M4-13 R2 (n7_fence): added (9,1,0) [byte+1 bit1==0] so it never collides with
        # cvt_i2f/cvt_f2i (byte+1 low-nib 7 => bit1=1); relaxed byte+2 0x56 -> {0x54,0x56}
        # (16,1,0)+(18,6,21) to name the cache-clear reverse_bits/find-MSB siblings (a7 04/05 54).
        "match": [(0, 7, 0x27), (9, 1, 0), (16, 1, 0), (18, 6, 21)],  # 0x27/0xa7; byte+2 in {0x54,0x56}
        "fields": [
            {"name": "fn_hi",    "start": 7,  "width": 1, "type": "opcode",
             "enum": {0: "popcount(b1=0x05)", 1: "reverse_bits(b1=0x04)|find_msb(b1=0x05)"}},
            {"name": "form",     "start": 8,  "width": 8, "type": "opcode",
             "enum": {5: "count/scan", 4: "reverse"}},
            {"name": "b2",       "start": 16, "width": 8, "type": "raw"},
            {"name": "operands", "start": 24, "width": 40, "type": "raw"},
        ],
        "semantics": "single-op bit-count / bit-scan (byte+2==0x56, 8 bytes). Operation = (byte0 bit7 fn_hi, "
                     "byte+1 form): (0x27,0x05)=popcount; (0xa7,0x04)=reverse_bits; (0xa7,0x05)=find-MSB / "
                     "bit-scan-reverse (index of the most-significant set bit; 0x80000000->31, 0xFF00->15). "
                     "clz/ctz are NOT single ops (find_msb + 31-x + clamp; ctz adds a 0x2b low-bit-isolate). "
                     "Shares byte0 low-7-bits with the 0x27/0xa7 convert family; distinguished by byte+1 form "
                     "and length 8.",
        "provenance": "HW-VALIDATED (EXP-0033): popcount/clz/ctz/reverse_bits read back exact over a 6-value "
                     "sweep; op-select splice-proven ((0x27,0x05)->popcount, (0xa7,0x04)->reverse_bits, "
                     "(0xa7,0x05)->find-MSB). popcount byte0 0x27,8B corroborates EXP-0007.",
    },
    # ---- rotate-by-immediate funnel shift (byte0 0x27, byte+1 0x01, 12 B) ---
    {
        "mnemonic": "irotate",
        "length": 12,
        # EXP-M4-13 R2 (n7_fence): relaxed byte+2 0x56 -> {0x54,0x56} to name the cache-clear rotate.
        "match": [(0, 8, 0x27), (8, 8, 0x01), (16, 1, 0), (18, 6, 21)],
        "fields": [
            {"name": "b1",       "start": 8,  "width": 8, "type": "raw"},
            {"name": "b2",       "start": 16, "width": 8, "type": "raw"},
            {"name": "operands", "start": 24, "width": 40, "type": "raw"},
            {"name": "tail",     "start": 64, "width": 32, "type": "raw"},
        ],
        "semantics": "d = rotate_left(a, k)  ; bit-rotate / funnel-shift by an IMMEDIATE amount. Single 12-byte "
                     "op in the 0x27 family (byte+1==0x01, byte+2==0x56): the 3-operand form fits a funnel shift "
                     "(hi,lo,shift); for a plain rotate hi==lo==a. Rotate by a REGISTER amount is a multi-instr "
                     "lowering (0x3b shift-prep + funnel + (32-n) subtract + OR).",
        "provenance": "HW-VALIDATED behaviour (EXP-0033): rotate(a,5) and rotate(a,n) read back exact. Single-op "
                     "immediate form vs multi-op dynamic form established by byte-diff. Operand bit-packing inferred.",
    },
    # ---- packed format CONVERT (pack): byte0 0x97, byte+2 0x56, 10 B --------
    {
        "mnemonic": "pack_convert",
        "length": 10,
        "match": [(0, 8, 0x97), (16, 8, 0x56)],   # byte+2==0x56 gates it off from the fragment frag_color_pack (0x54)
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8, "type": "raw"},
            {"name": "b2",   "start": 16, "width": 8, "type": "raw"},
            {"name": "src",  "start": 24, "width": 8, "type": "reg"},
            {"name": "body", "start": 32, "width": 48, "type": "raw"},
        ],
        "semantics": "packed format-conversion pack: pack_float_to_unorm2x16 / snorm / half -> a 32-bit packed "
                     "word. byte0 0x97 (COMPUTE, gated by byte+2==0x56). Same op family as the fragment "
                     "frag_color_pack (float colour -> attachment normalized format) -- 0x97 is the general "
                     "float->normalized-format pack/convert, in both compute and fragment; disambiguated by "
                     "byte+2 (compute pack 0x56 vs fragment 0x54).",
        "provenance": "HW-VALIDATED (EXP-0033): pack_float_to_unorm2x16 read back exact over 4 float2 inputs. "
                     "Single compute op (byte-diff); field bit-packing inferred.",
    },
    # ---- packed format CONVERT (unpack): byte0 0x17, byte+2 0x56, 10 B ------
    {
        "mnemonic": "unpack_convert",
        "length": 8,
        # byte0 0x17 collides with simd_ballot (also 0x17, 10B). RT-ISA-FIX: discriminate on
        # byte+1 LOW NIBBLE -- unpack byte+1==0x04 (low nib 4), ballot byte+1 in {0x07,0x17}
        # (low nib 7). Adding (8,4,0x04) makes the two descriptors MUTUALLY EXCLUSIVE (they can
        # never both match), which is necessary because unpack ALSO appears with byte+2==0x54
        # (the cache/last-use variant, EXP-0038) -- so byte+2 alone can NOT separate them from a
        # ballot's byte+2==0x54. EXP-0038: byte+2 bit1 (instr bit17) is a source cache/last-use
        # hint -- the (16,1,0)+(18,6,0x15) gate names both the 0x54 and 0x56 variants; the `b2`
        # field captures the full byte+2 so the codec round-trips byte-exact.
        "match": [(0, 8, 0x17), (8, 4, 0x04), (16, 1, 0), (18, 6, 0x15)],
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8, "type": "raw"},
            {"name": "b2",   "start": 16, "width": 8, "type": "raw"},
            {"name": "body", "start": 24, "width": 40, "type": "raw"},
        ],
        "semantics": "packed format UNPACK/convert: unpack_unorm2x16_to_float / snorm -> a float2. byte0 0x17, "
                     "8 bytes (EXP-M4-12 length CORRECTION: EXP-0033 recorded 10 by a 2-byte over-read; a fresh "
                     "isolated compile of unpack_unorm2x16_to_float = `17 04 56 00 00 00 1c ca` tokenizes cleanly "
                     "at 8B between device_load and device_store -- the HW readback validated the VALUE, not the "
                     "length). byte+1==0x04 (low nibble 4). Reads a 32-bit packed word and expands the two "
                     "normalized 16-bit lanes to floats. byte0 0x17 collides with simd_ballot (EXP-0018, also "
                     "0x17, 10B); RT-ISA-FIX separates them on byte+1 low nibble (unpack 4 vs ballot 7), since "
                     "both can carry byte+2 in {0x54,0x56}.",
        "provenance": "HW-VALIDATED (EXP-0033): unpack_unorm2x16_to_float read back exact "
                     "(0xFFFFFFFF->(1,1), 0x8000_4000->(0.25,0.5)). Single compute op; field bit-packing inferred.",
    },
    # ---- integer min/max CHAINED-operand variant (byte0 0x22): UNIFIED into `iminmax`
    # (n2_intalu, EXP-M4-13 R2). `22 01 1e 05 07 c0` (min3/clamp first op) is byte-for-byte
    # a low-nibble-2 imin at dst r2 -- now decoded by the dst-agnostic `iminmax` above.
    # ========================================================================
    # VERTEX VARYING STORE + TEXTURE COORDINATE MATH (EXP-0037)
    # ========================================================================
    # ---- VERTEX-stage varying / [[position]] store (byte0 0x57, 8 B) --------
    {
        "mnemonic": "vary_store",
        "length": 8,
        "match": [(0, 8, 0x57)],
        "fields": [
            {"name": "hint1",    "start": 8,  "width": 8, "type": "mod"},
            {"name": "hint2",    "start": 16, "width": 8, "type": "mod"},
            {"name": "src",      "start": 24, "width": 8, "type": "reg"},   # byte+3 = source GPR (HW-proven)
            {"name": "out_slot", "start": 32, "width": 8, "type": "imm"},   # byte+4 = destination output slot (index<<5)
            {"name": "b5",       "start": 40, "width": 8, "type": "raw"},   # byte+5 = 0x40 (const observed)
            {"name": "hint6",    "start": 48, "width": 8, "type": "mod"},   # byte+6 = splice-inert hint
            {"name": "b7",       "start": 56, "width": 8, "type": "raw"},   # byte+7 = 0x00
        ],
        "semantics": "uvs_buffer[out_slot] = reg[src]  ; VERTEX-stage store of a [[position]] component or a "
                     "user varying to the UVS / vertex-parameter buffer the fragment stage interpolates from "
                     "(the FS 0x2f iter op reads these coefficients, EXP-0029). Memory-family opcode (byte0 "
                     "0x57, low-nibble 7, sibling of 0x67 load / 0xe7 store / 0xd7 texture-write). byte+3 = "
                     "SOURCE GPR; byte+4 = DESTINATION OUTPUT SLOT (index<<5): [[position]].xyzw = slots 0-3 "
                     "(byte+4 0x00/0x20/0x40/0x60), user varyings at slots 4+ (0x80/0xa0/0xc0/0xe0). ONE op "
                     "per scalar component. Position-vs-varying is the SLOT RANGE, not a distinct opcode. "
                     "Mesh/object stages emit via the 0xe7 device store (EXP-0030); 0x57 is the traditional-VS path.",
        "provenance": "HW-VALIDATED (EXP-0037): splice-and-render on the A18 Pro via agxrender. byte+4=out-slot "
                     "proven by redirecting va.z's store slot 0xc0->0x80 (FS RED shows va.z's gradient) and by "
                     "moving position out of slots 0-3 (degenerate triangle); byte+3=source proven by zeroing "
                     "it (RED channel -> 0); byte+6 proven INERT. Length 8 tokenizes all VS stores byte-exact.",
    },
    # ---- texture COORDINATE / LOD / gather-offset setup ALU (0xNb, 10 B) -----
    {
        "mnemonic": "tex_coord_setup",
        "length": 10,
        "match": [(0, 4, 0x0b), (16, 8, 0x2f)],
        "fields": [
            {"name": "b0hi",  "start": 4,  "width": 4,  "type": "raw"},
            {"name": "b1",    "start": 8,  "width": 8,  "type": "raw"},
            {"name": "subop", "start": 16, "width": 8,  "type": "opcode",
             "enum": {0x27: "coord/LOD", 0x2f: "coord/interp"}},
            {"name": "b3",    "start": 24, "width": 8,  "type": "raw"},
            {"name": "mark",  "start": 32, "width": 8,  "type": "raw"},
            {"name": "body",  "start": 40, "width": 40, "type": "raw"},
        ],
        "semantics": "texture COORDINATE / LOD / gather-offset SETUP ALU (byte0 low-nibble 0x0b, 10 bytes, "
                     "byte+2 in {0x27,0x2f}, tail `.. 00 42 00 00 0X 00 00`). Computes the texel address / "
                     "normalized cube-face-or-array coordinate / explicit-LOD or bias / const gather offset "
                     "that the following tex_sample (0xb0/0x90) sampler op consumes as its coordinate/LOD "
                     "register operands. Emitted 1..N per sample. (The 0x27 byte+2 form gets the same length "
                     "but is not separately named here; the descriptor matches the 0x2f coord/interp form.)",
        "provenance": "inferred (byte-diff + clean tokenization, EXP-0037): 10-byte length makes k_tex_gather/"
                     "lod/compare/array_cube tokenize to the 0e stop with byte-exact re-serialization. The "
                     "coordinate-feeding role reuses EXP-0016's HW-validated op+1/op+3 coordinate operands; "
                     "fields not individually splice-decoded (a coord splice needs a non-uniform texture).",
    },
    # ---- coordinate / interpolation fused mul-add ALU LEADER (0x2e/0x3e, 10 B) -
    {
        "mnemonic": "coord_madf",
        "length": 10,
        "match": [(0, 8, 0x2e), (16, 8, 0x23)],
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8,  "type": "raw"},
            {"name": "op",   "start": 16, "width": 8,  "type": "raw"},
            {"name": "srcA", "start": 24, "width": 8,  "type": "reg"},
            {"name": "mark", "start": 32, "width": 8,  "type": "raw"},
            {"name": "body", "start": 40, "width": 40, "type": "raw"},
        ],
        "semantics": "coordinate / interpolation fused multiply-add ALU, byte0 LEADER form 0x2e (sibling 0x3e), "
                     "10 bytes: `2e/3e b1 23 a0 42 00 00 06 02 00`. Appears in the texture coordinate-generation "
                     "path (cube/array/3D normalized-coordinate math) and, as a byte+2 OP-SELECT (0x26/0x2e) of "
                     "the low-nibble-9 float group, in the vertex matrix-vector product -- a general fused mul/"
                     "mul-add, not texture-specific. This descriptor covers ONLY the byte0-LEADER 0x2e form "
                     "(gated on byte+2==0x23); the far more common op-select case is a 0x09 float op handled by "
                     "the float-ALU op-select length rule, NOT here.",
        "provenance": "inferred (byte-diff + clean tokenization, EXP-0037): 10-byte length aligns k_tex_array_cube "
                     "(`2e 87 23 a0 42 00 00 06 02 00`) cleanly between sample bundles; byte-exact re-serialization. "
                     "Fused-mul-add semantics inferred from co-occurrence in mvp*pos; not splice-decoded.",
    },
    # ========================================================================
    # u64 CARRY / NON-LEAF FRAME / HALF PACK (EXP-0038)
    # ========================================================================
    # ---- u64 CARRY-GENERATE (byte0 0x32, 6 B) --------------------------------
    {
        # EXP-M4-13 R2 (n2_intalu): WIDENED from byte0==0x32 (dst r3) to low-nibble-2 all dst
        # (byte+2==0x35 carry-generate marker). dst = byte0 high nibble.
        "mnemonic": "carry_gen",
        "length": 6,
        "match": [(0, 4, 2), (16, 8, 53)],
        "fields": [
            {"name": "dst",     "start": 4,  "width": 4, "type": "reg"},
            {"name": "subop",   "start": 8,  "width": 8, "type": "raw"},
            {"name": "srcA",    "start": 24, "width": 8, "type": "reg"},
            {"name": "cmpmode", "start": 32, "width": 8, "type": "enum",
             "enum": {0x22: "ordered"}},
            {"name": "b5",      "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "u64 CARRY-GENERATE. `32 01 35 03 22 81` (6 bytes). An unsigned-overflow compare in the "
                     "integer compare / min-max family (byte0 0x32 = 0x02|0x30; byte+2==0x35 marker; byte+4==0x22 "
                     "ordered-compare mode) detecting the carry-OUT of the immediately-preceding low-word 32-bit "
                     "add (sum_lo < operand, unsigned). Its per-lane predicate feeds a following 0x05 psel that "
                     "materializes the carry as {0,1}, added into the HIGH-word add. The compiler emits this "
                     "explicit chain for 64-bit ADD; 64-bit SUB uses the single native 0x1f op. Siblings byte0 "
                     "0x12 (a+const) and 0x22 (intermediate carry of a 3-operand add) share the byte+2==0x35 "
                     "signature. Operand register bit-packing inferred (byte-diff).",
        "provenance": "HW+SPLICE-VALIDATED (EXP-0038): u64 add carry correct across low->high carry "
                     "(0xFFFFFFFF+1 -> lo=0,hi=1), full carry-out, both-word carry, and a 3-operand two-chain add. "
                     "SPLICE-PROVEN load-bearing: neutralizing this op (byte0 0x32->0x00 or byte+4 0x22->0x26) "
                     "drops the carry (hi 1->0) while the low word stays correct. Length 6 tokenizes the chain "
                     "to 0 leftover (verify_fixes.py).",
    },
    # ---- NON-LEAF FUNCTION FRAME PROLOGUE (byte0 0x6f, 6 B) ------------------
    {
        "mnemonic": "frame_prologue",
        "length": 6,
        "match": [(0, 8, 0x6f)],
        "fields": [
            {"name": "subop",      "start": 8,  "width": 8, "type": "raw"},
            {"name": "marker",     "start": 16, "width": 8, "type": "raw"},
            {"name": "b3",         "start": 24, "width": 8, "type": "raw"},
            {"name": "b4",         "start": 32, "width": 8, "type": "raw"},
            {"name": "frame_size", "start": 40, "width": 8, "type": "imm"},
        ],
        "semantics": "NON-LEAF FUNCTION FRAME PROLOGUE. `6f 03 04 00 00 20` (6 bytes; the broader corpus also "
                     "shows `6f 03 54 00 00 10`). Emitted at the entry of a NON-leaf callee (one that itself "
                     "CALLs) to establish the per-thread SCRATCH frame in which it saves/restores its return/"
                     "link register around each inner call. Leaf callees have no prologue and return via "
                     "`8f 02 54 00`; a non-leaf callee has this prologue, brackets each nested CALL with the "
                     "8-byte 0x07 link save/restore, and returns via `8f 12 54 00`. byte+1==0x03 = frame sub-op; "
                     "byte+2 = 0x04/0x54 marker; byte+5 = candidate frame/scratch-size field (INFERRED).",
        "provenance": "HW-VALIDATED role (EXP-0038): the non-leaf chains k_chain and k_deep dispatch to correct "
                     "outputs; the 0x6f prologue is present verbatim in every non-leaf helper region extracted "
                     "from our own compiled kernels and ABSENT from every leaf helper. Field roles are byte-diff "
                     "INFERRED. Length 6 tokenizes the non-leaf frame to 0 leftover (verify_fixes.py).",
    },
    # ---- SPILL / FRAME-SETUP MARKER (byte0 0x60, 4 B, RT-1a-FIX item 4) -------
    # `60 00 00 00` appears instruction-aligned right after the ENTRY get_sr in high-
    # register-pressure / spilling kernels (big.bin: `8c a0 91 06 | 60 00 00 00| 9f 11
    # 54 ...`). Previously had NO length rule -> tokenization halted. RT-1a-FIX gives it
    # length 4 (the following iadd2 aligns) and characterizes it as far as HW splicing
    # allows: byte0/+1/+2 are runtime-INERT for the computation (splicing them is a
    # no-op on the big kernel's output), while byte+3 is this op's live last byte
    # (splicing +3 to 0xff faults). Best-understood role: a spill/scratch-frame or
    # occupancy setup marker emitted only in spilling kernels. Semantics beyond "4-byte,
    # byte+3-live" not fully decoded (a documented follow-up).
    {
        "mnemonic": "spill_frame_marker",
        "length": 4,
        "match": [(0, 8, 0x60)],
        "fields": [
            {"name": "b1", "start": 8,  "width": 8, "type": "raw"},   # inert in our splice test
            {"name": "b2", "start": 16, "width": 8, "type": "raw"},   # inert in our splice test
            {"name": "b3", "start": 24, "width": 8, "type": "raw"},   # LIVE: +3=0xff faults (HW)
        ],
        "semantics": "4-byte spill/frame-setup marker emitted right after the entry get_sr in "
                     "high-register-pressure / SPILLING kernels (byte0 0x60). Runtime-inert for "
                     "the computation in our splice test (byte0/+1/+2 sweeps are no-ops); byte+3 "
                     "is the only live byte (0xff faults). Best-understood role: scratch-frame / "
                     "occupancy setup for the spill path; exact semantics a follow-up. Adding it "
                     "unblocks tokenization (RT-1a-FIX: without a length rule the tokenizer halted).",
        "provenance": "HW-VALIDATED length + role bounds (RT-1a-FIX item 4): 0x60->4 aligns the "
                     "following 10-byte iadd2 in big.bin; big kernel output invariant to byte0/+1/"
                     "+2 splices, byte+3->0xff faults. raw/undecoded.log. Field semantics inferred.",
    },
    # ---- COMPACT frame/scope marker (byte0 0x60, 2 B, EXP-M4-01 round-3) -------
    # The `60 00 <nonzero>` sibling of the 4-byte spill_frame_marker: a 2-byte compact
    # frame/scope marker that precedes a threadgroup-atomic store (`60 00` + `e7 02 54..`
    # in k_atomics_tg / the isolated tg_store) or a divergent-CF block (`60 00` + a CF op
    # in k_atomics). Length disambiguates it from spill_frame_marker (byte+2==0x00 -> 4B).
    {
        "mnemonic": "frame_marker_compact",
        "length": 2,
        "match": [(0, 8, 0x60)],
        "fields": [
            {"name": "b1", "start": 8, "width": 8, "type": "raw"},
        ],
        "semantics": "2-byte compact frame/scope marker (byte0 0x60, byte+2 != 0x00). Precedes a "
                     "threadgroup-atomic store or a divergent control-flow block; the following "
                     "op is a full 14-byte threadgroup device_store or a CF op. Distinct from the "
                     "4-byte spill_frame_marker (byte+2==0x00).",
        "provenance": "length HW-anchored (EXP-M4-01 round-3, lenprobe): `60 00`->2 resyncs 8 clean "
                     "ops in k_atomics_tg@26 and k_atomics@362 (>=4 resyncs 0); byte+2==0x00 keeps "
                     "the spill marker at 4. Isolated via work/iso_tg.metal. Role inferred.",
    },
    # ---- CUBE/CUBE-ARRAY normalized-coord constant load (byte0 0xf0, 4 B) ------
    {
        "mnemonic": "cubearray_coord_const",
        "length": 4,
        "match": [(0, 8, 0xf0), (8, 8, 0xc0), (16, 8, 0x04)],
        "fields": [
            {"name": "b3", "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "4-byte constant / reciprocal-of-major-axis load feeding the cube/cube-array "
                     "face-select coordinate math (`f0 c0 04 00`, k_tex_array_cube@48). Precedes the "
                     "fspecial + coord_madf chain that normalizes the cube face coordinate.",
        "provenance": "length HW-anchored (EXP-M4-01 round-3, lenprobe): `f0 c0 04`->4 resyncs 5 clean "
                     "ops (fspecial + coord_madf) to @90. Tightly gated on the `f0 c0 04` signature so "
                     "no `f0 ..` operand tail is claimed. Role inferred (own-shader).",
    },
    # ---- THREADGROUP-memory address/base compute (byte0 0x1c, 6 B) -------------
    {
        "mnemonic": "tg_addr_compute",
        "length": 6,
        "match": [(0, 8, 0x1c), (8, 8, 0x02), (16, 8, 0x00)],
        "fields": [
            {"name": "b3", "start": 24, "width": 8, "type": "raw"},
            {"name": "b4", "start": 32, "width": 8, "type": "raw"},
            {"name": "b5", "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "6-byte threadgroup-buffer base/offset compute (`1c 02 00 00 00 00`, "
                     "k_threadgroup@46), bracketed between the low-nibble-3 threadgroup-id ops and "
                     "the threadgroup device_store. Distinct from the 4-byte get_sr datapath form "
                     "(byte+3 low-nibble 6).",
        "provenance": "length HW-anchored (EXP-M4-01 round-3, lenprobe): `1c 02 00 ..`->6 resyncs 8 "
                     "clean ops to @130; other lengths resync 0-1. Role inferred (own-shader).",
    },
    # ---- LINK-REGISTER SAVE / RESTORE around a nested call (byte0 0x07, 8 B) --
    {
        "mnemonic": "link_save_restore",
        "length": 8,
        "match": [(0, 8, 0x07), (8, 8, 0x00), (16, 8, 0x54), (32, 8, 0x81)],
        "fields": [
            {"name": "b1",         "start": 8,  "width": 8,  "type": "raw"},
            {"name": "marker",     "start": 16, "width": 8,  "type": "raw"},
            {"name": "b3",         "start": 24, "width": 8,  "type": "raw"},
            {"name": "scope",      "start": 32, "width": 8,  "type": "raw"},
            {"name": "dir_offset", "start": 40, "width": 24, "type": "raw"},
        ],
        "semantics": "LINK-REGISTER SAVE / RESTORE around a nested call in a non-leaf frame. save (before each "
                     "CALL) = `07 00 54 00 81 00 00 00`; restore (after each CALL) = `07 00 54 00 81 ff 1f 00` "
                     "(8 bytes). Same 0x07 fence/ordering family as the compute threadgroup_barrier (EXP-0025) "
                     "and fragment pixel_order (EXP-0029), but an 8-byte form gated by byte+1==0x00 (the barrier/"
                     "pixel-order forms are 6 bytes, byte+1 in {0x04,0x14}). byte+4==0x81 = scratch/stack scope; "
                     "byte+5..+7 discriminate SAVE (00 00 00) from RESTORE (ff 1f 00, a scratch offset). A "
                     "non-leaf callee spills its own link register because each inner CALL clobbers the hardware "
                     "link register (ret 0x8f encodes no return target).",
        "provenance": "HW-VALIDATED role (EXP-0038): present (exactly bracketing each nested CALL) in every "
                     "non-leaf helper region of k_chain/k_deep/k_bigframe, absent from leaf helpers; the frame "
                     "dispatches correctly. byte-field roles are byte-diff INFERRED. Length 8 tokenizes the "
                     "non-leaf frame to 0 leftover (verify_fixes.py). Without the byte+1 length gate the old "
                     "rule mis-lengths this as a 6-byte barrier and desyncs every non-leaf helper.",
    },
    # ---- HALF-LANE PACK (byte0 0x18, 4 B) ------------------------------------
    {
        "mnemonic": "half_pack",
        "length": 4,
        "match": [(0, 8, 0x18)],
        "fields": [
            {"name": "dstlo", "start": 8,  "width": 8, "type": "reg"},
            {"name": "src",   "start": 16, "width": 8, "type": "reg"},
            {"name": "b3",    "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "HALF-LANE PACK (assemble a half2 into a packed 32-bit register). `18 05 18 03` (4 bytes). "
                     "Combines the two fp16 lanes produced by the native-half 0x10 ALU (EXP-0033 half_alu) into "
                     "one 32-bit word for the device store (and the reverse assembly for half unpacks). Confirmed "
                     "4 bytes across half2 add (`18 05 18 03`), mul (`18 05 19 03`) and fma (`18 05 1b 07`). byte0 "
                     "HIGH nibble = destination register nibble -- the SAME op appears as 0x08/0x18/0x28/0x38 for "
                     "dst r0/r1/r2/r3 (this descriptor matches the 0x18 dst-r1 form). byte+2 = source register "
                     "(reg<<1)|hint. A longer 6-byte high-register form (byte+2==0x24, seen as 0x30/0x38 in the "
                     "broad corpus) is a documented follow-up. short2/short4 (int16) does NOT pack.",
        "provenance": "HW-VALIDATED (EXP-0038): the half2 round-trip k_h2roundtrip (float2 -> fp16 pack (0x18) -> "
                     "store -> load -> unpack -> float2) returns EXACT for 8 values. 4-byte length confirmed by "
                     "anchored segmentation of half2 add/mul/fma. Operand bit-packing INFERRED. The 0x30/0x38 "
                     "census siblings + the 6-byte high-register form are INFERRED (not splice-validated).",
    },
    # ==========================================================================
    # EXP-M4-13 full-corpus census closers (own-shader byte-diff; NOT HW-splice).
    # Merged by the integrate stage, each gated by roundtrip_test.py ALL PASS.
    # ==========================================================================
    # ---- low-nibble-0 catch-all: operand/pad WORD (NOT a standalone opcode) ----
    {
        "mnemonic": "pad_operand",
        "length": 2,
        "match": [(0, 4, 0)],
        "fields": [
            {"name": "hi",   "start": 4, "width": 4, "type": "raw"},
            {"name": "word", "start": 8, "width": 8, "type": "raw"},
        ],
        "semantics": "NOT A STANDALONE HARDWARE OPCODE. A 2-byte low-nibble-0 slot carrying a trailing "
                     "operand / immediate / SFU-coefficient WORD of the PRECEDING instruction, or inter-op "
                     "zero PADDING, or the interior bytes of one longer under-lengthed op. byte0 high nibble "
                     "and byte1 are a verbatim raw passthrough; the coefficient/immediate bits are "
                     "intentionally NOT semantically decoded (clean-room rule 5 -- the SFU range-reduction "
                     "coefficient SEQUENCE is not reconstructed). Named only so the tokenizer resolves these "
                     "vetted slots out of the unknown bucket; the more-specific frame_marker_compact (0x60) "
                     "and mov_imm (0x0c) win where they apply.",
        "provenance": "byte-diff + census EXP-M4-13 (own-MSL): NEGATIVE RESULT -- 0x00 is not an opcode. "
                     "Field positions are a raw 2-byte passthrough (no HW dispatch).",
    },
    # ---- 0x80 compute scoreboard/memory FENCE (device/wide scope), 4 bytes -----
    {
        "mnemonic": "dev_scoreboard_fence",
        "length": 4,
        "match": [(0, 8, 0x80), (8, 8, 0x02), (16, 8, 0x00)],
        "fields": [
            {"name": "b3", "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "Compute memory / scoreboard FENCE, device/wide-scope variant: `80 02 00 00` (4 bytes). "
                     "The 0x80 sibling of the 0x07/0x87 scoreboard_fence family (high bit = wider "
                     "memory/device scope). The compiler inserts it around divergent control flow and before "
                     "atomics/calls. byte+3 is a scope/flag operand (0x00 in observed forms). A bare `80 02` "
                     "with byte+2 != 0x00 is the 2-byte compact form (pad_operand).",
        "provenance": "byte-diff EXP-M4-13 (field positions; scope semantics from EXP-M4-01 census "
                     "anchoring). No HW dispatch -- structural / census-anchored, not splice-validated.",
    },
    # ---- low-nibble-3 compact MOVE / zero-extend / half-pack (all dst regs) -----
    {
        "mnemonic": "n3_mov",
        "length": 4,
        "match": [(0, 4, 3)],
        "fields": [
            {"name": "dst",      "start": 4,  "width": 4, "type": "reg"},
            {"name": "srcA_reg", "start": 8,  "width": 7, "type": "reg"},
            {"name": "srcA_uni", "start": 15, "width": 1, "type": "mod", "enum": {0: "gpr", 1: "uniform/hi"}},
            {"name": "sel",      "start": 16, "width": 8, "type": "raw"},
            {"name": "srcB",     "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "d = mov/zero-extend(srcA)  ; compact 4-byte register move / 16-bit zero-extend / "
                     "half-pack. dst = byte0 high nibble (r0..r15). byte1 = source operand (bit7 = "
                     "uniform-file / high-half flag). byte2 selects the sub-form (word vs low-half move); a "
                     "32-bit zero-extend of a 16-bit value emits the low-half move followed by the "
                     "`X3 00 00 01` high-half-zero companion. Generalises the HW-validated mov_zext16 "
                     "(0x13, dst r1) and frame_marker (0x43) to all dst regs; those keep their bytes by "
                     "match-bit specificity.",
        "provenance": "byte-diff EXP-M4-13 (own-MSL): dst PROVEN by parallel-extend / uint4 diffs (k_zext4 / "
                     "k_zext8w emit identical bodies differing only in the high nibble, stepping r0,r1,r2..); "
                     "srcA=byte1 tracks the source reg; sel/srcB sub-form INFERRED from OWN-MSL zero-extend / "
                     "move constructs -- NOT hardware dispatch-validated.",
    },
    # ---- low-nibble-3 10-byte address/coordinate/matrix-load prep (byte+2==0x27) ----
    {
        "mnemonic": "n3_addr_prep",
        "length": 10,
        "match": [(0, 4, 3), (16, 8, 39)],
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4,  "type": "reg"},
            {"name": "b1",   "start": 8,  "width": 8,  "type": "raw"},
            {"name": "b3",   "start": 24, "width": 8,  "type": "raw"},
            {"name": "tail", "start": 32, "width": 48, "type": "raw"},
        ],
        "semantics": "d = address/coordinate prep (matrix-load / texture-address / coordinate ALU). 10-byte "
                     "low-nibble-3 form, op-select byte+2 == 0x27. dst = byte0 high nibble. Distinct from the "
                     "low-nibble-2 rt_transform_test (also byte+2==0x27 but with byte+3==0x81, byte+4==0x22).",
        "provenance": "byte-diff EXP-M4-13 (length + op-select established across all dst high nibbles; dst = "
                     "high nibble by family analogy; operand body kept structural/raw -- NOT HW dispatch-"
                     "validated).",
    },
    # ---- low-nibble-3 10-byte fragment sample-id / sample-position read (byte0==0x03) ----
    {
        "mnemonic": "n3_sample_read",
        "length": 10,
        "match": [(0, 8, 3), (16, 8, 38)],
        "fields": [
            {"name": "b1",   "start": 8,  "width": 8,  "type": "raw"},
            {"name": "b3",   "start": 24, "width": 8,  "type": "raw"},
            {"name": "tail", "start": 32, "width": 48, "type": "raw"},
        ],
        "semantics": "fragment sample-id / sample-position read (byte0 0x03, op-select byte+2 == 0x26). "
                     "10-byte low-nibble-3 form.",
        "provenance": "byte-diff EXP-M4-13 (length / op-select from the EXP-0029 fragment sample-read length "
                     "rule; body structural/raw -- NOT HW dispatch-validated).",
    },
    # ==========================================================================
    # EXP-M4-13 n1_opselect: low-nibble-1 16-bit-destination CONVERT + native bfloat
    # ALU, generalised to ALL dst regs (byte0 high nibble = dst). Extends the
    # HW-VALIDATED byte0==0x11 cvt_f2h (EXP-0013) / bf_alu (EXP-O2D) descriptors to
    # r0..r15 and to the bf2-packed / fma forms they did not cover. Existing 0x11
    # descriptors are UNTOUCHED and win the byte0==0x11 tie by DB order (defined first).
    # byte-diff EXP-M4-13 (own-MSL); NOT HW-splice-validated. Merged by integrate stage.
    # ==========================================================================
    {
        "mnemonic": "cvt_f2h_dst",
        "length": 6,
        "match": [(0, 4, 1), (28, 4, 8)],
        "fields": [
            {"name": "dst",    "start": 4,  "width": 4, "type": "reg"},
            {"name": "srcfmt", "start": 8,  "width": 8, "type": "raw"},
            {"name": "opsel",  "start": 16, "width": 8, "type": "opcode",
             "enum": {0x1c: "f2h", 0x3c: "f2h(srcmode)"}},
            {"name": "src",    "start": 24, "width": 8, "type": "raw"},
            {"name": "dhalf",  "start": 32, "width": 8, "type": "raw"},
            {"name": "tail",   "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "d(half) = half(a)  ; fp32 -> fp16 narrowing convert, for ANY dst register (byte0 high "
                     "nibble). Generalises the byte0==0x11 (dst r1) cvt_f2h to r0..r15. byte+2 0x1c is the "
                     "base convert, 0x3c the same convert with the source-mode bit (bit5) set. byte+3 hi-nibble "
                     "8 (== 0x8x) is the single-source convert descriptor marker.",
        "provenance": "byte-diff EXP-M4-13 (field positions localised by dst-register sweep in "
                     "p_f2h_multi/p_packh2/p_h2conv; op-select from own-MSL half() construct). Length 6 anchored "
                     "between device_load/device_store brackets. Extends the HW-VALIDATED EXP-0013 cvt_f2h "
                     "(byte0==0x11) to all dst regs; not itself hardware-splice-validated.",
    },
    {
        "mnemonic": "cvt_bf16",
        "length": 8,
        "match": [(0, 4, 1), (24, 8, 0x81), (32, 8, 0x01)],
        "fields": [
            {"name": "dst",   "start": 4,  "width": 4, "type": "reg"},
            {"name": "srcw",  "start": 8,  "width": 8, "type": "opcode", "enum": {2: "src16", 3: "src32"}},
            {"name": "opsel", "start": 16, "width": 8, "type": "raw"},
            {"name": "src",   "start": 24, "width": 8, "type": "raw"},
            {"name": "fmt",   "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",    "start": 40, "width": 8, "type": "raw"},
            {"name": "dir",   "start": 48, "width": 8, "type": "opcode", "enum": {64: "to_bfloat", 128: "to_half"}},
            {"name": "b7",    "start": 56, "width": 8, "type": "raw"},
        ],
        "semantics": "bfloat convert (8-byte). byte+1 = source width (0x03 float32, 0x02 float16); byte+6 = "
                     "direction (0x40 = result bfloat: float->bfloat / half->bfloat; 0x80 = result half: "
                     "bfloat->half). byte+4 == 0x01 marks a bfloat operand. 8-byte sibling of the 6-byte "
                     "cvt_f2h_dst (byte+4 bit0 set = bfloat, so longer).",
        "provenance": "byte-diff EXP-M4-13 (p_f2bf/p_h2bf/p_bf2h single-op MSL). f2h-vs-f2bf length split "
                     "(byte+4 bit0) confirmed by direct byte-diff; direction byte+6 from h2bf(0x40) vs bf2h(0x80). "
                     "Own-MSL bfloat()/half() constructs; not hardware-splice-validated.",
    },
    {
        "mnemonic": "bf_add_dst",
        "length": 8,
        "match": [(0, 4, 1), (16, 8, 0x1c)],
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4,  "type": "reg"},
            {"name": "fmt",  "start": 8,  "width": 8,  "type": "opcode", "enum": {2: "bf", 4: "bf2"}},
            {"name": "srcA", "start": 24, "width": 8,  "type": "reg"},
            {"name": "srcB", "start": 32, "width": 8,  "type": "reg"},
            {"name": "tail", "start": 40, "width": 24, "type": "raw"},
        ],
        "semantics": "d(bfloat) = a + b  ; native bfloat add for ANY dst register. Generalises the byte0==0x11 "
                     "bf_alu (dst r1) to r0..r15. byte+1 = 0x02 scalar / 0x04 bfloat2-packed lane. Distinguished "
                     "from the 8-byte convert cvt_bf16 by byte+3 (a register here vs the 0x81 convert-source "
                     "descriptor there). The byte0==0x11 bf_alu (16 match bits) wins its own bytes.",
        "provenance": "byte-diff EXP-M4-13 (p_bfadd single-op MSL, dst-reg generalisation of the HW-VALIDATED "
                     "EXP-O2D bf_alu). Not itself hardware-splice-validated.",
    },
    {
        "mnemonic": "bf_mul_dst",
        "length": 8,
        "match": [(0, 4, 1), (16, 8, 0x1d)],
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4,  "type": "reg"},
            {"name": "fmt",  "start": 8,  "width": 8,  "type": "opcode", "enum": {2: "bf", 4: "bf2"}},
            {"name": "srcA", "start": 24, "width": 8,  "type": "reg"},
            {"name": "srcB", "start": 32, "width": 8,  "type": "reg"},
            {"name": "tail", "start": 40, "width": 24, "type": "raw"},
        ],
        "semantics": "d(bfloat) = a * b  ; native bfloat multiply for ANY dst register. op-select byte+2 == 0x1d "
                     "(vs 0x1c add) -- single-bit byte-diff (bf_add vs bf_mul).",
        "provenance": "byte-diff EXP-M4-13 (p_bfmul; opsel bit0 = add/mul confirmed by direct byte-diff "
                     "bf_add(0x1c) vs bf_mul(0x1d)). Not hardware-splice-validated.",
    },
    {
        "mnemonic": "bf_fma_dst",
        "length": 10,
        "match": [(0, 4, 1), (16, 8, 0x1e)],
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4,  "type": "reg"},
            {"name": "fmt",  "start": 8,  "width": 8,  "type": "opcode", "enum": {2: "bf", 4: "bf2"}},
            {"name": "srcA", "start": 24, "width": 8,  "type": "reg"},
            {"name": "srcB", "start": 32, "width": 8,  "type": "reg"},
            {"name": "srcC", "start": 40, "width": 8,  "type": "reg"},
            {"name": "tail", "start": 48, "width": 32, "type": "raw"},
        ],
        "semantics": "d(bfloat) = a*b + c  ; native bfloat fused multiply-add. op-select byte+2 == 0x1e (the fma "
                     "length bit, byte+2 bit1, is set) -> 10-byte 3-source form. Covers the byte0==0x11 case the "
                     "EXP-O2D length rule sized as 10 but had no descriptor for, plus all other dst regs.",
        "provenance": "byte-diff EXP-M4-13 (p_bffma single-op MSL: `11 02 1e 02 86 04 08 00 c0 81`, 10B, bracketed "
                     "by three device_loads). Not hardware-splice-validated.",
    },
    # ==========================================================================
    # EXP-M4-13 n4_tex: sr_read_wide -- the 8-byte member of the get_sr low-nibble-4
    # DATAPATH-READ family (byte0 low-3-bits 0b100; byte0 high nibble = dst r0..r15).
    # The wide/indexed builtin OR intersection_query PROPERTY read. Generalises to ALL
    # dst regs the length the committed DB only produced for dst-r0 (via the 0x04 frag
    # centroid rule). byte-diff/anchor EXP-M4-13; selector/sub SEMANTICS inferred, NOT
    # HW-splice. Strictly less specific than rt_intersect (byte+1==0xea) which keeps its
    # bytes. Merged by integrate stage.
    # ==========================================================================
    {
        "mnemonic": "sr_read_wide",
        "length": 8,
        "match": [(0, 4, 4), (15, 1, 1), (24, 8, 0), (16, 1, 0), (17, 1, 1)],
        "fields": [
            {"name": "dst", "start": 4,  "width": 4,  "type": "reg"},
            {"name": "sel", "start": 8,  "width": 7,  "type": "raw"},
            {"name": "sub", "start": 16, "width": 8,  "type": "raw"},
            {"name": "op",  "start": 32, "width": 32, "type": "raw"},
        ],
        "semantics": "d[dst] = wide_special_read(sel, sub)  ; 8-byte member of the get_sr low-nibble-4 datapath "
                     "family (byte0 low-3-bits 0b100). Reads a wide/indexed builtin OR, inside the "
                     "intersection_query BVH-traversal loop, a committed/candidate intersection or instance "
                     "PROPERTY (type / geometry-id / primitive-id / instance-id / distance / barycentrics / "
                     "object<->world transform component) into dst = byte0 high nibble. byte+1 (high bit always "
                     "set) is the property/register selector; byte+2 (low-nibble 2 or 6) a sub-selector; byte+3 "
                     "== 0x00; bytes+4..+7 a small operand/mask word. Emitted in bursts by every "
                     "intersection_query getter and by wide-builtin reads.",
        "provenance": "byte-diff EXP-M4-13 (OWN-SHADER): dst = byte0 high nibble byte-diff-PROVEN (corpus "
                     "dst-nibble histogram spans r0..r15); length 8 anchored by the immediately-following op "
                     "(44 82 26 00 -> 8 in 147/147; 64/84 81 a2 00 & 44 83 26 00 unanimous) and hand-verified at "
                     "a clean boundary directly after a 14-byte rt_as_load in own-compiled rtq_inst. selector / "
                     "sub-selector / operand-word SEMANTICS are structural/INFERRED, NOT hardware-dispatch-"
                     "validated. Generalises get_sr; strictly less specific than rt_intersect (byte+1==0xea).",
    },
    # ========================================================================
    # EXP-M4-13 ROUND-2 additions (nf_simd, n7_fence, n8_eight, n6_deriv, nb_ray)
    # ========================================================================
    # ---- RAY-QUERY traversal / getter op (nf_simd, 8 B) --------------------
    {
        "mnemonic": "rt_query_traverse",
        "length": 8,
        "match": [(0, 4, 15), (8, 8, 128), (16, 8, 134), (40, 8, 34), (48, 8, 130)],
        "fields": [
            {"name": "dst", "start": 4,  "width": 4, "type": "reg"},
            {"name": "opA", "start": 24, "width": 8, "type": "raw"},
            {"name": "sel", "start": 32, "width": 8, "type": "enum",
             "enum": {7: "sel0", 15: "sel1"}},
            {"name": "opB", "start": 56, "width": 8, "type": "raw"},
        ],
        "semantics": "8-byte special op emitted only inside intersection_query traversal / committed+candidate "
                     "result getters. byte0 HIGH nibble = dst register; byte+1=0x80, byte+2=0x86 (SFU/special-"
                     "function datapath marker); byte+5=0x22, byte+6=0x82 constant. byte+4 low-nibble 7 vs f is a "
                     "1-bit selector; byte+3/byte+7 are operand selectors. The trailing `[07|0f] 22 82 ZZ` "
                     "(bytes +4..+7) is the SECOND HALF of THIS instruction, not a separate 0x0f op. Internal "
                     "operand semantics left structural (clean-room rule 5: the getter algorithm is not lifted).",
        "provenance": "structural (inferred) + LENGTH byte-diff (EXP-M4-13 R2, own-MSL): length 8 established by "
                     "anchored resync across 76 occurrences in 5 own-compiled intersection_query shaders -- only "
                     "length 8 re-tokenizes the following ops (471 clean vs <=100 for 4/6/10/12). Constant bytes "
                     "+1/+2/+5/+6 and dst=byte0-hi read directly off the 76 samples. NOT HW-dispatch-validated.",
    },
    # ---- fldexp: runtime ldexp(float,int) = a * 2^n (nf_simd, 6 B) ---------
    {
        "mnemonic": "fldexp",
        "length": 6,
        "match": [(0, 4, 15), (8, 8, 21), (16, 8, 128)],
        "fields": [
            {"name": "dst",     "start": 4,  "width": 4, "type": "reg"},
            {"name": "operand", "start": 24, "width": 8, "type": "raw"},
            {"name": "b4",      "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",      "start": 40, "width": 8, "type": "raw"},
        ],
        "semantics": "fldexp: d = ldexp(a, n) = a * 2^n for a RUNTIME integer exponent n (float scale-by-power-"
                     "of-two). byte0 low-nibble 0xf, high-nibble = dst; byte+1=0x15 sub-op, byte+2=0x80 constant; "
                     "byte+3 = operand descriptor. Only emitted for the dynamic-exponent ldexp -- the constant-"
                     "exponent form folds to an fmul by a power-of-two literal.",
        "provenance": "byte-diff (EXP-M4-13 R2, own-MSL): length 6 proven by clean bracketing (iunary -> fldexp "
                     "-> device_store -> stop). Emission gated to dynamic exponent (ldexp(v,3)/ldexp(v,-2) "
                     "constant-fold, ldexp(v,n) emits it). byte+3 operand localized. NOT HW-dispatch-validated.",
    },
    # ---- integer shift-LEFT / bitfield-INSERT (0x27, 12 B) (n7_fence) -------
    {
        "mnemonic": "ibfins",
        "length": 12,
        "match": [(0, 8, 39), (16, 1, 0), (18, 6, 21)],   # 0x27; byte+2 bit0==0, bits18-23==0x15 ({0x54,0x56})
        "fields": [
            {"name": "form",     "start": 8,  "width": 8,  "type": "opcode",
             "enum": {16: "shl(reg)", 0: "insert/mask/narrow", 2: "addr/matrix-prep",
                      32: "shl/merge(var)", 17: "insert(var)"}},
            {"name": "cache",    "start": 17, "width": 1,  "type": "mod"},
            {"name": "operands", "start": 24, "width": 40, "type": "raw"},
            {"name": "opdesc",   "start": 64, "width": 8,  "type": "enum",
             "enum": {240: "reg-operand", 192: "imm-operand"}},
            {"name": "tail",     "start": 72, "width": 24, "type": "raw"},
        ],
        "semantics": "d = shift-left / bitfield-insert (integer). The byte0-bit7 LEFT/INSERT mirror of the "
                     "0xa7 ibfe (right/extract) family -- shl_reg (`27 10 54 ..`) is byte-identical to shr_log "
                     "(`a7 10 54 ..`) except byte0. 12-byte operand-descriptor form (byte+8 = 0xf0 register / "
                     "0xc0 immediate). byte+1 (form) selects the sub-op. byte+2 bit1 (cache) = source last-use hint.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): the shl_reg(0x27)/shr_log(0xa7) 12-byte ops are byte-"
                     "identical except byte0 -> byte0 bit7 = direction; 0x27 = the shift-LEFT / bitfield-INSERT "
                     "sibling of the HW-validated 0xa7 ibfe (EXP-0013). Field bit-packing / form map INFERRED "
                     "(no GPU dispatch); direction diff-proven.",
    },
    # ---- THREADGROUP atomic RMW (0x67, byte+1==0x03, 12 B) (n7_fence) -------
    {
        "mnemonic": "atomic_tg",
        "length": 12,
        "match": [(0, 8, 103), (8, 8, 3)],   # 0x67, byte+1 == 0x03
        "fields": [
            {"name": "b2",   "start": 16, "width": 8,  "type": "raw"},
            {"name": "ret",  "start": 24, "width": 8,  "type": "raw"},
            {"name": "b4",   "start": 32, "width": 8,  "type": "raw"},
            {"name": "src",  "start": 40, "width": 8,  "type": "raw"},
            {"name": "body", "start": 48, "width": 38, "type": "raw"},
            {"name": "op",   "start": 86, "width": 5,  "type": "opcode",
             "enum": {16: "add", 17: "and", 18: "cmpxchg", 21: "smin", 22: "or",
                      27: "sub", 28: "umax", 29: "umin", 30: "xchg", 31: "xor"}},
            {"name": "tail", "start": 91, "width": 5,  "type": "raw"},
        ],
        "semantics": "THREADGROUP (shared-memory) atomic read-modify-write. byte0 0x67 load/store family with the "
                     "threadgroup variant byte+1==0x03 (device atomics are byte+1 0x11/0x01, 14 B). Operation = the "
                     "5-bit op field at bits[86:91]. A single native op preceded by a simd_reduce lane-combine, NOT "
                     "a CAS retry loop. atomic_exchange emits the byte+2==0x56 cache-hint variant.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): op-select localised to bits[86:91] by diffing our own "
                     "tg_u_{add,sub,and,or,xor,max,min}/tg_s_min/tg_u_{cmpxchg,xchg} kernels. NOT HW-dispatch-"
                     "validated; the device sibling atomic_rmw IS HW-validated (EXP-0018) and shares the model.",
    },
    # ---- fragment tilebuffer/attachment READ, byte+1==0x06 (0x67, 12 B) -----
    {
        "mnemonic": "tile_read_mrt",
        "length": 12,
        "match": [(0, 8, 103), (8, 8, 6), (16, 8, 84)],   # 0x67, byte+1==0x06, byte+2==0x54
        "fields": [
            {"name": "dst",      "start": 24, "width": 8,  "type": "reg"},
            {"name": "b4",       "start": 32, "width": 8,  "type": "raw"},
            {"name": "rt_index", "start": 40, "width": 8,  "type": "imm"},
            {"name": "b6",       "start": 48, "width": 8,  "type": "raw"},
            {"name": "fmt",      "start": 56, "width": 8,  "type": "raw"},
            {"name": "tail",     "start": 64, "width": 32, "type": "raw"},
        ],
        "semantics": "fragment tilebuffer / attachment READ (byte+1==0x06). The plain-read sibling of tile_read "
                     "(0x0e programmable-blend) and imageblock_load (0x16 first-access). byte+3 = destination GPR, "
                     "byte+5 = render-target / imageblock-slice selector, byte+7 = slot format.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): the byte+1==0x06 read variant in our own blend_mrt_rw / "
                     "per_sample_blend / tile_imageblock kernels; field layout mirrors the HW-validated tile_read "
                     "(EXP-0029). No isolated GPU dispatch for this variant; the 0x0e/0x16 siblings ARE HW-validated.",
    },
    # ---- texture coordinate-projection / sample-address SETUP (0x17, 12 B) --
    {
        "mnemonic": "tex_addr_setup",
        "length": 12,
        "match": [(0, 8, 23), (16, 1, 0), (18, 6, 21)],   # 0x17; byte+2 in {0x54,0x56}
        "fields": [
            {"name": "form",     "start": 8,  "width": 8,  "type": "opcode",
             "enum": {1: "coord-proj", 5: "sample-addr/grad"}},
            {"name": "cache",    "start": 17, "width": 1,  "type": "mod"},
            {"name": "operands", "start": 24, "width": 40, "type": "raw"},
            {"name": "tail",     "start": 64, "width": 32, "type": "raw"},
        ],
        "semantics": "texture COORDINATE-PROJECTION / sample-address / gradient SETUP feeding a following "
                     "tex_sample. 12-byte form of the 0x17 group; byte+1 (form) 0x01 = coordinate projection "
                     "(cube/array/depth-compare), 0x05 = sample-address / gradient descriptor. byte+2 bit1 = "
                     "source cache/last-use hint (0x54/0x56).",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): present (12-byte, byte+1 in {0x01,0x05}) directly before "
                     "the tex_sample in our own cube/array/MSAA/depth-compare/grad texture kernels; length 12 from "
                     "the committed instr_length rule (EXP-M4-12). Field roles INFERRED; the tex_sample it feeds "
                     "IS HW-validated (EXP-0016/0037).",
    },
    # ---- native-half HIGH-HALF float ALU (low-nibble-8) (n8_eight) ---------
    {
        "mnemonic": "h_alu_hi",
        "length": 6,
        "match": [(0, 4, 8), (18, 3, 7)],
        "fields": [
            {"name": "dst",     "start": 4,  "width": 4, "type": "reg"},
            {"name": "srcA",    "start": 8,  "width": 8, "type": "reg"},
            {"name": "opsel",   "start": 16, "width": 3, "type": "opcode",
             "enum": {4: "hadd", 5: "hmul", 6: "hfma"}},
            {"name": "opflags", "start": 19, "width": 5, "type": "mod"},
            {"name": "srcB",    "start": 24, "width": 8, "type": "reg"},
            {"name": "ctrl",    "start": 32, "width": 8, "type": "mod"},
            {"name": "mods",    "start": 40, "width": 8, "type": "mod"},
        ],
        "semantics": "d.hi(half) = op(a, b) ; NATIVE fp16 float ALU writing the HIGH 16-bit half of the "
                     "destination register (the .y lane of a packed half2). byte0 low-nibble 0x8 is the high-half "
                     "sibling of the 0x10 low-half half_alu; byte0 high nibble = dst reg. op-select byte+2 low-3 "
                     "bits (0x1c hadd / 0x1d hmul / 0x1e hfma) is the SAME enum as the 0x09/0x10 float families.",
        "provenance": "byte-diff EXP-M4-13 R2 (OWN-SHADER): op-select by per-lane byte-diff -- half2(a.x*b.x, "
                     "a.y-b.y) -> low-half `10 04 1d`(fmul) + high-half `18 03 1c 05 00 08`(fadd). dst=byte0 hi "
                     "nibble (own half4 fma writes r0.hi/r1.hi). Length 6+2*(byte+4&3). Operand-field semantics "
                     "INFERRED, NOT hardware-dispatch-validated.",
    },
    {
        "mnemonic": "h_alu_hi_ext",
        "length": 8,
        "match": [(0, 4, 8), (18, 3, 7)],
        "fields": [
            {"name": "dst",     "start": 4,  "width": 4, "type": "reg"},
            {"name": "srcA",    "start": 8,  "width": 8, "type": "reg"},
            {"name": "opsel",   "start": 16, "width": 3, "type": "opcode",
             "enum": {4: "hadd", 5: "hmul", 6: "hfma"}},
            {"name": "opflags", "start": 19, "width": 5, "type": "mod"},
            {"name": "srcB",    "start": 24, "width": 8, "type": "reg"},
            {"name": "ext",     "start": 32, "width": 8, "type": "mod"},
            {"name": "srcC",    "start": 40, "width": 8, "type": "reg"},
            {"name": "tail",    "start": 48, "width": 16, "type": "raw"},
        ],
        "semantics": "d.hi(half) = a*b + c (fma) or op(a,b) with an extended saturate/abs source tail, writing the "
                     "HIGH 16-bit half. 8-byte member of the low-nibble-8 half ALU: byte+4 low-2 bits set selects "
                     "the extended encoding (fma addend srcC at byte+5), like the 0x09 fp32 polymorphism.",
        "provenance": "byte-diff EXP-M4-13 R2 (OWN-SHADER): own half2(a.x+b.x, fma(a.y,b.y,c.y)) -> high-half "
                     "`18 03 1e 05 81 06 00 20` (byte+4=0x81 -> 8B); srcC = byte+5. srcC/ext INFERRED.",
    },
    {
        "mnemonic": "h_coord_hi",
        "length": 6,
        "match": [(0, 4, 8), (16, 3, 6), (21, 1, 1)],
        "fields": [
            {"name": "dst",   "start": 4,  "width": 4, "type": "reg"},
            {"name": "srcA",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "opsel", "start": 16, "width": 8, "type": "opcode",
             "enum": {38: "hmul_coord", 46: "hfma_coord"}},
            {"name": "srcB",  "start": 24, "width": 8, "type": "reg"},
            {"name": "ctrl",  "start": 32, "width": 8, "type": "mod"},
            {"name": "mods",  "start": 40, "width": 8, "type": "mod"},
        ],
        "semantics": "d.hi(half) = fused-multiply[-add] coordinate op writing the HIGH 16-bit half; op-select 0x26 "
                     "(hmul_coord, 2-source) / 0x2e (hfma_coord, fused mul-add). Emitted by half-precision "
                     "geometry / interpolation. 6-byte 2-source form.",
        "provenance": "byte-diff EXP-M4-13 R2 (OWN-SHADER): corpus half_fma `38 88 26 82 00 86` / h2_many "
                     "`38 07 2e 82 00 84` (6B, byte+4==0x00). op-select 0x26/0x2e == byte+2. Field semantics INFERRED.",
    },
    {
        "mnemonic": "h_coord_hi_ext",
        "length": 8,
        "match": [(0, 4, 8), (16, 3, 6), (21, 1, 1)],
        "fields": [
            {"name": "dst",   "start": 4,  "width": 4, "type": "reg"},
            {"name": "srcA",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "opsel", "start": 16, "width": 8, "type": "opcode",
             "enum": {38: "hmul_coord", 46: "hfma_coord"}},
            {"name": "srcB",  "start": 24, "width": 8, "type": "reg"},
            {"name": "ext",   "start": 32, "width": 8, "type": "mod"},
            {"name": "srcC",  "start": 40, "width": 8, "type": "reg"},
            {"name": "tail",  "start": 48, "width": 16, "type": "raw"},
        ],
        "semantics": "d.hi(half) = fused-mul[-add] coordinate op (0x26/0x2e) writing the HIGH 16-bit half, 8-byte "
                     "extended form (byte+4 low2==1: 3rd source / ext tail at byte+5). See h_coord_hi.",
        "provenance": "byte-diff EXP-M4-13 R2 (OWN-SHADER): half vec2 high-half `48 86 26 82 01 84 00 c0` (8B, "
                     "byte+4==0x01). Length 6+2*(byte+4&3). Operand semantics INFERRED, NOT HW-dispatch-validated.",
    },
    {
        "mnemonic": "packed_half2_hi",
        "length": 6,
        "match": [(0, 4, 8), (16, 8, 36)],   # byte+2 == 0x24 packed-half2 ALU
        "fields": [
            {"name": "dst",   "start": 4,  "width": 4, "type": "reg"},
            {"name": "srcA",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "opsel", "start": 16, "width": 8, "type": "opcode",
             "enum": {36: "hpack2_alu"}},
            {"name": "srcB",  "start": 24, "width": 8, "type": "reg"},
            {"name": "mods",  "start": 32, "width": 16, "type": "mod"},
        ],
        "semantics": "d(half2) = op(a, b) on a PACKED 2xfp16 register (both lanes in ONE op), op-select 0x24. The "
                     "low-nibble-8 member (byte0 high nibble = dst) of the packed-half2 ALU already sized by the "
                     "packed-half2 length rule; this descriptor names it.",
        "provenance": "byte-diff EXP-M4-13 R2 (OWN-SHADER): corpus half `18 b0 24 82 80 c0` / `38 82 24 84 00 c8` "
                     "(EXP-M4-01 packed-half2). op-select 0x24 == byte+2. Field semantics INFERRED.",
    },
    # ---- ray-query traversal predicate / SFU marker (n6_deriv) -------------
    {
        "mnemonic": "rtq_pred",
        "length": 4,
        "match": [(0, 8, 6), (8, 8, 194), (16, 16, 0)],   # 06 c2 00 00 (byte-invariant)
        "fields": [],
        "semantics": "Ray-query traversal predicate/condition word. Byte-INVARIANT 4-byte token (06 c2 00 00) the "
                     "intersection_query compiler emits immediately after the candidate-status compare (icmp_pred, "
                     "byte0 0x0a) and before its consumer (if_push conditional branch, or a predicated iadd2). "
                     "Exclusively emitted inside intersection_query / ray-query traversal loops. Exact micro-op "
                     "NOT-YET-CHARACTERIZED; documented as a fixed encoding + length only.",
        "provenance": "byte-diff EXP-M4-13 R2 (OWN-MSL): invariant 06 c2 00 00 across 260 corpus occurrences in 44 "
                     "own-compiled ray-query shaders, ALWAYS directly after a 6-byte icmp_pred; reproduced in an "
                     "isolated OWN ray-query kernel. Length 4 anchored by clean resync of the following branch/iadd2 "
                     "to program end. Compile-only host: semantics inferred, NOT GPU-dispatch-validated.",
    },
    {
        "mnemonic": "sfu_marker",
        "length": 2,
        "match": [(0, 8, 6), (8, 8, 2)],   # 06 02 (byte-invariant)
        "fields": [],
        "semantics": "SFU / transcendental helper marker word. Byte-INVARIANT 2-byte token (06 02) the compiler "
                     "emits adjacent to special-function-unit and varying/mesh output ops -- after a 6-byte "
                     "low-nibble-2 min/max range-reduction op and before an fspecial (2f/af) SFU op or a 0x80 "
                     "output word. Fixed control token with no operand bits; exact micro-op NOT-YET-CHARACTERIZED. "
                     "Per clean-room rule 5 the adjacent range-reduction coefficient words are left raw.",
        "provenance": "byte-diff EXP-M4-13 R2 (OWN-MSL): invariant 06 02 across 59 corpus occurrences in 22 "
                     "own-compiled shaders; reproduced in an isolated OWN fast::sin kernel. Length 2 was already "
                     "in the committed rule (EXP-M4-12 S1); this descriptor only NAMES the family-only token. "
                     "Compile-only host: semantics inferred, NOT GPU-dispatch-validated.",
    },
    # ========================================================================
    # 0x?b COMPACT MOVES + 10-byte modifier/logic ALU (nb_ray, EXP-M4-13 R2)
    # dst = byte0 high nibble; src = byte+1; form = byte+2; opnd-type = byte+3.
    # Specific ops (ray_move_*, rtq_state_move, uniform_mov, funary, ilogic,
    # tex_coord_setup) win by match specificity; the reg_move_c*/b_alu10_* are
    # FAMILY-LEVEL fallbacks (match on byte+2 low-nibble). Field bit-packing is
    # byte-diff / bracket-inferred (own-MSL, NO GPU dispatch).
    # ========================================================================
    {
        "mnemonic": "ray_move_copy6", "length": 4,
        "match": [(0, 4, 11), (16, 8, 65)],   # byte+2 == 0x41
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "form", "start": 16, "width": 8, "type": "enum", "enum": {65: "copy_b6(b3=0x08)"}},
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "RAY register-marshalling MOVE, bit6 copy form (4B). dst=byte0 hi nibble, src=byte+1, "
                     "byte+2==0x41 (byte+3==0x08 = 32-bit register operand). The dominant move in the ray-struct "
                     "marshalling grid after rt_intersect.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): a clean 4-byte grid bracketed between rt_intersect and "
                     "rt_as_load across >=8 RT kernels; 100% of 0x41-form bytes are raytracing. Field bit-packing "
                     "inferred, not splice-validated.",
    },
    {
        "mnemonic": "ray_move_zero6", "length": 4,
        "match": [(0, 4, 11), (16, 8, 64)],   # byte+2 == 0x40
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "form", "start": 16, "width": 8, "type": "enum", "enum": {64: "zero_b6(b3=0x00)"}},
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "RAY register-marshalling MOVE, bit6 zero form (4B). byte+2==0x40 -> writes a zero/const "
                     "component in the bit6 source-class (the no-source counterpart of the 0x41 copy form).",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): bracketed in the RT marshalling grid immediately before "
                     "the 0x41 copy run. Not splice-validated.",
    },
    {
        "mnemonic": "ray_move_zinit", "length": 4,
        "match": [(0, 4, 11), (16, 8, 128)],   # byte+2 == 0x80
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "form", "start": 16, "width": 8, "type": "enum", "enum": {128: "zero_init"}},
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "RAY register-marshalling MOVE, zero-init form (4B). byte+2==0x80 -> zero/const component "
                     "(e.g. const origin float3(0,0,0)) in the bit7 source-class. Sibling of ray_move (0x81).",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): bracketed inside the marshalling grid of rt_assume_"
                     "identity / rt_query_*. Not splice-validated.",
    },
    {
        "mnemonic": "rtq_state_move", "length": 4,
        "match": [(0, 4, 11), (16, 8, 9), (24, 8, 0)],   # byte+2==0x09, byte+3==0x00
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "form", "start": 16, "width": 8, "type": "enum", "enum": {9: "query_state_read"}},
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "Intersection-query compact register move (4B). byte+2==0x09, byte+3==0x00, byte+1 = source "
                     "selector. Emitted once per intersection_query kernel, reading a fixed query-state / result "
                     "register into a GPR.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): identical `8b 14 09 00` / `6b 14 09 00` in "
                     "rt_query_abort/bbox_commit/candidate_getters/curve/transforms. Not splice-validated.",
    },
    {
        "mnemonic": "funary_imm", "length": 10,
        "match": [(0, 4, 11), (16, 8, 15)],   # byte+2 == 0x0f
        "fields": [
            {"name": "dst",   "start": 4,  "width": 4, "type": "reg"},
            {"name": "b1",    "start": 8,  "width": 8, "type": "raw"},
            {"name": "form",  "start": 16, "width": 8, "type": "enum", "enum": {15: "modifier_imm"}},
            {"name": "srcA",  "start": 24, "width": 8, "type": "reg"},
            {"name": "lut_a", "start": 32, "width": 8, "type": "mod"},
            {"name": "mod",   "start": 40, "width": 8, "type": "mod"},
            {"name": "ext",   "start": 48, "width": 32, "type": "raw"},
        ],
        "semantics": "Float source-modifier / integer-logic move with an immediate/operand tail (10B). byte+2==0x0f "
                     "selects the modifier-with-immediate form (vs 0x0e plain fmov, 0x1e/0x1f LUT2 logic). Op-select "
                     "bits in the tail are INFERRED (shared with the HW-validated funary/ilogic).",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): bracketed to exactly 10B between a 14B device_load and a "
                     "14B device_store in bitops__and_imm_u32 / float_arith__negabs. Not splice-validated.",
    },
    {
        "mnemonic": "b_alu10_lo7", "length": 10,
        "match": [(0, 4, 11), (16, 4, 7)],   # byte+2 low-nibble 7
        "fields": [
            {"name": "dst",     "start": 4,  "width": 4, "type": "reg"},
            {"name": "b1",      "start": 8,  "width": 8, "type": "raw"},
            {"name": "form_hi", "start": 20, "width": 4, "type": "raw"},
            {"name": "srcA",    "start": 24, "width": 8, "type": "reg"},
            {"name": "b4",      "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",      "start": 40, "width": 8, "type": "raw"},
            {"name": "ext",     "start": 48, "width": 32, "type": "raw"},
        ],
        "semantics": "0x?b 10-byte modifier/convert/setup ALU, byte+2 low-nibble 0x7 (source-modifier / shift-mask "
                     "/ convert; siblings 0x17 `& mask`, 0x27 tex/operand setup, 0x07/0x47/0x67). Family-level "
                     "decode; exact op-select within the tail NOT characterised.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): bracketed 10-byte (`1b 52 07 7a 10 02 ..`) between "
                     "rt_ray_mem and imad. Family-level; not splice-validated.",
    },
    {
        "mnemonic": "b_alu10_loe", "length": 10,
        "match": [(0, 4, 11), (16, 4, 14)],   # byte+2 low-nibble e
        "fields": [
            {"name": "dst",     "start": 4,  "width": 4, "type": "reg"},
            {"name": "b1",      "start": 8,  "width": 8, "type": "raw"},
            {"name": "form_hi", "start": 20, "width": 4, "type": "raw"},
            {"name": "srcA",    "start": 24, "width": 8, "type": "reg"},
            {"name": "b4",      "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",      "start": 40, "width": 8, "type": "raw"},
            {"name": "ext",     "start": 48, "width": 32, "type": "raw"},
        ],
        "semantics": "0x?b 10-byte modifier ALU, byte+2 low-nibble 0xe (funary/ilogic/shift-prep base with a "
                     "non-zero dst register). Named forms funary(0x0e)/ilogic(0x1e) win by specificity; this "
                     "fallback covers 0x2e/0x4e/0x8e (shift-amount prep). Family-level.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): bracketed 10-byte in dec2_n8 / rt_query kernels. "
                     "Family-level; not splice-validated.",
    },
    {
        "mnemonic": "b_alu10_lof", "length": 10,
        "match": [(0, 4, 11), (16, 4, 15)],   # byte+2 low-nibble f
        "fields": [
            {"name": "dst",     "start": 4,  "width": 4, "type": "reg"},
            {"name": "b1",      "start": 8,  "width": 8, "type": "raw"},
            {"name": "form_hi", "start": 20, "width": 4, "type": "raw"},
            {"name": "srcA",    "start": 24, "width": 8, "type": "reg"},
            {"name": "b4",      "start": 32, "width": 8, "type": "raw"},
            {"name": "b5",      "start": 40, "width": 8, "type": "raw"},
            {"name": "ext",     "start": 48, "width": 32, "type": "raw"},
        ],
        "semantics": "0x?b 10-byte modifier ALU, byte+2 low-nibble 0xf (funary_imm 0x0f / ilogic 0x1f base with a "
                     "non-zero dst). Named forms win by specificity; this fallback covers 0x3f/0x4f/0x8f. Family-level.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): bracketed 10-byte (`cb 11 3f 0d 00 02 ..`) in RT / dec2_n8 "
                     "kernels. Family-level; not splice-validated.",
    },
    {
        "mnemonic": "reg_move_c0", "length": 4,
        "match": [(0, 4, 11), (16, 4, 0)],   # byte+2 low-nibble 0
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "form", "start": 16, "width": 8, "type": "raw"},
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "Compact 4-byte register move, low-nibble-0 source-class. byte+2==0x00 = const-zero / scope-"
                     "prep; 0x20/0x60/0xa0/0xc0/0xe0 = source-class variants. Family-level decode.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): `Xb 00 00 00` prep ops anchored before clean device_store "
                     "/ pop_reconverge runs and the 0x20-range call-arg marshalling grids. Family-level.",
    },
    {
        "mnemonic": "reg_move_c1", "length": 4,
        "match": [(0, 4, 11), (16, 4, 1)],   # byte+2 low-nibble 1
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "form", "start": 16, "width": 8, "type": "raw"},
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "Compact 4-byte register move, low-nibble-1 source-class. Observed forms 0x61/0xa1 (RT-query "
                     "marshalling) and 0x01/byte+3==0x00 (uniform-move sibling). Family-level.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): bracketed 4-byte in the compact-move grids of dec2_n8 / "
                     "rt_query_* kernels. Family-level; not splice-validated.",
    },
    {
        "mnemonic": "reg_move_c9", "length": 4,
        "match": [(0, 4, 11), (16, 4, 9)],   # byte+2 low-nibble 9
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "form", "start": 16, "width": 8, "type": "raw"},
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "Compact 4-byte register move, low-nibble-9 source-class. Observed forms 0x29/0x49/0x69/0x89/"
                     "0xa9 in the RT-query / dec2_n8 marshalling grids. Family-level.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): bracketed 4-byte between tg-prep / device ops in the "
                     "intersection-query kernels. Family-level; not splice-validated.",
    },
    {
        "mnemonic": "reg_move_cb", "length": 4,
        "match": [(0, 4, 11), (16, 4, 11)],   # byte+2 low-nibble b
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "form", "start": 16, "width": 8, "type": "raw"},
            {"name": "b3",   "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "Compact 4-byte pack / bitcast / convert move, byte+2 low-nibble 0xb (0x0b/0x1b/0x2b/0x3b). "
                     "Appears in conversions_pack / bitcast_vec / pack_norm and the 64-bit int helpers. Family-level.",
        "provenance": "byte-diff EXP-M4-13 R2 (own-MSL): `0b 01 1b 05` bracketed 4-byte before a device_store; "
                     "`4b 05 3b 09 2b 07 3b 0b` a regular 4-byte grid. Closes the 0xe7 device-store bleed. "
                     "Not splice-validated.",
    },
    {
        "mnemonic": "tg_atomic_prep", "length": 8,
        "match": [(0, 4, 11), (16, 8, 6)],   # byte+2 == 0x06
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "src",  "start": 8,  "width": 8, "type": "reg"},
            {"name": "form", "start": 16, "width": 8, "type": "enum", "enum": {6: "tg_atomic_rmw_prep"}},
            {"name": "body", "start": 24, "width": 40, "type": "raw"},
        ],
        "semantics": "Threadgroup-atomic RMW descriptor prep (8B). byte0 low-nibble 0xb, byte+2==0x06; sets up the "
                     "atomic-value / descriptor for a threadgroup atomic RMW. dst=byte0 hi nibble (scope/reg).",
        "provenance": "byte-diff EXP-M4-13 R2 / round-1 EXP-M4-01: `0b 00 06 00 00 00 00 00` anchored before a "
                     "clean device_store in atomics__tg_u_add. Length 8 (b1==0,b2==0x06). Not splice-validated.",
    },
    # ============================ EXP-M4-13 ROUND 4 ============================
    {
        "mnemonic": "b_alu14_c83", "length": 14,
        "match": [(0, 4, 15), (7, 1, 0), (16, 8, 131)],   # low-nibble 0xf, bit7==0, byte+2==0x83
        "fields": [
            {"name": "hi",   "start": 4,  "width": 3,  "type": "raw"},
            {"name": "rega", "start": 8,  "width": 8,  "type": "reg"},
            {"name": "regb", "start": 24, "width": 8,  "type": "reg"},
            {"name": "c4",   "start": 32, "width": 8,  "type": "raw"},
            {"name": "c6",   "start": 48, "width": 8,  "type": "raw"},
            {"name": "zz",   "start": 56, "width": 8,  "type": "raw"},
            {"name": "tail", "start": 80, "width": 32, "type": "raw"},
        ],
        "semantics": "Low-nibble-0xf 14-byte integer/simd ALU (byte+2 == 0x83 form). Distinct from the "
                     "iadd2/imad 0x9f/0x1f family (byte+2 == 0x54): byte0 high nibble is a variant selector "
                     "(0x3f/0x5f/0x7f observed), byte+1 = (reg<<1)|1 and byte+3 = byte+1-1 form a register "
                     "operand pair, tail carries a fixed `03 00 80 <ZZ> 00 00 03 00` frame plus a trailing "
                     "register word. Appears back-to-back in the RT-traversal coordinate/index getters and the "
                     "log2(N) shuffle+multiply integer simd-prefix/product reduction trees. Exact arithmetic "
                     "NOT resolved -- structural/length only.",
        "provenance": "byte-diff EXP-M4-13 R4 (own-MSL): back-to-back spacing = exactly 14 across the corpus "
                     "(e.g. `3f 07 83 06 03 00 80 04 00 00 03 00 12 01` then the next 0x3f/0x7f op); "
                     "byte+1/byte+3 register-pair relation (b3=b1-1) holds across all high-nibble variants. "
                     "Not splice-validated (M4 compile-only, no GPU dispatch).",
    },
    {
        "mnemonic": "if_push_pred", "length": 4,
        "match": [(0, 8, 15), (8, 4, 5)],   # byte0==0x0f, byte+1 low nibble == 5
        "fields": [
            {"name": "pred",  "start": 12, "width": 4, "type": "raw"},
            {"name": "scope", "start": 16, "width": 8, "type": "raw"},
            {"name": "level", "start": 24, "width": 8, "type": "raw"},
        ],
        "semantics": "Execution-mask PUSH / if-enter, PREDICATE variant (4B). byte0 0x0f, byte+1 low nibble == "
                     "5 with a non-zero HIGH nibble selecting a predicate/condition register (the plain 0x05 "
                     "base is if_push). byte+2 = CF marker (0x54 outer / 0x56 last-use), byte+3 = nesting "
                     "level. Pairs with the following 0f 01 jump_cond as the if/loop test-and-branch in the "
                     "RT-query and integer simd-prefix kernels; paired with a later 0f 06 pop_reconverge.",
        "provenance": "byte-diff EXP-M4-13 R4 (own-MSL): ~100 corpus leaders (`0f 15 54 21`, `0f 45 54 21`, "
                     "`0f 25 56 02`, ...) each bracketed to 4 bytes by the immediately-following `0f 01 54 "
                     "<off>` jump_cond. Generalizes the RT-ISA-FIX HW-validated b1==0x05 -> 4 push. Not "
                     "splice-validated.",
    },
    {
        "mnemonic": "b_alu14_prep2", "length": 2,
        "match": [(0, 4, 2), (8, 1, 1)],   # byte0 low nibble 2, byte+1 bit0 == 1
        "fields": [
            {"name": "dst", "start": 4, "width": 4, "type": "reg"},
            {"name": "sel", "start": 8, "width": 8, "type": "raw"},
        ],
        "semantics": "2-byte compact PREP word preceding a b_alu14 (byte+2==0x83 int/simd ALU). byte0 low "
                     "nibble 2, high nibble = dst reg; byte+1 = (dst<<1)|1 (the compact register field, size "
                     "bit set). A per-operand register declaration / high-half select emitted right before "
                     "the 14-byte ALU op in the RT getter and integer simd-reduction trees. Distinct from the "
                     "6-byte low-nibble-2 min/max (whose byte+2 is a min/max op-select, not a b_alu14 leader).",
        "provenance": "byte-diff EXP-M4-13 R4 (own-MSL): `72 0f | 3f 13 83 ..`, `52 0b | 3f 13 83 ..`, "
                     "`82 11 | 3f 45 83 ..`, `92 13 | 3f 17 83 ..` -- prev op decodes cleanly (falu2) so the "
                     "2-byte word is a genuine leader, and byte0=(dst<<4)|2 / byte+1=(dst<<1)|1 holds across "
                     "dst regs. Not splice-validated.",
    },
    {
        "mnemonic": "int_alu_ehi", "length": 10,
        "match": [(0, 8, 239), (16, 8, 84), (72, 8, 64)],   # byte0==0xef, byte+2==0x54, byte+9==0x40
        "fields": [
            {"name": "b1flags", "start": 8,  "width": 8, "type": "raw"},
            {"name": "dst",     "start": 24, "width": 8, "type": "reg"},
            {"name": "opmode",  "start": 32, "width": 8, "type": "mod"},
            {"name": "b5",      "start": 40, "width": 8, "type": "raw"},
            {"name": "srcdesc", "start": 48, "width": 8, "type": "raw"},
            {"name": "srcB",    "start": 56, "width": 8, "type": "raw"},
            {"name": "srcC",    "start": 64, "width": 8, "type": "raw"},
        ],
        "semantics": "Integer address/index arithmetic (dst=byte+3, op-select=byte+4); the high-register-"
                     "pressure integer ALU form emitted by std140 uniform->storage matrix-copy shaders. "
                     "Distinct opcode from iadd2/imad. byte0==0xef, byte+2==0x54 and byte+9==0x40 are "
                     "invariant structural markers. Exact per-opmode operation is inferred from field "
                     "position (compile-only host -- no HW dispatch on this M4).",
        "provenance": "EXP-M4-13 R4 (lenhi): byte-diff over 276 own-compiled instances extracted from our own "
                     "shdump compilation of open-source Dawn/Tint std140 matNxN_to_storage MSL; length 10 "
                     "anchored by bracketing (every instance re-aligns at a 10-byte stride between known ops). "
                     "Own hand-written MSL emits 0x9f for equivalent integer address math on this toolchain -> "
                     "0xef could NOT be own-MSL-reproduced (first-class negative reproduction result). Not "
                     "splice-validated.",
    },
    {
        "mnemonic": "vtx_out_pos", "length": 8,
        "match": [(0, 4, 11), (8, 8, 0), (16, 8, 38), (24, 8, 0), (32, 8, 64), (40, 8, 0), (48, 8, 0)],
        "fields": [
            {"name": "dst",  "start": 4,  "width": 4, "type": "reg"},
            {"name": "slot", "start": 56, "width": 8, "type": "imm"},
        ],
        "semantics": "Vertex-stage output-position / attribute op. byte0 high nibble = dst reg; byte+7 = "
                     "varying/output slot (0x04/0x08/0x0c/0x10/0x14). Bytes +4..+7 (`40 00 00 SS`) were the "
                     "dominant spurious 0x40 root desync before this op was lengthed 8.",
        "provenance": "byte-diff EXP-M4-13 R4 (own-MSL): `Xb 00 26 00 40 00 00 SS`; corpus co-occurrence 55/55 "
                     "with a preceding low-nibble-b leader; `40 00 00 SS` independent in only 2/57 sites.",
    },
    {
        "mnemonic": "vary_slot", "length": 4,
        "match": [(0, 8, 0), (16, 8, 64)],   # byte0==0x00, byte+2==0x40
        "fields": [
            {"name": "sel",  "start": 8,  "width": 8, "type": "raw"},
            {"name": "slot", "start": 24, "width": 8, "type": "imm"},
        ],
        "semantics": "Vertex varying-output SLOT descriptor emitted immediately before each `57 SS 54 ..` "
                     "vary_store; byte+3 = the varying slot (monotone, tracks the store slot). byte+1 (sel) in "
                     "{0x04,0x0a,0x0c} = the output-class form.",
        "provenance": "byte-diff EXP-M4-13 R4 (own-MSL vtest_posonly `00 0c 40 60` -> vary_store, reproduced "
                     "byte-exact); genuine leader -- appears after 8+ distinct preceding ops corpus-wide.",
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
                "0x60": "4  [SPILL/FRAME-SETUP MARKER (spill_frame_marker): `60 00 00 00` right after the entry "
                        "get_sr in high-register-pressure / SPILLING kernels. Runtime-inert for the computation "
                        "(byte0/+1/+2 splices no-op), byte+3 live (0xff faults). Previously halted tokenization "
                        "(no length rule). RT-1a-FIX HW: length 4; exact role a follow-up]",
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
