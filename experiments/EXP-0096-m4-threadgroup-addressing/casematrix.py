#!/usr/bin/env python3
"""EXP-0096 frozen perturbation matrix + observation codec (single source of
truth), closing GLCS-A01 (compute launch ABI is NOT this experiment's job --
see APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md; GLCS-A01 is out of Bundle F's scope,
which is GLCS-A02 only) and GLCS-A02 (threadgroup/shared-memory addressing and
finite allocation semantics). Methodology copied from
../EXP-0082-m4-mem-offset-semantics/casematrix.py: a large frozen splice
matrix, one field FAMILY changed per case, an exact host-computed expected
observation per case, decided BEFORE any GPU dispatch.

Two splice mechanisms, both first-class and both documented (this is itself a
GLCS-A02 finding, not a shortcut):

  * kernels/tga.metal probes the `tg_addr_compute` (0x1c) instruction. The
    tools/agx-isa DB models ONLY b3/b4/b5 (byte+3/4/5) as real fields (type
    "mod"); byte0 (whole byte, including the high nibble prior A18 evidence
    calls a LIVE dst/operand selector) and byte+1 (also LIVE) are pinned by
    the DB's own `match` clause. tools/agx-isa's assembler therefore CANNOT
    express a byte0-hi or byte+1 variant through its field mechanism -- this
    is the "assembler cannot express an encoding" case the dispatch names as
    a first-class finding. Those two are spliced by DIRECT RAW BYTE PATCH
    (raw_byte0_hi / raw_byte1 / raw_byte2 in `fields`); b3/b4/b5 go through
    the normal isadb decode/assemble round trip (raw_* and b3/b4/b5 are never
    mixed in the same case -- one field family per case, same discipline as
    EXP-0082).
  * kernels/tg_ld.metal / tg_st.metal probe the ordinary device_load /
    device_store instruction family with the threadgroup space bit set --
    the SAME instruction EXP-0082 already decoded for device space. All of
    idx_off / elem_size / index_reg / space ARE real isadb fields here, so
    these cases use isadb.assemble exactly as EXP-0082 did, unmodified.

Authoring-stage finding (compile-only, no GPU dispatch, see
PRE_REGISTRATION.md): `tg_addr_compute` is emitted ONLY for the
compile-time-constant-offset masked-index pattern proven in prior A18
evidence (own-MSL k_thr.metal / EXP-M4-14); substituting a device/idxbuf-
sourced runtime offset for either compile-time constant makes the compiler
NOT emit it (three independent authored variants tried, none emitted it).
Consequently `tga.metal` keeps the compile-time-constant-offset shape and
gets its RUNTIME variability from thread ID and device input data, not from
an idxbuf-controlled address -- the splice matrix supplies all the address
variation instead, which is exactly what a splice-and-observe method needs.
"""
import hashlib
import struct

# ---------------------------------------------------------------------------
# tga family: threadgroup float tile[256], baseline o[i] = ((i+1)&255) +
# ((i+2)&255) via tile[li]=a[i] (a[i]=i identity fill), one thread per element,
# grid=256 tg=256. Confirmed on this M4 host at authoring time (PRE_REGISTRATION.md):
# baseline RESULT = 3,5,7,...,509,255,1 (i=0..253 -> 2i+3; i=254->255; i=255->1).
# ---------------------------------------------------------------------------
TGA_N = 256


def tga_baseline():
    out = []
    for i in range(TGA_N):
        out.append(((i + 1) & 255) + ((i + 2) & 255))
    return out


def tga_corrupt_ip2():
    """The known A18-side corruption pattern for a byte0-hi perturbation:
    o[i] = (i+2) mod 256 (confirmed byte-identical on this M4 at authoring
    time: splicing byte0 0x1c->0x2c gave RESULT 2,3,4,...,255,0,1)."""
    return [(i + 2) & 255 for i in range(TGA_N)]


def fill_a_identity_f32():
    return b"".join(struct.pack("<f", float(i)) for i in range(TGA_N))


