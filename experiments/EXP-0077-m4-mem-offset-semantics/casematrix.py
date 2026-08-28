#!/usr/bin/env python3
"""EXP-0077 frozen perturbation matrix + observation codec (single source of truth).

run.py builds every case from CASES below; verify.py re-derives and checks the
contract against it; analysis.py decodes observations with the same codec. The
matrix is frozen BEFORE any GPU dispatch of a spliced variant.

Per case:
  name      unique case name
  item      questionnaire item (MEM-01..MEM-05) or family tag (CTRL / VAL-*)
  kernel    "ld" (kernels/ld_bank.metal, splice the unique base_slot==2 load)
            or "st" (kernels/st_bank.metal, splice the unique base_slot==1 store)
  idx       [i0, i1, i2, i3] bound to idxbuf (buffer 3); the effective GPR index
            is j = i0 + i1 (i1 is 0 in every family except VAL-IDXREG)
  fields    instruction-field overrides spliced into the probe instruction via
            tools/agx-isa assemble(decode(...)+overrides) -- one FAMILY of change
            per case; {} = unspliced control
  pred      frozen predictions, each a named hypothesis -> predicted effective
            BYTE offset into the probe buffer (or the strings "oob" /
            "explore"), plus "scale" documenting the element-size hypothesis.

Hypotheses (frozen):
  H-ELEM   effective byte offset B = ((j + off) mod 2^32) * scale  -- offset in
           ELEMENT units, added to the index before the element-size scale
  H-BYTE   effective byte offset B = j*scale + off                -- offset in
           BYTE units, added after the scale
  H-U      idx_off interpreted unsigned (0..2047)
  H-S      idx_off interpreted as 11-bit two's-complement (-1024..+1023)
  H-W32    the (index+offset)*scale computation wraps modulo 2^32 exactly
  H-SC     elem_size codes {0:16,1:1,2:2,3:4,4:8} bytes (bits[1:4] of byte+12)
"""
import struct

A_WORDS = 4096            # probe read buffer (ld kernel buffer 2), 16384 bytes
TGT_WORDS = 2048          # probe store target (st kernel buffer 1), 8192 bytes
STORE_CONST = 0x5A17C0DE  # st kernel stores this constant (4 bytes)
A_TAG_HI = 0x3CA50000     # a[w] = A_TAG_HI | w

# element-size code table (bits[1:4] of byte+12) under hypothesis H-SC
ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}
ELEM_BYTE = {code: (0x40 | (code << 1)) for code in ELEM_SCALE}   # 0x40,42,44,46,48


def a_word(w):
    return (A_TAG_HI | w) & 0xFFFFFFFF


def fill_a():
    return b"".join(struct.pack("<I", a_word(w)) for w in range(A_WORDS))


def fill_idx(idx):
    return b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in idx)


def sext11(f):
    return f - 2048 if f & 0x400 else f


def decode_load_value(v):
    """Decode a 32-bit observation read from the a[] pattern buffer.

    Returns (byte_offset, word, residue, ambiguous) or None when the value does
    not match any in-bounds window of the pattern (out-of-allocation read,
    zero, or garbage). Byte layout of word w: [w&0xFF, (w>>8)&0xFF, 0xA5, 0x3C].
    The (0xA5, 0x3C) tag pair pins the residue; residues 0/2/3 decode the word
    unambiguously; residue 1 sees w's high byte and (w+1)'s low byte, giving at
    most two candidates (ambiguous=True when both are in range).
    """
    if not isinstance(v, int) or v < 0 or v > 0xFFFFFFFF:
        return None
    p = [(v >> (8 * i)) & 0xFF for i in range(4)]
    if p[2] == 0xA5 and p[3] == 0x3C:                      # residue 0
        w = (p[1] << 8) | p[0]
        if w < A_WORDS:
            return (w * 4, w, 0, False)
        return None
    if p[1] == 0xA5 and p[2] == 0x3C:                      # residue 1
        hi = p[0]
        lo_next = p[3]
        cands = [(hi << 8) | ((lo_next - 1) & 0xFF)]
        if lo_next == 0x00:                                # w low byte 0xFF, carry
            cands.append((hi << 8) | 0xFF)
        ok = [w for w in cands if w < A_WORDS]
        if not ok:
            return None
        w = ok[0]
        return (w * 4 + 1, w, 1, len(set(ok)) > 1)
    if p[0] == 0xA5 and p[1] == 0x3C:                      # residue 2
        wnext = (p[3] << 8) | p[2]
        w = wnext - 1
        if 0 <= w < A_WORDS and wnext <= A_WORDS:
            return (w * 4 + 2, w, 2, False)
        return None
    if p[3] == 0xA5 and p[0] == 0x3C:                      # residue 3
        wnext = (p[2] << 8) | p[1]
        w = wnext - 1
        if 0 <= w < A_WORDS and wnext <= A_WORDS:
            return (w * 4 + 3, w, 3, False)
        return None
    return None


