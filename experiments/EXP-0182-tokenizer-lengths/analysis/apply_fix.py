#!/usr/bin/env python3
"""EXP-0182 -- build a candidate tools/agx-isa tree with named length-rule patches.

Each patch is an exact-string replacement against the frozen `isadb.py`
(sha256 9cda47a1d4b3857c9f20423ab5d63c38050d37220da06bc5d2dc12a77d6ef1a8), so a
reviewer can apply them one at a time and re-measure. Patches:

  n1     LOW-NIBBLE-1 group (single-source convert + native bfloat ALU) -- key the
         length on the bits that IDENTIFY the instruction (byte+3 source-descriptor
         class, byte+2 op-select) instead of on the operand bytes byte+1/byte+2's low
         nibble, and generalise it over byte0's high nibble (the DESTINATION register).
         Closes bf_add_dst, bf_fma_dst, cvt_f2h_dst; lengths cvt_bf16.
  r9     Restore the documented intent of the R9 trailing-word closure ("fires only
         where baseline instr_length was None"): never claim a 2-byte pad where the
         low-nibble-1 rule yields a length at which a REAL NAMED descriptor matches.
         Required for n1 to be reachable at byte0 0x21 (`_R9_SIGS[(0x21,0x00)] = 2`).
  n2     LOW-NIBBLE-2 op-select 0x1c -> 6 bytes (hminmax). Derived mechanically:
         analysis/opsel_length_map.py shows 0x1c is an op-select for which db.json's
         own low-nibble-2 descriptors imply exactly one length, and which
         instr_length gets wrong at 14 of the 16 destination registers.
  n2b    Same, for iminmax's remaining unambiguous op-selects 0x06 / 0x0e / 0x16.
  n2c    Same, for isel10_c's unambiguous op-selects 0x05 / 0x15 -> 10 bytes.
  n0     DEF-0180-7: generalise the native-half (fp16) ALU family from the full-byte
         gate `if b0 == 0x10` to byte0's LOW NIBBLE, mirroring the already-committed
         low-nibble-8 high-half rule. Length FORMULA deliberately unchanged (that is
         EXP-0180's measured result to merge, not this experiment's).

Usage:
  python3 analysis/apply_fix.py work/cand_x n1 r9 n2
  python3 analysis/apply_fix.py --inplace ../../tools/agx-isa n1 r9 n2
CLEAN-ROOM: edits our own tool only.
"""
import hashlib, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPDIR = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXPDIR, "..", ".."))
SRC = os.path.join(REPO, "tools", "agx-isa")