def decode_tga_output(hexbytes):
    """hexbytes: 256 little-endian float32 values (1024 bytes) as produced by
    `--out 0=256`. Returns a list of 256 ints (values are always small exact
    integers under every case this matrix exercises) or None if any value is
    not an exact small integer (a genuine NaN/garbage observation)."""
    if hexbytes is None or len(hexbytes) < TGA_N * 8:
        return None
    raw = bytes.fromhex(hexbytes[:TGA_N * 8])
    vals = struct.unpack("<%df" % TGA_N, raw)
    out = []
    for v in vals:
        if v != v or abs(v) > 1e6 or v != int(v):   # NaN, huge, or non-integral
            return None
        out.append(int(v))
    return out


def tga_dstreg_bit3_pairs():
    """The 8 (low3, bit3) pairs the TGA-DSTREG family's byte0-hi sweep is
    built from: (hi, hi|0x8) for hi in 0..7. analysis.py uses this to test
    the retention-flag-vs-index-bit hypothesis (see the caution above
    tga_dstreg's case() calls) without assuming an answer here."""
    return [(hi, hi | 0x8) for hi in range(8)]


def tga_summary(observed):
    """Compact, deterministic summary of a 256-value tga observation against
    the two named hypotheses (baseline / known ip2-corruption), plus a raw
    diff digest so an unnamed pattern is not silently discarded."""
    if observed is None:
        return {"decodable": False}
    base = tga_baseline()
    ip2 = tga_corrupt_ip2()
    diffs_base = [i for i in range(TGA_N) if observed[i] != base[i]]
    return {
        "decodable": True,
        "matches_baseline": observed == base,
        "matches_known_ip2_corruption": observed == ip2,
        "num_diff_from_baseline": len(diffs_base),
        "first_diff_index": diffs_base[0] if diffs_base else None,
        "first_diff_values": ([observed[diffs_base[0]], base[diffs_base[0]]]
                              if diffs_base else None),
        "observed_sha256": hashlib.sha256(
            b"".join(struct.pack("<i", v) for v in observed)).hexdigest(),
    }


# ---------------------------------------------------------------------------
# tg_ld / tg_st family: threadgroup uint tile[2048] (8 KiB), device_load/store
# with the threadgroup space bit set. Same tag/decode scheme as
# ../EXP-0082-m4-mem-offset-semantics/casematrix.py (byte-for-byte reused
# constants and codec), applied to the threadgroup array instead of a device
# buffer, and to the (empirically DIFFERENT -- see PRE_REGISTRATION.md)
# threadgroup-space field encoding this experiment characterizes.
# ---------------------------------------------------------------------------
A_WORDS = 2048             # tg_ld.metal: threadgroup tile[] AND device a[] (both 2048 words)
TGT_WORDS = 2048           # tg_st.metal: threadgroup tile[] AND the extra[] readback
STORE_CONST = 0x5A17C0DE
A_TAG_HI = 0x3CA50000


def a_word(w):
    return (A_TAG_HI | w) & 0xFFFFFFFF


def fill_a():
    return b"".join(struct.pack("<I", a_word(w)) for w in range(A_WORDS))


def fill_idx(idx):
    return b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in idx)


def sext11(f):
    return f - 2048 if f & 0x400 else f


def decode_load_value(v):
    """Identical codec to EXP-0082's decode_load_value (see that file for the
    full residue-decoding rationale), over the SAME tag pattern and word
    count, now reading the threadgroup tile instead of a device buffer."""
    if not isinstance(v, int) or v < 0 or v > 0xFFFFFFFF:
        return None
    p = [(v >> (8 * i)) & 0xFF for i in range(4)]
    if p[2] == 0xA5 and p[3] == 0x3C:
        w = (p[1] << 8) | p[0]
        if w < A_WORDS:
            return (w * 4, w, 0, False)
        return None
    if p[1] == 0xA5 and p[2] == 0x3C:
        hi = p[0]
        lo_next = p[3]
        cands = [(hi << 8) | ((lo_next - 1) & 0xFF)]
        if lo_next == 0x00:
            cands.append((hi << 8) | 0xFF)
        ok = [w for w in cands if w < A_WORDS]
        if not ok:
            return None
        w = ok[0]
        return (w * 4 + 1, w, 1, len(set(ok)) > 1)
    if p[0] == 0xA5 and p[1] == 0x3C:
        wnext = (p[3] << 8) | p[2]
        w = wnext - 1
        if 0 <= w < A_WORDS and wnext <= A_WORDS:
            return (w * 4 + 2, w, 2, False)
        return None
    if p[3] == 0xA5 and p[0] == 0x3C:
        wnext = (p[2] << 8) | p[1]
        w = wnext - 1
        if 0 <= w < A_WORDS and wnext <= A_WORDS:
            return (w * 4 + 3, w, 3, False)
        return None
    return None