def encode_expected_word_at_byte_offset(b):
    """The 32-bit value a 32-bit read at byte offset b returns (b <= 16380)."""
    w, r = b >> 2, b & 3
    if r == 0:
        return a_word(w)
    if r == 1:
        return (a_word(w + 1) & 0xFF) << 24 | 0x3C << 16 | 0xA5 << 8 | ((w >> 8) & 0xFF)
    if r == 2:
        wn = w + 1
        return (((wn >> 8) & 0xFF) << 24) | ((wn & 0xFF) << 16) | (0x3C << 8) | 0xA5
    wn = w + 1
    return (0xA5 << 24) | (((wn >> 8) & 0xFF) << 16) | ((wn & 0xFF) << 8) | 0x3C


def decode_store_diff(tgt_words):
    """Decode the st observation: tgt as a list of 2048 u32 (post-run).

    Returns {"byte_offset": b or None, "words_changed": [...], "bytes": {off: val}}
    for the first contiguous 4-byte window matching STORE_CONST little-endian.
    """
    raw = b"".join(struct.pack("<I", v) for v in tgt_words)
    want = struct.pack("<I", STORE_CONST)
    idx = raw.find(want)
    out = {"byte_offset": None, "words_changed": [], "nonzero_bytes": {}}
    changed = [i for i, v in enumerate(tgt_words) if v != 0]
    out["words_changed"] = changed
    for i, b in enumerate(raw):
        if b != 0:
            out["nonzero_bytes"][i] = b
    if idx >= 0:
        out["byte_offset"] = idx
    return out


def pred_b(j, off_u, off_s, code, scale):
    """Predicted byte offsets under the competing hypotheses."""
    s = ELEM_SCALE[code]
    helem_u = ((j + off_u) * s) & 0xFFFFFFFF
    helem_s = ((j + off_s) * s) & 0xFFFFFFFF
    hbyte_u = (j * s + off_u) & 0xFFFFFFFF
    return {"H-ELEM+H-U": helem_u, "H-ELEM+H-S": helem_s, "H-BYTE+H-U": hbyte_u}


CASES = []


def case(name, item, kernel, idx, fields=None, pred=None, note=""):
    CASES.append({"name": name, "item": item, "kernel": kernel,
                  "idx": list(idx), "fields": fields or {}, "pred": pred or {},
                  "note": note})


# ---------------------------------------------------------------------------
# C-CTRL: unspliced controls (both kernels). j = i0.
# ---------------------------------------------------------------------------
case("ld_ctrl_idx64", "CTRL", "ld", [64, 0, 77, 909], {},
     {"H-ELEM+H-U": 256, "H-ELEM+H-S": 256, "H-BYTE+H-U": 256})
case("ld_ctrl_idx1", "CTRL", "ld", [1, 0, 77, 909], {},
     {"H-ELEM+H-U": 4, "H-ELEM+H-S": 4, "H-BYTE+H-U": 4})
case("ld_ctrl_idx0", "CTRL", "ld", [0, 0, 77, 909], {},
     {"H-ELEM+H-U": 0, "H-ELEM+H-S": 0, "H-BYTE+H-U": 0})
case("ld_ctrl_idx2047", "CTRL", "ld", [2047, 0, 77, 909], {},
     {"H-ELEM+H-U": 8188, "H-ELEM+H-S": 8188, "H-BYTE+H-U": 8188})
case("st_ctrl_idx64", "CTRL", "st", [64, 0, 77, 909], {},
     {"H-ELEM+H-U": 256, "H-ELEM+H-S": 256, "H-BYTE+H-U": 256})
case("st_ctrl_idx0", "CTRL", "st", [0, 0, 77, 909], {},
     {"H-ELEM+H-U": 0, "H-ELEM+H-S": 0, "H-BYTE+H-U": 0})