# ---------------------------------------------------------------------------- n1 helper
N1_HELPER = '''
def _n1_len(buf, off):
    """EXP-0182: length of the LOW-NIBBLE-1 group (single-source CONVERT + NATIVE
    BFLOAT ALU) at buf[off], or None if these bytes are not that group.

    DEF-0181-2 / DEF-0171-2 (EXP-0181, EXP-0171; re-derived from committed raw in
    EXP-0182). byte0's HIGH NIBBLE is the DESTINATION register throughout this group --
    db.json says so itself: cvt_f2h_dst, cvt_bf16, bf_add_dst and bf_fma_dst all pin
    `[0, 4, 1]` and none of them pins `[0, 8, v]`. The two rules this replaces keyed the
    length on bytes that select OPERANDS, and both gates excluded encodings OUR OWN
    HARDWARE EXECUTED CORRECTLY:

      * the convert gate demanded `byte+2 & 0x0f == 0x0c`, so the HW anchors
        `01 01 14 81 05 02 40 00` (cvt_bf16) and `c1 01 14 81 04 02` (cvt_f2h_dst) --
        both `outcome: ok, match: true` on G17P in EXP-0162 raw, cvt_bf16 also on M4 in
        EXP-0144 -- had NO length at all (`unknown instruction length`);
      * the bfloat gate demanded `byte+1 in {0x02, 0x04}`, but G17P's own compiler emits
        byte+1 == 0x00: `21 00 1c 00 11 00 c0 81` (bf_add_dst, 8B) and
        `21 00 1e 00 86 04 10 00 c0 81` (bf_fma_dst, 10B), both EXP-0156 `ok` against a
        host bf16 oracle. Our tokenizer split the 8-byte add into `operand_word` +
        `mov_imm` + a `cvt_f2h` that ran off the end of the instruction, and every token
        after it in that carrier was garbage (EXP-0156 raw/g17p-20260830-bf03
        00_inputs.json `carrier_tokens.bfadd`).

    Key on the bits that IDENTIFY the instruction instead:
      byte+3 hi-nibble 8  -> single-source CONVERT (db.json cvt_f2h_dst `match [28,4,8]`);
                             length from byte+4 bit0: ->half 6, ->bfloat 8 (EXP-M4-13 n1).
      else byte+2 op-select 0x1c add / 0x1d mul -> 8 ; 0x1e fma -> 10
                             (db.json bf_add_dst `match [16,8,28]`, bf_fma_dst `[16,8,30]`).
    The byte0 == 0x11 sub-rules that predate this are kept verbatim BELOW the two general
    ones, so every previously-correct byte0 == 0x11 length is reproduced.
    """
    b0 = buf[off]
    if (b0 & 0x0f) != 0x01:
        return None
    b1 = buf[off + 1] if off + 1 < len(buf) else -1
    b2 = buf[off + 2] if off + 2 < len(buf) else 0
    b3 = buf[off + 3] if off + 3 < len(buf) else 0
    b4 = buf[off + 4] if off + 4 < len(buf) else 0
    # fp16 PACK/CONVERT compact op (EXP-M4-01 round-3, k_cvt_half@32 `31 01 3c 81 00 c2`).
    # Kept FIRST and unchanged: it fired before the general rules in the old ordering.
    if b1 == 0x01 and b2 == 0x3c:
        return 6
    # single-source CONVERT: byte+3 is the convert-SOURCE descriptor (hi nibble 8).
    if (b3 & 0xf0) == 0x80:
        return 8 if (b4 & 0x01) else 6
    # NATIVE BFLOAT ALU, every dst register and every byte+1 source class.
    if b2 in (0x1c, 0x1d):
        return 8
    if b2 == 0x1e:
        return 10
    # ---- byte0 == 0x11 legacy sub-rules, preserved verbatim ----
    if b0 == 0x11 and b1 == 0x03:
        return 8 if (b4 & 0x01) else 6
    if b1 in (0x02, 0x04):
        return 10 if (b2 & 0x02) else 8
    if b0 == 0x11:
        return 8 if (b2 & 0x02) else 6
    return None


def _n1_real_instr(buf, off):
    """EXP-0182 (DEF-0171-2): guard for the R9 trailing-word closure.

    That closure documents itself as firing "only where baseline instr_length was None
    at a real boundary". It does not: `_R9_SIGS[(0x21, 0x00)] = 2` shadows
    `21 00 1c 00 11 00 c0 81`, an 8-byte native bfloat add that G17P executed correctly
    against a host bf16 oracle. Restore the documented intent for this group only --
    never claim a 2-byte pad where the low-nibble-1 rule yields a length at which a REAL
    NAMED descriptor matches."""
    L = _n1_len(buf, off)
    return L is not None and _r9_named_at(buf, off, L)

'''

OLD_R9_ANCHOR = "def instr_length(buf, off=0):"

OLD_R9_GUARD = """    if _r9 is not None and _r9_succ_safe(buf, off + _r9):
        return _r9"""
NEW_R9_GUARD = """    if _r9 is not None and _r9_succ_safe(buf, off + _r9) \\
            and not _n1_real_instr(buf, off):
        return _r9                     # EXP-0182: `and not _n1_real_instr(...)` restores this
                                       # table's own documented intent (fire only where the
                                       # baseline length was None). Without it `_R9_SIGS[(0x21,
                                       # 0x00)] = 2` shadows the HW-VALIDATED 8-byte bfloat add
                                       # `21 00 1c 00 11 00 c0 81` (EXP-0156, G17P, ok vs a host
                                       # bf16 oracle) and desyncs the rest of the carrier."""

OLD_0X11 = """    if b0 == 0x11:
        b1v = buf[off + 1] if off + 1 < len(buf) else -1
        if b1v == 0x03:
            # EXP-M4-13 (n1_opselect): the 6-vs-8 convert sub-split. float->HALF (cvt_f2h,
            # byte+4 bit0 clear) = 6B; float->BFLOAT (cvt_f2bf, byte+4 bit0 set) = 8B. The
            # old flat `->6` mis-lengthed float->bfloat. (cvt_f2h `11 03 1c 81 00 c2` stays 6.)
            return 8 if (off + 4 < len(buf) and (buf[off + 4] & 0x01)) else 6
        if b1v in (0x02, 0x04):
            return 10 if (off + 2 < len(buf) and (buf[off + 2] & 0x02)) else 8   # bfloat add/mul (8) | fma (10)
        return 8 if (off + 2 < len(buf) and (buf[off + 2] & 0x02)) else 6         # legacy fallback"""