def encode_expected_word_at_byte_offset(b):
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


def pred_b(j, off_u, off_s, scale):
    helem_u = ((j + off_u) * scale) & 0xFFFFFFFF
    helem_s = ((j + off_s) * scale) & 0xFFFFFFFF
    hbyte_u = (j * scale + off_u) & 0xFFFFFFFF
    return {"H-ELEM+H-U": helem_u, "H-ELEM+H-S": helem_s, "H-BYTE+H-U": hbyte_u}


CASES = []


def case(name, item, kernel, idx, fields=None, pred=None, note=""):
    CASES.append({"name": name, "item": item, "kernel": kernel,
                  "idx": list(idx), "fields": fields or {}, "pred": pred or {},
                  "note": note})


# ===========================================================================
# TGA family (kernel="tga"): tg_addr_compute (0x1c) field decode.
# idx is unused for this kernel (no idxbuf) but kept as a 4-int placeholder
# [0,0,0,0] for record-shape uniformity with the other two kernels.
# ===========================================================================
_Z = [0, 0, 0, 0]

case("tga_ctrl", "CTRL", "tga", _Z, {}, {"matches_baseline": True})

# TGA-DSTREG: byte0 HIGH NIBBLE full 16-value sweep (low nibble fixed 0xc).
# 0x1 reproduces the unspliced baseline (identity case, included for the
# family's own internal consistency check).
#
# CAUTION (2026-08-28, coordinator steering input; see
# work/COMPILER-EXPLAINER-INTERACTION-20260828.md and apple9_isa_explainer.md):
# an external compiler engineer's cross-checked bit tables found that our
# db.json's "N-bit register index" fields can silently conflate a REGISTER
# NUMBER with a per-source RETENTION/liveness flag in an adjacent bit (a
# CONFIRMED decoding bug for falu2's 6-byte compact-float srcA_reg/srcB_reg:
# their nominal top bit, bit15/bit31, is a retention flag, not part of the
# index -- two example instructions differing ONLY in retention state decoded
# to DIFFERENT "register numbers" 64 apart under our field layout). That is a
# DIFFERENT instruction family from tg_addr_compute, so the exact bit position
# does not transfer -- but the METHODOLOGICAL lesson does: this experiment
# does NOT assume tg_addr_compute's byte0 high nibble is a clean 4-bit linear
# register/operand index merely because db.json's prose calls it a "dst-
# register/operand selector". analysis.py's tga_dstreg_pairs() (see
# tga_dstreg_bit3_pairs() below) explicitly tests the pairing hypothesis --
# do hi and hi|0x8 (bit3 held/cleared, low 3 bits fixed) show (a) IDENTICAL
# downstream output (bit3 inert for this observable), (b) a retention-style
# signature (one member of the pair behaves like baseline/coherent, the other
# like a dropped/zeroed contributor -- the docs/isa/register-move-and-
# liveness.md silent-zero pattern), or (c) two distinctly different but each
# internally coherent linear patterns (consistent with a true index bit) --
# rather than asserting a width from the sweep shape alone. EXP-0099 is
# settling the general register-field/retention-flag question on hardware in
# parallel; this experiment cross-references it and does not duplicate it.
for hi in range(16):
    case("tga_dstreg_%x" % hi, "TGA-DSTREG", "tga", _Z, {"raw_byte0_hi": hi},
         {}, note="byte0 = (hi<<4)|0xc; hi=1 is the unspliced baseline value; "
                   "do NOT assume this nibble is a clean linear index (see caution above)")

# TGA-SRCSEL: byte+1 FULL dense sweep 0x00..0xFF (the DB match pins this at
# 0x02; prior A18 evidence sampled only {0x00,0x01,0x02,0x03,0x06,0xff}).
for v in range(256):
    case("tga_srcsel_%02x" % v, "TGA-SRCSEL", "tga", _Z, {"raw_byte1": v}, {},
         note="byte+1 full-byte dense sweep; baseline value is 0x02")