# ---------------------------------------------------------------------------
# VAL-IDXREG: byte+5 index-register selection re-validation on the 0x44-form
# load (RT-1a A18-proven field; M4 re-validation datum, non-load-bearing).
# i1 = 1 so the live registers hold distinguishable values:
#   r0 = j = 65, vec4 r5..r8 = i0..i3 = 64, 1, 77, 909.
# ---------------------------------------------------------------------------
for tag, reg in (("r0_j", 0x00), ("r1", 0x01), ("r2", 0x02), ("r3", 0x03),
                 ("r4", 0x04), ("r5_i0", 0x05), ("r6_i1", 0x06), ("r7_i2", 0x07),
                 ("r0_j_b7", 0x80), ("r1_b7", 0x81), ("r5_b7", 0x85),
                 ("r0x40", 0x40), ("r0x7f", 0x7F), ("r0xff", 0xFF)):
    case("ld_idxreg_" + tag, "VAL-IDXREG", "ld", [64, 1, 77, 909],
         {"index_reg": reg}, {}, note="observed value identifies which GPR fed the index")

# ---------------------------------------------------------------------------
# MEM-01: is the GPR index scaled by the encoded element size?
# idx=1 and idx=3/5 across elem codes; predicted B under H-SC.
# ---------------------------------------------------------------------------
for code in (1, 2, 3, 4, 0):
    case("ld_scale1_code%d" % code, "MEM-01", "ld", [1, 0, 77, 909],
         {"elem_size": ELEM_BYTE[code]},
         {"H-ELEM+H-U": 1 * ELEM_SCALE[code], "H-ELEM+H-S": 1 * ELEM_SCALE[code],
          "H-BYTE+H-U": 1 * ELEM_SCALE[code]})
for code in (1, 2, 3, 4):
    case("ld_scale3_code%d" % code, "MEM-01", "ld", [3, 0, 77, 909],
         {"elem_size": ELEM_BYTE[code]},
         {"H-ELEM+H-U": 3 * ELEM_SCALE[code], "H-ELEM+H-S": 3 * ELEM_SCALE[code],
          "H-BYTE+H-U": 3 * ELEM_SCALE[code]})
case("ld_scale5_code4", "MEM-01", "ld", [5, 0, 77, 909], {"elem_size": ELEM_BYTE[4]},
     {"H-ELEM+H-U": 40, "H-ELEM+H-S": 40, "H-BYTE+H-U": 40})
case("ld_scale17_code1", "MEM-01", "ld", [17, 0, 77, 909], {"elem_size": ELEM_BYTE[1]},
     {"H-ELEM+H-U": 17, "H-ELEM+H-S": 17, "H-BYTE+H-U": 17})
# store side: byte+12 spliced across the code table (st baseline byte+12=0x11;
# its scale semantics are probed, not pre-assumed)
for val, tag in ((0x10, "c0"), (0x12, "c1"), (0x14, "c2"), (0x18, "c3"),
                 (0x40, "c8"), (0x42, "c1b"), (0x44, "c2b"), (0x46, "c3b"),
                 (0x48, "c4b"), (0x4A, "c5b"), (0x00, "zero"), (0x11, "base_echo")):
    case("st_scale1_%s" % tag, "MEM-01", "st", [1, 0, 77, 909], {"elem_size": val},
         {}, note="store stride observation; byte+12 baseline 0x11")

# ---------------------------------------------------------------------------
# MEM-02: is the immediate offset added in ELEMENT units (H-ELEM) or BYTE units
# (H-BYTE)?  Cases where the two hypotheses predict different byte offsets.
# ---------------------------------------------------------------------------
case("ld_off1_code3_idx0", "MEM-02", "ld", [0, 0, 77, 909], {"idx_off": 1},
     pred_b(0, 1, 1, 3, 4))
case("ld_off2_code3_idx0", "MEM-02", "ld", [0, 0, 77, 909], {"idx_off": 2},
     pred_b(0, 2, 2, 3, 4))
case("ld_off1_code3_idx1", "MEM-02", "ld", [1, 0, 77, 909], {"idx_off": 1},
     pred_b(1, 1, 1, 3, 4))
case("ld_off2_code2_idx0", "MEM-02", "ld", [0, 0, 77, 909],
     {"idx_off": 2, "elem_size": ELEM_BYTE[2]}, pred_b(0, 2, 2, 2, 2))
case("ld_off3_code2_idx2", "MEM-02", "ld", [2, 0, 77, 909],
     {"idx_off": 3, "elem_size": ELEM_BYTE[2]}, pred_b(2, 3, 3, 2, 2))