NEW_0X11 = """    # EXP-0182 GENERAL FIX (DEF-0181-2 / DEF-0171-2): the byte0 == 0x11 block, the
    # `X1 01 3c` pack-convert rule and the `(b0 & 0x0f) == 0x01 and b0 != 0x11` block that
    # used to live here and below are now ONE rule keyed on the identifying bits, applied
    # at every destination register. See `_n1_len` for the full derivation and the HW
    # anchors each old gate excluded.
    _n1 = _n1_len(buf, off)
    if _n1 is not None:
        return _n1"""

OLD_PACK_AND_GEN = """    # ---- fp16 PACK/CONVERT compact op (low-nibble-1, byte+1==0x01, byte+2==0x3c), 6B ----
    # EXP-M4-01 round-3: k_cvt_half@32 `31 01 3c 81 00 c2` (dst r3). The half<->int/float
    # pack-convert helper the mixed-precision `half(int)`/`int(half)` path emits; distinct from
    # the 0x11 bfloat/cvt group (byte+1 in {0x02,0x03,0x04}). High nibble = dst reg. Anchored 6B
    # (the following `27 07 54 ..` cvt_f2i tokenizes cleanly; a walk of the whole kernel closes).
    if (b0 & 0x0f) == 0x01 and (buf[off + 1] if off + 1 < len(buf) else -1) == 0x01 \\
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
"""
NEW_PACK_AND_GEN = """    # (the fp16 pack-convert rule and the general low-nibble-1 convert/bfloat rules that
    #  used to sit here are folded into `_n1_len`, called above -- EXP-0182.)
"""

OLD_N2_6 = "            if b2 in (0x1e, 0x2e, 0x3e, 0x26, 0x36, 0x35, 0x3d, 0x23, 0x2b, 0x03):"
NEW_N2_6 = """            if b2 in (0x1e, 0x2e, 0x3e, 0x26, 0x36, 0x35, 0x3d, 0x23, 0x2b, 0x03,
                      0x1c):
                # EXP-0182 (DEF-0181-2): op-select 0x1c added. `hminmax` (db.json
                # `match [[0,4,2],[16,8,28]]`, length 6) is the fp16 sibling of iminmax and
                # its HW anchor `22 00 1c 00 10 c0` -- EXP-0156, G17P, `ok` against a host
                # fp16 max oracle -- decoded at only TWO of the sixteen destination
                # registers, and NOT at the one that proved it: the op-select was missing
                # from this list, so the length fell through to the FULL-BYTE per-destination
                # fallbacks (`if b0 == 0x02 / 0x12 / 0x22 / 0x32`) below, which give 10 for
                # dst r2 and no length at all for r4..r15. analysis/opsel_length_map.py
                # derives this mechanically from db.json."""

OLD_N2_6B = """                      0x1c):"""
NEW_N2_6B = """                      0x1c, 0x06, 0x0e, 0x16):"""

OLD_N2_C = """            if b2 in (0x1d, 0x2d):"""
NEW_N2_C = """            if b2 in (0x05, 0x15):
                return 10              # EXP-0182: isel10_c's unambiguous op-selects
                                       # (db.json `match [[0,4,2],[16,3,5]]`, length 10).
            if b2 in (0x1d, 0x2d):"""

OLD_N0 = """    if b0 == 0x10:
        if buf[off + 2] in (0x18, 0x38, 0x19, 0x21, 0x31, 0x30, 0x39):"""
