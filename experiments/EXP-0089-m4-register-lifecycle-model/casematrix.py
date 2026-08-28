#!/usr/bin/env python3
"""EXP-0089 shared case matrix: kernel metadata, FROZEN compiler-output anchors,
input buffers, independent host-side oracles, and the splice-case generator.

Single source of truth imported by run.py, verify.py and analysis.py.

This experiment is a SUCCESSOR to EXP-0086-m4-register-liveness-bits, dispatched
to (1) complete EXP-0086's formal two-run gate (which closed with only run01
valid), (2) test the LITERAL instruction-bit-17 field (the actual 0x54/0x56
byte named in docs/isa/README.md:770), which EXP-0086 could not reach because
bit 17 was opcode-determining in every falu2i/falu2/falu_srcmod12b instance it
could compile, (3) sweep EXP-0086's corrupting CAND_B bit across the distance/
pressure/control-flow conditions it was never tested under, (4) characterize
the "ctrl"/"ctrl_lo" field EXP-0086 found was NOT actually inert, and
(5) build a discriminating case for the producer/consumer model question.

CARRIED OVER VERBATIM from EXP-0086 (byte-identical files / values, re-verified
by a fresh compile on this session's toolchain before reuse -- see
PRE_REGISTRATION.md Sec 1):
  - kernels/{adjacent,near,far4,far16,pressure,if_boundary,loop_boundary}.metal
  - ANCHORS, INPUTS, OUT_N, EXPECTED, INERT_FIELD for those 7 kernels
  - CAND_A case design (candA_flip_c1/c2/both: top-bit of the falu2i/falu2/
    falu_srcmod12b 7-bit register-select field)
  - the _decode/_splice_field/_splice_raw/build_splice_args splice machinery
    (the _splice_raw addition is NEW, for the two lit17 kernels' unpack_convert
    positive control, which db.json cannot express as a named field)

NEW in this experiment:
  - CAND_B (opflags bit0) cases, extended from EXP-0086's "adjacent only" scope
    to ALL 7 original kernels (item 3 of the dispatch: distance/pressure/
    control-flow sweep of the one bit EXP-0086 found corrupts).
  - ctrl/ctrl_lo VALUE SWEEP (8 bit-pattern masks x {c1,c2} x 7 kernels): item 4.
  - LIT17 kernels (lit17_unpack.metal, lit17_cvt.metal): two independent
    instruction families (unpack_convert byte0=0x17, cvt_i2f byte0=0xa7/0x07)
    in which byte+2 (bits 16-23, instruction bit 17 IS the literal claimed bit)
    is a genuinely free field (not opcode-determining -- verified against
    db.json's own `match` tables, see PRE_REGISTRATION.md Sec 2), each
    naturally emitting TWO separate instructions reading the SAME source
    register with the literal 0x56/0x54 polarity: item 2 of the dispatch.
  - discrim3 kernel: a 3-reader extension of "adjacent" (x1=v+10, x2=v+20,
    x3=v+30) used as the producer/consumer discriminating case: item 5.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only use: decode_one / assemble)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def a_bytes(vals):
    return b"".join(struct.pack("<f", f32(v)) for v in vals)


def a_bytes_u32(vals):
    return b"".join(struct.pack("<I", int(v) & 0xFFFFFFFF) for v in vals)


def a_bytes_i32(vals):
    return b"".join(struct.pack("<i", int(v)) for v in vals)


# -----------------------------------------------------------------------------
# Kernel classes
# -----------------------------------------------------------------------------
ORIGINAL_KERNELS = ("adjacent", "near", "far4", "far16", "pressure",
                    "if_boundary", "loop_boundary")
LIT17_KERNELS = ("lit17_unpack", "lit17_cvt")
DISCRIM_KERNELS = ("discrim3",)
KERNELS = ORIGINAL_KERNELS + LIT17_KERNELS + DISCRIM_KERNELS

# -----------------------------------------------------------------------------
# Per-kernel input buffers (buffer 0 = "a"), grid=1 tg=1 (single thread, tid=0)
# CARRIED OVER (7 original kernels): identical to EXP-0086's casematrix.py.
# -----------------------------------------------------------------------------
def _fillN(n):
    return [1000.0 + 13.25 * i for i in range(1, n + 1)]


INPUTS = {
    "adjacent": [7.5],
    "near": [7.5, 1000.0],
    "far4": [7.5, 1000.0, 1013.25, 1026.5, 1039.75],
    "far16": [7.5] + _fillN(16),
    "pressure": [7.5] + _fillN(40),
    "if_boundary": [7.5, 2.0, 3.5],       # a1=2.0 (>0.5 => if-branch taken)
    "loop_boundary": [7.5, 3.0, 100.25, 200.5, 300.75],  # a1=3.0 => n=3
    # NEW kernels:
    "lit17_unpack": [0x70001000],   # single uint32: low16=0x1000, high16=0x7000
    "lit17_cvt": [1234],            # single int32, positive (sign-unambiguous)
    "discrim3": [7.5],
}

OUT_N = {
    "adjacent": 2, "near": 3, "far4": 4, "far16": 3, "pressure": 3,
    "if_boundary": 2, "loop_boundary": 3,
    "lit17_unpack": 2, "lit17_cvt": 2, "discrim3": 3,
}


def input_bytes(kernel):
    """Per-kernel input-buffer byte packer. Default float32 (matches the 7
    original kernels' `device float* a`); lit17_unpack/lit17_cvt declare
    `device uint*`/`device int*` and need the matching raw packing."""
    vals = INPUTS[kernel]
    if kernel == "lit17_unpack":
        return a_bytes_u32(vals)
    if kernel == "lit17_cvt":
        return a_bytes_i32(vals)
    return a_bytes(vals)


# -----------------------------------------------------------------------------
# Independent host-side oracle for out[] (mirrors the MSL source exactly, op
# by op, each intermediate rounded to float32). CARRIED OVER (7 original
# kernels): identical to EXP-0086's casematrix.py.
# -----------------------------------------------------------------------------
def expected_adjacent(a):
    v = a[0]
    return [f32(v + 10.0), f32(v + 20.0)]


def expected_near(a):
    v = a[0]
    x1 = f32(v + 10.0)
    f0 = f32(a[1] + 0.01)
    x2 = f32(v + 20.0)
    return [x1, x2, f0]


def expected_far4(a):
    v = a[0]
    x1 = f32(v + 10.0)
    f0 = f32(a[1] + 0.01)
    f1 = f32(a[2] + 0.02)
    f2 = f32(a[3] + 0.03)
    f3 = f32(a[4] + 0.04)
    x2 = f32(v + 20.0)
    return [x1, x2, f32(f0 + f1), f32(f2 + f3)]


def _expected_farN(a, n):
    v = a[0]
    x1 = f32(v + 10.0)
    fs = [f32(a[i + 1] + 0.001 * (i + 1)) for i in range(n)]
    x2 = f32(v + 20.0)
    s = 0.0
    for f in fs:
        s = f32(s + f)
    return [x1, x2, s]


def expected_far16(a):
    return _expected_farN(a, 16)


def expected_pressure(a):
    return _expected_farN(a, 40)


def expected_if_boundary(a):
    v = a[0]
    x1 = f32(v + 10.0)
    if a[1] > 0.5:
        x2 = f32(f32(v + a[2]) + 20.0)
    else:
        x2 = f32(-1.0)
    return [x1, x2]


def expected_loop_boundary(a):
    v = a[0]
    x1 = f32(v + 10.0)
    n = int(a[1])
    acc = 0.0
    for i in range(n):
        acc = f32(f32(acc + a[2 + i]) + v)
    x2 = f32(v + 20.0)
    return [x1, x2, acc]


# NEW oracles -----------------------------------------------------------------
def expected_lit17_unpack(a):
    """Independent re-implementation of the public MSL Shading Language spec's
    unpack_unorm2x16_to_float / unpack_snorm2x16_to_float (PUBLIC source: the
    formulas are documented behavior of a public Metal builtin, not learned
    from any Apple binary): unorm component = u16/65535; snorm component =
    clamp(int16(u16)/32767, -1, 1)."""
    p = int(a[0]) & 0xFFFFFFFF
    lo = p & 0xFFFF
    hi = (p >> 16) & 0xFFFF
    v1x = f32(lo / 65535.0)
    v1y = f32(hi / 65535.0)
    x1 = f32(v1x + v1y)

    def s16(u):
        i = u if u < 32768 else u - 65536
        val = i / 32767.0
        return max(-1.0, min(1.0, val))
    v2x = f32(s16(lo))
    v2y = f32(s16(hi))
    x2 = f32(v2x + v2y + 5.0)
    return [x1, x2]


def expected_lit17_cvt(a):
    """int->float and (uint)int->float convert + add. Test input is positive
    so the signed/unsigned reinterpretation is numerically identical (scope
    note: this test does not exercise sign-extension, only the literal-bit-17
    splice on two separate same-source-register converts)."""
    v = int(a[0])
    x1 = f32(float(v) + 10.0)
    uv = v & 0xFFFFFFFF
    x2 = f32(float(uv) + 20.0)
    return [x1, x2]


def expected_discrim3(a):
    v = a[0]
    return [f32(v + 10.0), f32(v + 20.0), f32(v + 30.0)]


EXPECTED = {
    "adjacent": expected_adjacent, "near": expected_near, "far4": expected_far4,
    "far16": expected_far16, "pressure": expected_pressure,
    "if_boundary": expected_if_boundary, "loop_boundary": expected_loop_boundary,
    "lit17_unpack": expected_lit17_unpack, "lit17_cvt": expected_lit17_cvt,
    "discrim3": expected_discrim3,
}


# -----------------------------------------------------------------------------
# FROZEN anchors. 7 original kernels CARRIED OVER VERBATIM from EXP-0086's
# casematrix.py (re-verified byte-identical on a fresh compile this session --
# see PRE_REGISTRATION.md Sec 1). lit17_unpack/lit17_cvt/discrim3 are NEW,
# located by this session's own pilot OWN-SHADER compiles (no GPU dispatch),
# frozen here and re-verified fresh by baseline.py before every capture.
# -----------------------------------------------------------------------------
ANCHORS = {
    "adjacent": {
        "c1": {"offset": 0x12, "mnemonic": "falu2i", "hex": "09e5048380c0", "reg_field": "srcA_reg"},
        "c2": {"offset": 0x18, "mnemonic": "falu2i", "hex": "19f514038000", "reg_field": "srcA_reg"},
        "c2_out_idx": 1, "v_low6": 1,
    },
    "near": {
        "c1": {"offset": 0x2a, "mnemonic": "falu2i", "hex": "49e5048380c0", "reg_field": "srcA_reg"},
        "c2": {"offset": 0x40, "mnemonic": "falu2i", "hex": "29f514038000", "reg_field": "srcA_reg"},
        "c2_out_idx": 1, "v_low6": 1,
    },
    "far4": {
        "c1": {"offset": 0x72, "mnemonic": "falu2i", "hex": "09e5048380c0", "reg_field": "srcA_reg"},
        "c2": {"offset": 0x84, "mnemonic": "falu2i", "hex": "19f514038000", "reg_field": "srcA_reg"},
        "c2_out_idx": 1, "v_low6": 1,
    },
    "far16": {
        "c1": {"offset": 0x192, "mnemonic": "falu2i", "hex": "49e5048580c0", "reg_field": "srcA_reg"},
        "c2": {"offset": 0x22c, "mnemonic": "falu2i", "hex": "29f514058000", "reg_field": "srcA_reg"},
        "c2_out_idx": 1, "v_low6": 2,
    },
    "pressure": {
        "c1": {"offset": 0x41e, "mnemonic": "falu2i", "hex": "49e504858000", "reg_field": "srcA_reg"},
        "c2": {"offset": 0x592, "mnemonic": "falu2i", "hex": "29f514058000", "reg_field": "srcA_reg"},
        "c2_out_idx": 1, "v_low6": 2,
    },
    "if_boundary": {
        "c1": {"offset": 0x54, "mnemonic": "falu2", "hex": "198134030020", "reg_field": "srcA_reg"},
        "c2": {"offset": 0x66, "mnemonic": "falu2i", "hex": "09e514018020", "reg_field": "srcA_reg"},
        "c2_out_idx": 0, "v_low6": 0,
    },
    "loop_boundary": {
        "c1": {"offset": 0x94, "mnemonic": "falu_srcmod12b", "hex": "298310058f0454220f0054bc", "reg_field": "srcA_reg"},
        "c2": {"offset": 0xb2, "mnemonic": "falu2i", "hex": "59e504838000", "reg_field": "srcA_reg"},
        "c2_out_idx": 0, "v_low6": 1,
    },
    # NEW: two independent literal-bit-17 families. Both compile source
    # deliberately uses TWO DIFFERENT MSL builtins/casts reading the SAME
    # source register (a single identical expression CSEs into one
    # instruction -- confirmed by pilot; see PRE_REGISTRATION.md Sec 2) so the
    # compiler emits two separate, splice-addressable instructions.
    "lit17_unpack": {
        "c1": {"offset": 0x12, "mnemonic": "unpack_convert", "hex": "1704560401000eaa", "literal_field": "cache"},
        "c2": {"offset": 0x1a, "mnemonic": "unpack_convert", "hex": "1704540001001cca", "literal_field": "cache"},
        "c2_out_idx": 1, "v_low6": None,
    },
    "lit17_cvt": {
        "c1": {"offset": 0x12, "mnemonic": "cvt_i2f", "hex": "a707560003048e60", "literal_field": "mode"},
        "c2": {"offset": 0x1a, "mnemonic": "cvt_i2f", "hex": "a70754020304ac20", "literal_field": "mode"},
        "c2_out_idx": 1, "v_low6": None,
    },
}

DISCRIM_ANCHORS = {
    "discrim3": {
        "x1": {"offset": 0x12, "mnemonic": "falu2i", "hex": "49e5048180c0"},
        "x2": {"offset": 0x18, "mnemonic": "falu2i", "hex": "29f504818000"},
        "x3": {"offset": 0x28, "mnemonic": "falu2i", "hex": "09ff14018000"},
    },
}


def get_anchor(kernel):
    return DISCRIM_ANCHORS[kernel] if kernel in DISCRIM_ANCHORS else ANCHORS[kernel]


def anchor_site_keys(kernel):
    a = get_anchor(kernel)
    return [k for k in a if isinstance(a[k], dict)]


# inert-control field per mnemonic (present, generic "mod" tail; not a proven
# semantic field before this experiment -- CARRIED OVER from EXP-0086, now
# swept over VALUES rather than a single bit0 flip; see make_cases below).
INERT_FIELD = {
    "falu2i": "ctrl_lo",
    "falu2": "ctrl",
    "falu_srcmod12b": "ctrl",
}

# literal-bit-17 field name per lit17 kernel's mnemonic (both are 8-bit MOD
# fields per db.json's own `match` table where every OTHER bit of that byte
# is opcode-fixed -- i.e. flipping 0x02 on this field IS flipping literal
# instruction bit 17 and nothing else; see PRE_REGISTRATION.md Sec 2).
LIT17_FIELD = {"lit17_unpack": "cache", "lit17_cvt": "mode"}

CTRL_MASKS = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x7f)


def _decode(hexstr):
    buf = bytes.fromhex(hexstr)
    rec, length = isadb.decode_one(buf, 0)
    assert isadb.assemble(rec["mnemonic"], rec["fields"]) == buf, "round-trip failed for anchor"
    return rec


def _splice_field(hexstr, field, new_value):
    """Decode hexstr, override ONE named field, reassemble. Returns
    (new_hex, changed_byte_idx, old_value). CARRIED OVER from EXP-0086."""
    rec = _decode(hexstr)
    base = bytes.fromhex(hexstr)
    flds = dict(rec["fields"])
    old_value = flds[field]
    flds[field] = new_value
    new = isadb.assemble(rec["mnemonic"], flds)
    changed = [i for i in range(len(base)) if base[i] != new[i]]
    return new.hex(), changed, old_value


def _splice_raw(hexstr, rel_off, new_byte):
    """Overwrite ONE raw byte at a relative offset within the instruction,
    with NO isadb field model involved. NEW in this experiment: used only for
    lit17_unpack's positive control, whose presumed source-register byte is
    embedded inside db.json's opaque 32-bit `convert_desc` raw field (not
    independently named), so isadb has no field to target. Returns
    (new_hex, changed_byte_idx, old_byte)."""
    b = bytearray(bytes.fromhex(hexstr))
    old = b[rel_off]
    b[rel_off] = new_byte & 0xFF
    return bytes(b).hex(), [rel_off], old


def make_cases(kernel):
    """Case list for one of the 9 c1/c2-shaped kernels (7 original + 2 lit17).
    Each case: {name, item, splice: [(site, kind, key, value), ...], note}.
    kind in {"field","raw"}; site in {"c1","c2","both"->expanded to 2 entries}.
    """
    anc = ANCHORS[kernel]
    c1, c2 = anc["c1"], anc["c2"]
    cases = [{"name": "baseline", "item": "BASELINE", "splice": [], "note": "no splice"}]

    if kernel in ORIGINAL_KERNELS:
        rec1 = _decode(c1["hex"])
        rec2 = _decode(c2["hex"])
        rf1, rf2 = c1["reg_field"], c2["reg_field"]
        natA1 = rec1["fields"][rf1]
        natA2 = rec2["fields"][rf2]
        flipA1 = natA1 ^ 0x40
        flipA2 = natA2 ^ 0x40
        cases += [
            {"name": "candA_flip_c1", "item": "CAND_A",
             "splice": [("c1", "field", rf1, flipA1)],
             "note": "flip CAND_A top-bit on c1 only (0x%x->0x%x)" % (natA1, flipA1)},
            {"name": "candA_flip_c2", "item": "CAND_A",
             "splice": [("c2", "field", rf2, flipA2)],
             "note": "flip CAND_A top-bit on c2 only (0x%x->0x%x)" % (natA2, flipA2)},
            {"name": "candA_flip_both", "item": "CAND_A",
             "splice": [("c1", "field", rf1, flipA1), ("c2", "field", rf2, flipA2)],
             "note": "flip CAND_A top-bit on BOTH c1 and c2 (agreement test)"},
        ]
        natB1 = rec1["fields"]["opflags"]
        natB2 = rec2["fields"]["opflags"]
        flipB1 = natB1 ^ 0x1
        flipB2 = natB2 ^ 0x1
        cases += [
            {"name": "candB_flip_c1", "item": "CAND_B",
             "splice": [("c1", "field", "opflags", flipB1)],
             "note": "flip CAND_B (opflags bit0) on c1 only (0x%x->0x%x)" % (natB1, flipB1)},
            {"name": "candB_flip_c2", "item": "CAND_B",
             "splice": [("c2", "field", "opflags", flipB2)],
             "note": "flip CAND_B (opflags bit0) on c2 only (0x%x->0x%x)" % (natB2, flipB2)},
            {"name": "candB_flip_both", "item": "CAND_B",
             "splice": [("c1", "field", "opflags", flipB1), ("c2", "field", "opflags", flipB2)],
             "note": "flip CAND_B (opflags bit0) on BOTH c1 and c2"},
        ]
        low6_2 = natA2 & 0x3F
        top_2 = natA2 & 0x40
        wrong_low6 = (low6_2 + 1) & 0x3F
        posctl_val = top_2 | wrong_low6
        cases.append({"name": "positive_control_c2", "item": "CONTROL",
                      "splice": [("c2", "field", rf2, posctl_val)],
                      "note": "redirect c2's operand register (low6 %d->%d), detection-capability positive control"
                      % (low6_2, wrong_low6)})
        for site, rec in (("c1", rec1), ("c2", rec2)):
            mnem = anc[site]["mnemonic"]
            field = INERT_FIELD[mnem]
            nat = rec["fields"][field]
            for mask in CTRL_MASKS:
                newval = nat ^ mask
                cases.append({"name": "ctrl_sweep_%s_b%02x" % (site, mask), "item": "CTRL_SWEEP",
                              "splice": [(site, "field", field, newval)],
                              "note": "%s/%s XOR 0x%02x on %s (nat=0x%x -> 0x%x)"
                              % (mnem, field, mask, site, nat, newval)})
        return cases

    if kernel in LIT17_KERNELS:
        rec1 = _decode(c1["hex"])
        rec2 = _decode(c2["hex"])
        field = LIT17_FIELD[kernel]
        nat1 = rec1["fields"][field]
        nat2 = rec2["fields"][field]
        flip1 = nat1 ^ 0x02   # literal instruction bit 17 (byte+2 bit1)
        flip2 = nat2 ^ 0x02
        cases += [
            {"name": "lit17_flip_c1", "item": "LIT17",
             "splice": [("c1", "field", field, flip1)],
             "note": "flip LITERAL bit17 (%s) on c1 only (0x%x->0x%x)" % (field, nat1, flip1)},
            {"name": "lit17_flip_c2", "item": "LIT17",
             "splice": [("c2", "field", field, flip2)],
             "note": "flip LITERAL bit17 (%s) on c2 only (0x%x->0x%x)" % (field, nat2, flip2)},
            {"name": "lit17_flip_both", "item": "LIT17",
             "splice": [("c1", "field", field, flip1), ("c2", "field", field, flip2)],
             "note": "flip LITERAL bit17 (%s) on BOTH c1 and c2" % field},
        ]
        if kernel == "lit17_cvt":
            nat_src = rec2["fields"]["src"]
            wrong_src = nat_src ^ 0x1
            cases.append({"name": "positive_control_c2", "item": "CONTROL",
                          "splice": [("c2", "field", "src", wrong_src)],
                          "note": "redirect c2's src register (%d->%d), detection-capability positive control"
                          % (nat_src, wrong_src)})
        else:  # lit17_unpack: source register is an opaque byte inside
               # db.json's raw `convert_desc` field (byte+4 within the 8-byte
               # instruction), located by pilot byte-diff (both c1 and c2
               # share the SAME byte+4 value == the load's destination
               # register); no named isadb field exists for it, so this is a
               # raw-byte splice, not a field splice.
            nat_byte = int(c2["hex"][8:10], 16)  # byte offset 4 = hex chars 8:10
            wrong_byte = (nat_byte + 1) & 0xFF
            cases.append({"name": "positive_control_c2", "item": "CONTROL",
                          "splice": [("c2", "raw", 4, wrong_byte)],
                          "note": "redirect c2's presumed source-register byte (byte+4, %d->%d, raw splice), "
                                  "detection-capability positive control" % (nat_byte, wrong_byte)})
        return cases

    raise ValueError("unknown kernel class: " + kernel)


def make_discrim_cases():
    """discrim3: three separate later readers (x1,x2,x3) of the same v. Natural
    CAND_B (opflags bit0) values are (x1=0,x2=0,x3=1) on this compile (NOT the
    simple alternating 0/1 pattern EXP-0086 saw with only two readers -- a
    genuine, honestly-reported scheduling difference, see PRE_REGISTRATION.md
    Sec 5/RESULTS.md). The producer/consumer discriminator: does flipping ONE
    reader's bit corrupt only its immediate schedule-neighbor, or every LATER
    reader, or (causally impossible if the mechanism is real) an EARLIER one?
    """
    anc = DISCRIM_ANCHORS["discrim3"]
    recs = {s: _decode(anc[s]["hex"]) for s in ("x1", "x2", "x3")}
    nat = {s: recs[s]["fields"]["opflags"] for s in ("x1", "x2", "x3")}
    flip = {s: nat[s] ^ 0x1 for s in ("x1", "x2", "x3")}
    cases = [{"name": "baseline", "item": "BASELINE", "splice": [], "note": "no splice"}]
    for s in ("x1", "x2", "x3"):
        cases.append({"name": "discrim_flip_%s" % s, "item": "DISCRIM",
                      "splice": [(s, "field", "opflags", flip[s])],
                      "note": "flip CAND_B (opflags bit0) on %s only (0x%x->0x%x)" % (s, nat[s], flip[s])})
    cases.append({"name": "discrim_flip_x1_x2", "item": "DISCRIM",
                  "splice": [("x1", "field", "opflags", flip["x1"]),
                             ("x2", "field", "opflags", flip["x2"])],
                  "note": "flip CAND_B on BOTH x1 and x2 (x3 untouched)"})
    return cases


REPEAT_N = 3


def full_case_list():
    """Every (kernel, case, repeat_index) tuple in the frozen capture order:
    9 c1/c2-shaped kernels (in KERNELS order, skipping discrim3) then discrim3."""
    out = []
    i = 0
    for kernel in ORIGINAL_KERNELS + LIT17_KERNELS:
        for case in make_cases(kernel):
            for rep in range(REPEAT_N):
                out.append({"i": i, "kernel": kernel, "rep": rep, **case})
                i += 1
    for case in make_discrim_cases():
        for rep in range(REPEAT_N):
            out.append({"i": i, "kernel": "discrim3", "rep": rep, **case})
            i += 1
    return out


def build_splice_args(kernel, case, site_hex_map):
    """Turn a case's abstract (site, kind, key, value) list into concrete
    `_agc.main@OFF=HEX` args, re-assembling from the FROZEN anchor hex (not
    from a live re-decode) so every case's splice is traceable to the exact
    committed anchor. site_hex_map: {site_name: current_hex} (post any
    earlier splice in the same case -- sites are independent, so in practice
    always the anchor hex)."""
    anc = get_anchor(kernel)
    args = []
    changed_total = []
    for site, kind, key, val in case["splice"]:
        off = anc[site]["offset"]
        cur_hex = site_hex_map[site]
        if kind == "field":
            new_hex, changed, _old = _splice_field(cur_hex, key, val)
        elif kind == "raw":
            new_hex, changed, _old = _splice_raw(cur_hex, key, val)
        else:
            raise ValueError("unknown splice kind: " + kind)
        base = bytes.fromhex(cur_hex)
        new = bytes.fromhex(new_hex)
        for i in changed:
            args.append("_agc.main@%d=%02x" % (off + i, new[i]))
            changed_total.append(off + i)
    return args, changed_total


if __name__ == "__main__":
    # smoke self-print (no GPU, no Metal): show the full case list summary
    cases = full_case_list()
    print("total cases:", len(cases))
    from collections import Counter
    print(Counter((c["kernel"], c["item"]) for c in cases))