case("ld_off1_code1_idx0", "MEM-02", "ld", [0, 0, 77, 909],
     {"idx_off": 1, "elem_size": ELEM_BYTE[1]}, pred_b(0, 1, 1, 1, 1))
case("ld_off4_code1_idx0", "MEM-02", "ld", [0, 0, 77, 909],
     {"idx_off": 4, "elem_size": ELEM_BYTE[1]}, pred_b(0, 4, 4, 1, 1))
case("ld_off1_code4_idx1", "MEM-02", "ld", [1, 0, 77, 909],
     {"idx_off": 1, "elem_size": ELEM_BYTE[4]}, pred_b(1, 1, 1, 4, 8))
case("st_off1_idx64", "MEM-02", "st", [64, 0, 77, 909], {"idx_off": 1},
     {"H-ELEM+H-U": 260, "H-ELEM+H-S": 260, "H-BYTE+H-U": 257})
case("st_off2_idx64", "MEM-02", "st", [64, 0, 77, 909], {"idx_off": 2},
     {"H-ELEM+H-U": 264, "H-ELEM+H-S": 264, "H-BYTE+H-U": 258})
case("st_off1_idx0", "MEM-02", "st", [0, 0, 77, 909], {"idx_off": 1},
     {"H-ELEM+H-U": 4, "H-ELEM+H-S": 4, "H-BYTE+H-U": 1})
case("st_off1_idx1", "MEM-02", "st", [1, 0, 77, 909], {"idx_off": 1},
     {"H-ELEM+H-U": 8, "H-ELEM+H-S": 8, "H-BYTE+H-U": 5})

# ---------------------------------------------------------------------------
# MEM-03 (dense): full 11-bit idx_off sweep at idx=1024. Every field value
# lands in-bounds under BOTH signedness hypotheses (elements 0..3071), so any
# fault/zero/miss in this family is a hole or failure-mode datum.
# ---------------------------------------------------------------------------
for f in range(0, 2048):
    case("ld_range_f%04d" % f, "MEM-03", "ld", [1024, 0, 77, 909], {"idx_off": f},
         pred_b(1024, f, sext11(f), 3, 4))

# MEM-03 (negative-side OOB): idx=64; under H-S the high field values go below
# the buffer -> first-invalid / failure-mode observation. Under H-U they stay
# in-bounds. Also the byte+11 bits2..7 (format tail) inertness probes.
for f in (0x3FE, 0x3FF, 0x400, 0x401, 0x402, 0x7FE, 0x7FF):
    case("ld_neg_f%04x" % f, "MEM-03", "ld", [64, 0, 77, 909], {"idx_off": f},
         pred_b(64, f, sext11(f), 3, 4))
for tag, b11 in (("b44", 0x44), ("b48", 0x48), ("b50", 0x50), ("b60", 0x60),
                 ("bc0", 0xC0), ("b00", 0x00)):
    case("ld_tail11_%s" % tag, "MEM-03", "ld", [1024, 0, 77, 909],
         {"ldform_hi11": b11 >> 2}, {"H-ELEM+H-U": 4096, "H-ELEM+H-S": 4096,
                                     "H-BYTE+H-U": 4096},
         note="byte+11 bits2..7 (format tail) inertness for the offset")
case("ld_tail9_dst5", "MEM-03", "ld", [64, 0, 77, 909], {"dst_ext9": 5}, {},
     note="byte+9 bits0..6 (dst reg ext) is NOT offset: expect consumer break, not a[64]")
case("ld_tail9_dst0", "MEM-03", "ld", [64, 0, 77, 909], {"dst_ext9": 0}, {},
     note="byte+9 bits0..6 (dst reg ext) is NOT offset: expect consumer break, not a[64]")
case("st_off_max_1ff", "MEM-03", "st", [1024, 0, 77, 909], {"idx_off": 0x1FF},
     {"H-ELEM+H-U": (1024 + 511) * 4, "H-ELEM+H-S": (1024 + 511) * 4,
      "H-BYTE+H-U": 4096 + 511})
case("st_off_200", "MEM-03", "st", [1024, 0, 77, 909], {"idx_off": 0x200},
     {"H-ELEM+H-U": (1024 + 512) * 4, "H-ELEM+H-S": (1024 + 512) * 4,
      "H-BYTE+H-U": 4096 + 512})
case("st_off_3ff", "MEM-03", "st", [1024, 0, 77, 909], {"idx_off": 0x3FF},
     {"H-ELEM+H-U": (1024 + 1023) * 4, "H-ELEM+H-S": (1024 + 1023) * 4,
      "H-BYTE+H-U": 4096 + 1023})