NEW_N0 = """    _n0_half = (b0 == 0x10)
    if not _n0_half and (b0 & 0x0f) == 0x00 and b0 != 0x00 \\
            and off + 4 < len(buf) and buf[off + 2] in (0x1c, 0x1d, 0x1e, 0x26, 0x2e) \\
            and (buf[off + 4] & 0x7c) == 0:
        # EXP-0182 (DEF-0180-7, HW-VALIDATED G17P by EXP-0180): byte0's HIGH NIBBLE is the
        # DESTINATION register of this family -- EXP-0180's DSTNIB arm ran byte0 = n<<4 for
        # every n = 0..15 on two carriers in two gated runs and the result landed in r[n]'s
        # low 16 bits, 16 of 16. The old FULL-BYTE gate `if b0 == 0x10` lengthed only dst r1,
        # so fifteen of sixteen destinations did not tokenize and every corpus census over
        # this family under-counts by construction. This function's own docstring records the
        # identical bug being fixed for the 0x09 float family ("using the full byte
        # mis-tokenizes any falu2 whose dst register is >= 1"); it was never applied here.
        # Gated exactly like the already-committed low-nibble-8 high-half sibling below:
        # byte+2 must be a real half op-select and (byte+4 & 0x7c) == 0.
        # The length FORMULA is deliberately left unchanged -- EXP-0180 measured it on
        # hardware as a function of (byte+2 & 7, byte+4 & 3) and found this code wrong in 18
        # of 32 cells; merging that measured rule is EXP-0180's result, not this experiment's.
        _n0_half = True
    if _n0_half:
        if buf[off + 2] in (0x18, 0x38, 0x19, 0x21, 0x31, 0x30, 0x39):"""

# n0w: the same DEF-0180-7 generalisation, but gated on the OP-SELECT (byte+2 & 7) that
# EXP-0180 measured on hardware (4 hadd / 5 hmul / 6 hfma) rather than on the compiler's
# canonical opflags bytes {0x1c,0x1d,0x1e,0x26,0x2e}. EXP-0180's own DSTNIB encodings carry
# byte+2 = 0x04 / 0x06 (opflags 0), so the narrow gate does not reach them.
NEW_N0W = NEW_N0.replace(
    "and off + 4 < len(buf) and buf[off + 2] in (0x1c, 0x1d, 0x1e, 0x26, 0x2e) \\\n"
    "            and (buf[off + 4] & 0x7c) == 0:",
    "and off + 4 < len(buf) and (buf[off + 2] & 0x07) in (0x04, 0x05, 0x06) \\\n"
    "            and (buf[off + 4] & 0x7c) == 0:")
assert NEW_N0W != NEW_N0

PATCHES = {
    "n1": [(OLD_0X11, NEW_0X11), (OLD_PACK_AND_GEN, NEW_PACK_AND_GEN)],
    "r9": [(OLD_R9_GUARD, NEW_R9_GUARD)],
    "n2": [(OLD_N2_6, NEW_N2_6)],
    "n2b": [(OLD_N2_6B, NEW_N2_6B)],
    "n2c": [(OLD_N2_C, NEW_N2_C)],
    "n0": [(OLD_N0, NEW_N0)],
    "n0w": [(OLD_N0, NEW_N0W)],
}
NEEDS_HELPER = {"n1", "r9"}
ORDER = ["n1", "r9", "n2", "n2b", "n2c", "n0", "n0w"]


def patch(text, names):
    if NEEDS_HELPER & set(names):
        assert text.count(OLD_R9_ANCHOR) == 1
        text = text.replace(OLD_R9_ANCHOR, N1_HELPER.lstrip("\n") + "\n" + OLD_R9_ANCHOR)
    for n in ORDER:
        if n not in names:
            continue
        for old, new in PATCHES[n]:
            if text.count(old) != 1:
                raise SystemExit("patch %s: anchor found %d times, expected 1:\n%s"
                                 % (n, text.count(old), old[:200]))
            text = text.replace(old, new)
    return text


def main():
    args = [a for a in sys.argv[1:]]
    inplace = "--inplace" in args
    if inplace:
        args.remove("--inplace")
    dest, names = args[0], args[1:]
    for n in names:
        if n not in PATCHES:
            raise SystemExit("unknown patch %r; known: %s" % (n, ", ".join(ORDER)))
    src_text = open(os.path.join(SRC, "isadb.py")).read()
    if not inplace:
        dest = os.path.abspath(dest)
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(SRC, dest, ignore=shutil.ignore_patterns("__pycache__"))
        src_text = open(os.path.join(SRC, "isadb.py")).read()
    out = patch(src_text, set(names))
    target = os.path.join(dest, "isadb.py") if not inplace else os.path.join(dest, "isadb.py")
    open(target, "w").write(out)
    print("%s  patches=%s  sha256=%s" % (os.path.relpath(target, REPO), ",".join(names),
                                         hashlib.sha256(out.encode()).hexdigest()[:16]))


main()