# TGA-LENDISC: byte+2 representative sweep (DB match pins this at 0x00; prior
# A18 evidence sampled {0x00,0x01,0x02,0x08,0xff} and found them baseline;
# this widens that sample without the cost of a full 256-value sweep).
_lendisc_vals = sorted(set(list(range(16)) + [0x10 * k for k in range(1, 16)]
                           + [0x81, 0xC4, 0x99, 0xAA, 0x55, 0xE7, 0xFF]))
for v in _lendisc_vals:
    case("tga_lendisc_%02x" % v, "TGA-LENDISC", "tga", _Z, {"raw_byte2": v}, {},
         note="byte+2 representative sweep; baseline value is 0x00; the DB's "
              "own disassembler treats nonzero as a length-form discriminator")

# TGA-RESERVED: b3/b4/b5 (the DB's true "mod" fields), each swept over a
# representative set through isadb.assemble (round-trip proof), plus a
# simultaneous 3-byte perturbation reproducing EXP-M4-14's own ff/ee/dd test.
_rep = sorted(set(list(range(16)) + [0x10 * k for k in range(2, 16)] + [0xFF]))
for fname in ("b3", "b4", "b5"):
    for v in _rep:
        case("tga_%s_%02x" % (fname, v), "TGA-RESERVED", "tga", _Z, {fname: v}, {},
             note="%s DB field sweep (prior A18 evidence: individually inert)" % fname)
case("tga_reserved_simultaneous", "TGA-RESERVED", "tga", _Z,
     {"b3": 0xFF, "b4": 0xEE, "b5": 0xDD}, {"matches_baseline": True},
     note="simultaneous b3/b4/b5 perturbation, mirrors EXP-M4-14's ff/ee/dd test")


# ===========================================================================
# TGLS-LD family (kernel="tg_ld"): threadgroup device_load address fields.
# idx = [i0, i1, i2, i3]; effective GPR index j = i0 + i1 (i1=0 by default).
# ===========================================================================
case("ld_ctrl_idx0", "CTRL", "tg_ld", [0, 0, 77, 909], {},
     {"H-ELEM+H-U": 0})
case("ld_ctrl_idx64", "CTRL", "tg_ld", [64, 0, 77, 909], {},
     {"H-ELEM+H-U": 256})
case("ld_ctrl_idx2047", "CTRL", "tg_ld", [2047, 0, 77, 909], {},
     {"H-ELEM+H-U": 8188})

# TGLS-LD-03 dense: idx=0, idx_off swept 0..2047 -- lands EXACTLY on tile
# elements 0..2047 (the full 8 KiB tile), the direct threadgroup analogue of
# EXP-0082's MEM-03 dense sweep.
for f in range(0, 2048):
    case("ld_range_f%04d" % f, "TGLS-LD-03", "tg_ld", [0, 0, 77, 909], {"idx_off": f},
         {"H-ELEM+H-U": f * 4})

# TGLS-LD-03 boundary continuation: idx=0, RAW field value 2048..2175 --
# immediately past the dense sweep's ceiling. tools/agx-isa's assembler
# HARD-REJECTS idx_off >= 2048 (`ValueError: idx_off=0x800 exceeds width 11`)
# -- a first-class tooling-gap finding discovered while freezing this matrix:
# the assembler enforces an 11-bit ceiling structurally and CANNOT construct
# an out-of-range value through the normal field mechanism. These cases use
# `idx_off_wide_raw` instead (run.py::splice_case, tg_ld/tg_st only): a
# DIRECT RAW BYTE PATCH that treats the combined 17-bit region spanning
# idx_off (bits 79..89) AND the adjacent `ldform_hi11` tail (bits 90..95,
# byte+11 bits 2..7) as one contiguous field, bypassing isadb's width check
# entirely. This necessarily also overwrites `ldform_hi11`'s prior value --
# there is no way to push idx_off past 2047 without doing so under this
# model -- so these cases test a "wider contiguous counter" hypothesis, not
# a clean single-field idx_off value; the label makes this explicit.
for f in range(2048, 2176):
    case("ld_over_f%04d" % f, "TGLS-LD-03", "tg_ld", [0, 0, 77, 909], {"idx_off_wide_raw": f},
         {}, note="RAW 17-bit-window value beyond the assembler's 11-bit idx_off ceiling; "
                   "necessarily also overwrites ldform_hi11 (see family docstring)")