case("st_off_400", "MEM-03", "st", [1024, 0, 77, 909], {"idx_off": 0x400},
     {"H-ELEM+H-U": (1024 + 1024) * 4, "H-ELEM+H-S": (1024 - 1024) * 4,
      "H-BYTE+H-U": 4096 + 1024})
case("st_off_7ff", "MEM-03", "st", [1024, 0, 77, 909], {"idx_off": 0x7FF},
     {"H-ELEM+H-U": (1024 + 2047) * 4, "H-ELEM+H-S": (1024 - 1) * 4,
      "H-BYTE+H-U": 4096 + 2047})
case("st_off_7ff_idx1023", "MEM-03", "st", [1023, 0, 77, 909], {"idx_off": 0x7FF},
     {"H-ELEM+H-U": (1023 + 2047) * 4, "H-ELEM+H-S": (1023 - 1) * 4,
      "H-BYTE+H-U": 4092 + 2047})

# ---------------------------------------------------------------------------
# MEM-04: can the instruction encode base + index*stride + offset for arbitrary
# strides? Probe the elem-code ceiling (codes 5..7, odd codes, high bits) --
# every WORKING code is a power of two; no field combination yields stride 3.
# ---------------------------------------------------------------------------
for val, tag in ((0x4A, "code5"), (0x4C, "code6"), (0x4E, "code7"),
                 (0x50, "code8"), (0x58, "c11"), (0x60, "c16"), (0x00, "code0"),
                 (0x02, "c0b1"), (0x06, "c0b3"), (0x41, "odd0"), (0x43, "odd1"),
                 (0x45, "odd2"), (0x47, "odd3"), (0x49, "odd4"), (0x4F, "odd5"),
                 (0xC6, "hi_c6"), (0x86, "hi_b7"), (0xFF, "all1")):
    case("ld_elemcode_%s" % tag, "MEM-04", "ld", [1, 0, 77, 909],
         {"elem_size": val}, {}, note="element-size code space probe (idx=1)")
case("ld_elemcode_code5_idx3", "MEM-04", "ld", [3, 0, 77, 909],
     {"elem_size": 0x4A}, {}, note="code5 stride linearity (idx=3)")
case("ld_stride3_try", "MEM-04", "ld", [1, 0, 77, 909], {},
     {"H-ELEM+H-U": 4, "H-ELEM+H-S": 4, "H-BYTE+H-U": 4},
     note="control: no encoding produces stride 3; baseline idx=1 reads word 1")
for val, tag in ((0x1A, "code5"), (0x1C, "code6"), (0x30, "hi"), (0x13, "odd"),
                 (0x10, "c0")):
    case("st_elemcode_%s" % tag, "MEM-04", "st", [1, 0, 77, 909],
         {"elem_size": val}, {}, note="store byte+12 code space probe (idx=1)")

# ---------------------------------------------------------------------------
# MEM-05: does 32-bit address/index arithmetic wrap exactly mod 2^32 (H-W32)?
# j = i0 (i1=0). Wrapped predictions land at word 0; the far-OOB controls would
# read/store far outside under no-wrap.
# ---------------------------------------------------------------------------
case("ld_wrap_ffffffff_p1", "MEM-05", "ld", [0xFFFFFFFF, 0, 77, 909], {"idx_off": 1},
     {"H-ELEM+H-U+H-W32": 0, "H-ELEM+H-S+H-W32": 0})
case("ld_wrap_ffffffff_p0_1b", "MEM-05", "ld", [0xFFFFFFFF, 0, 77, 909],
     {"elem_size": ELEM_BYTE[1]}, {"H-ELEM+H-U": 0xFFFFFFFF},
     note="far-OOB read control (byte 0xFFFFFFFF) -> failure mode datum")
case("ld_wrap_40000000", "MEM-05", "ld", [0x40000000, 0, 77, 909], {},
     {"H-ELEM+H-U+H-W32": 0})
case("ld_wrap_7fffffff_p1", "MEM-05", "ld", [0x7FFFFFFF, 0, 77, 909], {"idx_off": 1},
     {"H-ELEM+H-U+H-W32": 0})
case("ld_wrap_c0000000", "MEM-05", "ld", [0xC0000000, 0, 77, 909], {},
     {"H-ELEM+H-U+H-W32": 0})
case("ld_wrap_3fffffff_p1", "MEM-05", "ld", [0x3FFFFFFF, 0, 77, 909], {"idx_off": 1},
     {"H-ELEM+H-U+H-W32": 0})