# TGLS-LD-01: elem_size FULL dense sweep (0x00..0xFF) at idx=1 -- the
# threadgroup-space baseline value (0x08) does not match ANY of EXP-0082's
# device-space ELEM_BYTE codes, so this experiment does not assume a code
# table and instead sweeps exhaustively.
for v in range(256):
    case("ld_elemsize_%02x" % v, "TGLS-LD-01", "tg_ld", [1, 0, 77, 909],
         {"elem_size": v}, {}, note="elem_size full-byte dense sweep; baseline is 0x08")

# TGLS-LD index_reg re-validation (mirrors EXP-0082 VAL-IDXREG).
for tag, reg in (("r0_j", 0x00), ("r1", 0x01), ("r2", 0x02), ("r3", 0x03),
                 ("r4", 0x04), ("r5", 0x05), ("r0x40", 0x40), ("r0x7f", 0x7F),
                 ("r0x80", 0x80), ("r0xff", 0xFF)):
    case("ld_idxreg_" + tag, "TGLS-LD-IDXREG", "tg_ld", [64, 1, 77, 909],
         {"index_reg": reg}, {}, note="observed value identifies which GPR fed the index")

# TGLS-LD-05: 32-bit wrap (mirrors EXP-0082 MEM-05).
case("ld_wrap_ffffffff_p1", "TGLS-LD-05", "tg_ld", [0xFFFFFFFF, 0, 77, 909],
     {"idx_off": 1}, {}, note="H-W32 predicts element 0 (wrap); far-OOB otherwise")
case("ld_wrap_40000000", "TGLS-LD-05", "tg_ld", [0x40000000, 0, 77, 909], {}, {},
     note="H-W32 predicts element 0")
case("ld_wrap_7fffffff_p1", "TGLS-LD-05", "tg_ld", [0x7FFFFFFF, 0, 77, 909],
     {"idx_off": 1}, {}, note="H-W32 predicts element 0")
case("ld_wrap_80000000", "TGLS-LD-05", "tg_ld", [0x80000000, 0, 77, 909], {}, {},
     note="far-OOB control, no offset")
case("ld_wrap_3fffffff_p1", "TGLS-LD-05", "tg_ld", [0x3FFFFFFF, 0, 77, 909],
     {"idx_off": 1}, {}, note="H-W32 predicts element 0")

# TGLS-LD VAL-EXTRA: space-bit flip (device vs threadgroup) and access_desc inertness.
for tag, b1 in (("dev", 0x00), ("tg", 0x02), ("hi4", 0x12), ("hi6", 0x42)):
    case("ld_space_%s" % tag, "TGLS-LD-EXTRA", "tg_ld", [64, 0, 77, 909], {"space": b1},
         {}, note="space bit1 selects device(0) vs threadgroup(1); other bits exploration")


# ===========================================================================
# TGLS-ST family (kernel="tg_st"): threadgroup device_store address fields,
# asymmetric (smaller) sweep, exactly mirroring EXP-0082's st_bank treatment.
# ===========================================================================
case("st_ctrl_idx0", "CTRL", "tg_st", [0, 0, 77, 909], {}, {"H-ELEM+H-U": 0})
case("st_ctrl_idx64", "CTRL", "tg_st", [64, 0, 77, 909], {}, {"H-ELEM+H-U": 256})

for f in (0x0, 0x1, 0x1FE, 0x1FF, 0x200, 0x3FE, 0x3FF, 0x400, 0x401, 0x7FE, 0x7FF):
    case("st_off_%03x" % f, "TGLS-ST-03", "tg_st", [0, 0, 77, 909], {"idx_off": f},
         {"H-ELEM+H-U": f * 4}, note="store-side offset boundary probe, idx=0")
case("st_off_800", "TGLS-ST-03", "tg_st", [0, 0, 77, 909], {"idx_off_wide_raw": 0x800},
     {}, note="RAW value beyond the assembler's 11-bit idx_off ceiling (0x800=2048)")
for f in (2040, 2044, 2046, 2047):
    case("st_edge_%d" % f, "TGLS-ST-03", "tg_st", [0, 0, 77, 909], {"idx_off": f},
         {"H-ELEM+H-U": f * 4}, note="store-side tile-capacity edge (tile is exactly 2048 words)")
# beyond the assembler's 11-bit idx_off ceiling: same idx_off_wide_raw raw-patch
# mechanism as TGLS-LD-03's over-ceiling family (see its docstring for the
# "necessarily also overwrites st_desc_hi" caveat -- the store-side tail field
# occupying the same byte+11 bits2..7 position).
for f in (2048, 2049, 2052, 2060, 2100):
    case("st_edge_%d" % f, "TGLS-ST-03", "tg_st", [0, 0, 77, 909], {"idx_off_wide_raw": f},
         {}, note="RAW 17-bit-window value beyond the assembler's 11-bit idx_off ceiling")

for v in (0x00, 0x02, 0x04, 0x08, 0x0A, 0x10, 0x20, 0x40, 0x46, 0x48, 0x80,
          0x81, 0xC0, 0xFF, 0x11, 0x44):
    case("st_elemsize_%02x" % v, "TGLS-ST-01", "tg_st", [1, 0, 77, 909],
         {"elem_size": v}, {}, note="store-side elem_size cross-check; baseline 0x02")

case("st_wrap_ffffffff_p1", "TGLS-ST-05", "tg_st", [0xFFFFFFFF, 0, 77, 909],
     {"idx_off": 1}, {}, note="H-W32 predicts element 0")
case("st_wrap_40000000", "TGLS-ST-05", "tg_st", [0x40000000, 0, 77, 909], {}, {},
     note="H-W32 predicts element 0")

CASES = tuple(CASES)
TOTAL = len(CASES)


def hand_validation():
    """Frozen hand-computed cross-check set (independent of the prediction
    encoder), the same role as EXP-0082's hand_validation(): a small set of
    exact expected values computed BY HAND from the fill patterns and the
    authoring-stage-confirmed baseline formulas."""
    return [
        ("tga_ctrl", "baseline_array", tga_baseline()),
        ("tga_dstreg_2", "known_ip2_corruption", tga_corrupt_ip2()),
        ("ld_ctrl_idx64", "word", 0x3CA50040),
        ("ld_range_f0000", "word", 0x3CA50000),
        ("ld_range_f2047", "word", 0x3CA507FF),
        ("st_ctrl_idx64", "byte_offset", 256),
    ]


# ===========================================================================
# BUDGET family: public-Metal boundary sweep for maximum threadgroup-shared
# bytes, allocation granularity, and the static+dynamic combination rule
# (GLCS-A02's second half). Executed by harness/tgbudget.m, NOT agxtest --
# each case compiles a fresh, argv-parametrized kernel (own-MSL, public Metal
# API only) and reports compile/pipeline/dispatch status plus a full-range
# fill+verify byte count (BAD_BYTE_COUNT) using a bit-mixing (non-periodic)
# hash, not a raw linear one -- see PRE_REGISTRATION.md "authoring-stage
# correction" for why a first draft's linear byte pattern was BLIND to real
# 64 KiB aliasing (period 256 divides 65536 evenly, so a periodic pattern
# cannot distinguish "byte k" from "byte k+65536" and silently passed a
# corrupted case). This experiment's frozen ranges below were chosen AFTER
# authoring-stage calibration (compile+dispatch only, in scratch, never
# promoted/cited as evidence) located two real boundaries:
#   * STATIC (compile-time `threadgroup T tile[N]`): hard MTLComputePipelineState
#     creation FAILURE once the (4-byte-rounded) requested size exceeds 32768 B.
#   * DYNAMIC (`setThreadgroupMemoryLength:`) and COMBINED (static + dynamic in
#     the same kernel): NOT validated by pipeline creation at all; a kernel
#     whose TOTAL static+dynamic footprint exceeds 65536 B (64 KiB) dispatches
#     "successfully" (STATUS OK, no command-buffer error) but SILENTLY
#     CORRUPTS data (BAD_BYTE_COUNT > 0), consistent with (not yet proven to
#     be exactly) a 64 KiB physical aliasing window shared by both static and
#     dynamic threadgroup memory.
# Each case its own process (a fresh compile+dispatch); BUDGET_KEYS (run.py)
# defines the record shape.
# ===========================================================================
def budget_case(name, item, mode, static_bytes, dynamic_bytes, expect_pipeline_ok,
                 expect_clean=None, note=""):
    BUDGET_CASES.append({
        "name": name, "item": item, "mode": mode,
        "static_bytes": static_bytes, "dynamic_bytes": dynamic_bytes,
        "expect_pipeline_ok": expect_pipeline_ok,
        "expect_clean": expect_clean,   # True/False/None(unpredicted) for BAD_BYTE_COUNT==0
        "note": note,
    })