case("ld_wrap_3fffffff_p0", "MEM-05", "ld", [0x3FFFFFFF, 0, 77, 909], {},
     {"H-ELEM+H-U": 0xFFFFFFFC},
     note="far-OOB control: (0x3FFFFFFF*4) just below 2^32 without the +1")
case("ld_wrap_ffffffff_p2_2b", "MEM-05", "ld", [0xFFFFFFFF, 0, 77, 909],
     {"idx_off": 2, "elem_size": ELEM_BYTE[2]}, {"H-ELEM+H-U+H-W32": 2})
case("ld_wrap_80000000_1b", "MEM-05", "ld", [0x80000000, 0, 77, 909],
     {"elem_size": ELEM_BYTE[1]}, {"H-ELEM+H-U": 0x80000000},
     note="mid-OOB read control (2 GiB offset)")
case("st_wrap_ffffffff_p1", "MEM-05", "st", [0xFFFFFFFF, 0, 77, 909], {"idx_off": 1},
     {"H-ELEM+H-U+H-W32": 0})
case("st_wrap_40000000", "MEM-05", "st", [0x40000000, 0, 77, 909], {},
     {"H-ELEM+H-U+H-W32": 0})

# ---------------------------------------------------------------------------
# VAL-EXTRA: cheap ties to prior A18-side evidence (byte+1 space selector,
# byte+6 inertness) so the probe instruction is anchored to the documented
# family behavior on M4.
# ---------------------------------------------------------------------------
for tag, b1 in (("tg02", 0x02), ("dev10", 0x10)):
    case("ld_space_%s" % tag, "VAL-EXTRA", "ld", [64, 0, 77, 909], {"space": b1},
         {}, note="byte+1 space selector (0x02 expected to read 0 per A18 evidence)")
for tag, b6 in (("zero", 0x00), ("ff", 0xFF)):
    case("ld_inert6_%s" % tag, "VAL-EXTRA", "ld", [64, 0, 77, 909],
         {"access_desc": b6}, {}, note="byte+6 inertness (A18-side RT-1a evidence)")

CASES = tuple(CASES)
TOTAL = len(CASES)


def dense_anchors():
    """(first, last) dense-sweep case names + their frozen predictions."""
    fam = [c for c in CASES if c["item"] == "MEM-03" and c["name"].startswith("ld_range_f")]
    return fam[0], fam[-1]


def hand_validation():
    """Frozen hand-computed set: case name -> exact expected 32-bit observation
    under the leading hypotheses (computed BY HAND from the fill pattern, not by
    encode_expected_word_at_byte_offset; analysis.py cross-checks both)."""
    return [
        # ld_ctrl_idx64: element 64, 4B aligned -> a[64] = 0x3CA50040
        ("ld_ctrl_idx64", 0x3CA50040),
        # ld_ctrl_idx1 -> a[1] = 0x3CA50001
        ("ld_ctrl_idx1", 0x3CA50001),
        # ld_scale1_code1: idx=1, 1B elements -> byte offset 1: bytes
        # [b1(0)=0x00, 0xA5, 0x3C, b0(1)=0x01] -> 0x013CA500
        ("ld_scale1_code1", 0x013CA500),
        # ld_scale1_code2: byte offset 2: [0xA5, 0x3C, 0x01, 0x00] -> 0x00013CA5
        ("ld_scale1_code2", 0x00013CA5),
        # ld_scale1_code4: byte offset 8 -> word 2 aligned -> 0x3CA50002
        ("ld_scale1_code4", 0x3CA50002),
        # ld_scale1_code0 (16B): byte offset 16 -> word 4 -> 0x3CA50004
        ("ld_scale1_code0", 0x3CA50004),
        # ld_off1_code3_idx0 under H-ELEM: word 1 -> 0x3CA50001;
        # under H-BYTE: byte 1 -> 0x013CA500 (both frozen, hand values)
        ("ld_off1_code3_idx0", 0x3CA50001),
        # ld_range_f0000: idx 1024, off 0 -> word 1024 = 0x3CA50400
        ("ld_range_f0000", 0x3CA50400),
        # ld_range_f0001: off +1 -> word 1025 = 0x3CA50401
        ("ld_range_f0001", 0x3CA50401),
        # ld_wrap_ffffffff_p1 under H-W32: word 0 -> 0x3CA50000
        ("ld_wrap_ffffffff_p1", 0x3CA50000),
    ]