BUDGET_CASES = []

# --- STATIC: coarse capacity sweep + dense boundary bracket -----------------
_static_coarse = sorted(set([0, 1, 2, 3, 4, 8, 16, 17, 32, 64, 100, 128, 256, 512,
                             1000, 1024, 2048, 4096, 8192, 16384, 20480, 24576,
                             28672, 30720, 31744, 32256, 32512, 32752, 32760,
                             32764, 32767, 32768]))
for v in _static_coarse:
    budget_case("static_coarse_%d" % v, "BUDGET-STATIC-CAP", "static", v, 0,
                expect_pipeline_ok=(v <= 32768), expect_clean=True if v <= 32768 else None,
                note="coarse static-bytes capacity sweep")
for v in range(32765, 32800):
    budget_case("static_dense_%d" % v, "BUDGET-STATIC-CAP", "static", v, 0,
                expect_pipeline_ok=(v <= 32768), expect_clean=True if v <= 32768 else None,
                note="dense bracket around the 32768-byte static ceiling")
for v in (32800, 33024, 40960, 65536, 131072):
    budget_case("static_over_%d" % v, "BUDGET-STATIC-CAP", "static", v, 0,
                expect_pipeline_ok=False, expect_clean=None,
                note="beyond-ceiling control, expect PIPELINE_FAIL")

# --- DYNAMIC: coarse + dense boundary bracket + periodicity characterization
_dyn_coarse = sorted(set([0, 1, 2, 3, 4, 8, 16, 17, 32, 64, 100, 128, 256, 512,
                          1000, 1024, 2048, 4096, 8192, 16384, 32768]))
for v in _dyn_coarse:
    budget_case("dynamic_coarse_%d" % v, "BUDGET-DYNAMIC-CAP", "dynamic", 0, v,
                expect_pipeline_ok=True, expect_clean=True,
                note="coarse dynamic-bytes sweep, all well within the 65536 window")
for v in range(65530, 65545):
    budget_case("dynamic_dense_%d" % v, "BUDGET-DYNAMIC-CAP", "dynamic", 0, v,
                expect_pipeline_ok=True, expect_clean=(v <= 65536),
                note="dense bracket around the 65536-byte dynamic aliasing boundary")
for v in (98304, 131072, 196608, 262144, 524288, 1048576):
    budget_case("dynamic_beyond_%d" % v, "BUDGET-DYNAMIC-CAP", "dynamic", 0, v,
                expect_pipeline_ok=True, expect_clean=False,
                note="periodicity/aliasing characterization beyond one 64 KiB window")

# --- COMBINED: static+dynamic split sweep around the shared 65536-byte total
for sfix in (0, 4096, 16384, 32768):
    boundary = 65536 - sfix
    for v in sorted(set([0, 100, max(0, boundary - 1), boundary, boundary + 1,
                         boundary + 100, min(131072 - sfix, boundary + 65536)])):
        total = sfix + v
        budget_case("combined_s%d_d%d" % (sfix, v), "BUDGET-COMBINED", "combined",
                    sfix, v, expect_pipeline_ok=True, expect_clean=(total <= 65536),
                    note="static=%d fixed, dynamic swept around the shared 65536 total" % sfix)
# granularity-focused combined probe (non-power-of-two static split)
for v in sorted(set([65435, 65436, 65437, 65536 - 100, 65536 - 100 + 1])):
    total = 100 + v
    budget_case("combined_gran_s100_d%d" % v, "BUDGET-COMBINED", "combined", 100, v,
                expect_pipeline_ok=True, expect_clean=(total <= 65536),
                note="non-power-of-two static split (100 B) boundary cross-check")

BUDGET_CASES = tuple(BUDGET_CASES)
BUDGET_TOTAL = len(BUDGET_CASES)
