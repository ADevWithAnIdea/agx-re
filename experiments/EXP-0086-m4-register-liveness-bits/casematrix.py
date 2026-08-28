#!/usr/bin/env python3
"""EXP-0086 shared case matrix: kernel metadata, FROZEN compiler-output anchors
(the exact byte offset/hex/fields of the two v-consuming instructions located
during pilot/pre-registration compiles on THIS toolchain), input buffers, an
independent host-side float32 re-implementation of each kernel's arithmetic
(the baseline oracle), and the splice-case generator.

Single source of truth imported by run.py, verify.py and analysis.py (the
EXP-0073/0081 lesson: one definition, never restated).

Candidate register-liveness/"cache" bits under test (both empirically located
by pilot compiles + isadb decode, documented in PRE_REGISTRATION.md):

  CAND_A: the TOP bit of the "srcA_reg" (or, where v is the second operand,
          "srcB_reg") 7-bit register-select field in the float-ALU 2-source
          family (falu2i / falu2 / falu_srcmod12b -- all share a 7-bit
          register field whose low 6 bits are the register number and whose
          top bit we hypothesize is the "cache/last-use" flag). Toggling it
          is `new = natural ^ 0x40` (register number in the low 6 bits is
          preserved bit-for-bit).
  CAND_B: bit 0 of the "opflags" field (spot-checked on the `adjacent` kernel
          only) -- toggled as `new = natural ^ 0x1`.

Every splice is a single field-family change on ONE instruction (or the same
field on BOTH paired instructions for the "flip_both" case, which is one
semantic change -- CAND_A polarity -- applied at its two relevant sites).
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


# -----------------------------------------------------------------------------
# Per-kernel input buffers (buffer 0 = "a"), grid=1 tg=1 (single thread, tid=0)
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
}

OUT_N = {
    "adjacent": 2, "near": 3, "far4": 4, "far16": 3, "pressure": 3,
    "if_boundary": 2, "loop_boundary": 3,
}


# -----------------------------------------------------------------------------
# Independent host-side float32 oracle for out[] (mirrors the MSL source
# exactly, op by op, each intermediate rounded to float32 -- CODEX "capture
# the baseline" is the live GPU run; this is the pre-registered INDEPENDENT
# prediction it is checked against).
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


EXPECTED = {
    "adjacent": expected_adjacent, "near": expected_near, "far4": expected_far4,
    "far16": expected_far16, "pressure": expected_pressure,
    "if_boundary": expected_if_boundary, "loop_boundary": expected_loop_boundary,
}


# -----------------------------------------------------------------------------
# FROZEN anchors: (offset, mnemonic, hex) for the producer's first read (c1)
# and the later/second read (c2) of the SAME underlying register, located by
# decode_one()-driven disassembly of a pilot compile on this exact toolchain
# (git rev + macOS/Metal version pinned in PRE_REGISTRATION.md /
# CAPTURE_CONTRACT.json). baseline.py MUST reproduce these exactly on a fresh
# compile before any capture proceeds (frozen_anchor_diffs gate, EXP-0081
# pattern) -- a toolchain drift is a clean pre-capture stop, not a repair.
#
# reg_field: which field name on that mnemonic holds v's register (top bit =
# CAND_A). c2_out_idx: which `out[]` element the LATER read (c2) ultimately
# feeds (this is NOT always index 1 -- see if_boundary/loop_boundary, where
# the source-order-first variable x1 was rescheduled by the compiler to AFTER
# the branch/loop and is the one sharing v's register with the in-scope read).
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
        # c1 is the register-form fadd INSIDE the if (v + a[tid+2]); c2 is the
        # falu2i x1 SCHEDULED AFTER the if/pop_reconverge that shares v's
        # physical register (NOT the source-adjacent falu2i at +0x5a, which
        # reads the partial sum register, not v).
        "c1": {"offset": 0x54, "mnemonic": "falu2", "hex": "198134030020", "reg_field": "srcA_reg"},
        "c2": {"offset": 0x66, "mnemonic": "falu2i", "hex": "09e514018020", "reg_field": "srcA_reg"},
        "c2_out_idx": 0, "v_low6": 0,
    },
    "loop_boundary": {
        # c1 is the 12-byte extended-form fadd INSIDE the loop body
        # (acc = acc + a[...] + v); c2 is the falu2i x1 SCHEDULED AFTER the
        # loop's pop_reconverge that shares v's physical register. Both
        # NATURAL values are SET (0x41) -- the compiler never emits a
        # cross-loop CLEAR for this pair; the adversarial case forces one.
        "c1": {"offset": 0x94, "mnemonic": "falu_srcmod12b", "hex": "298310058f0454220f0054bc", "reg_field": "srcA_reg"},
        "c2": {"offset": 0xb2, "mnemonic": "falu2i", "hex": "59e504838000", "reg_field": "srcA_reg"},
        "c2_out_idx": 0, "v_low6": 1,
    },
}

KERNELS = list(ANCHORS.keys())

# inert-control field per mnemonic (present, generic "mod" tail; not a proven
# semantic field -- exactly the paired control the task asked for).
INERT_FIELD = {
    "falu2i": "ctrl_lo",
    "falu2": "ctrl",
    "falu_srcmod12b": "ctrl",
}


def _decode(hexstr):
    buf = bytes.fromhex(hexstr)
    rec, length = isadb.decode_one(buf, 0)
    assert isadb.assemble(rec["mnemonic"], rec["fields"]) == buf, "round-trip failed for anchor"
    return rec


def _splice_field(hexstr, field, new_value):
    """Decode hexstr, override ONE field, reassemble. Returns (new_hex, changed_byte_idx)."""
    rec = _decode(hexstr)
    base = bytes.fromhex(hexstr)
    flds = dict(rec["fields"])
    old_value = flds[field]
    flds[field] = new_value
    new = isadb.assemble(rec["mnemonic"], flds)
    changed = [i for i in range(len(base)) if base[i] != new[i]]
    return new.hex(), changed, old_value


def make_cases(kernel):
    """Return the list of case dicts for `kernel`, each:
    {name, item, splice: [(site, field, new_value)], note}
    site in {"c1","c2","both"}. `item` groups cases for the analysis report.
    """
    anc = ANCHORS[kernel]
    c1, c2 = anc["c1"], anc["c2"]
    rec1 = _decode(c1["hex"])
    rec2 = _decode(c2["hex"])
    natA1 = rec1["fields"][c1["reg_field"]]
    natA2 = rec2["fields"][c2["reg_field"]]
    flipA1 = natA1 ^ 0x40
    flipA2 = natA2 ^ 0x40
    cases = []
    cases.append({"name": "baseline", "item": "BASELINE", "splice": [], "note": "no splice"})
    cases.append({"name": "candA_flip_c1", "item": "CAND_A",
                  "splice": [("c1", c1["reg_field"], flipA1)],
                  "note": "flip CAND_A top-bit on c1 only (0x%x->0x%x)" % (natA1, flipA1)})
    cases.append({"name": "candA_flip_c2", "item": "CAND_A",
                  "splice": [("c2", c2["reg_field"], flipA2)],
                  "note": "flip CAND_A top-bit on c2 only (0x%x->0x%x)" % (natA2, flipA2)})
    cases.append({"name": "candA_flip_both", "item": "CAND_A",
                  "splice": [("c1", c1["reg_field"], flipA1), ("c2", c2["reg_field"], flipA2)],
                  "note": "flip CAND_A top-bit on BOTH c1 and c2 (agreement test)"})
    # inert control (paired null): flip bit0 of the presumed-inert ctrl field on c1
    inert_field = INERT_FIELD[c1["mnemonic"]]
    inert_nat = rec1["fields"][inert_field]
    inert_flip = inert_nat ^ 0x1
    cases.append({"name": "inert_control_c1", "item": "CONTROL",
                  "splice": [("c1", inert_field, inert_flip)],
                  "note": "flip a presumed-inert field bit0 on c1 (0x%x->0x%x), null-result control"
                  % (inert_nat, inert_flip)})
    # positive control: redirect c2's LOW 6 register bits to a different register
    low6_2 = natA2 & 0x3F
    top_2 = natA2 & 0x40
    wrong_low6 = (low6_2 + 1) & 0x3F
    posctl_val = top_2 | wrong_low6
    cases.append({"name": "positive_control_c2", "item": "CONTROL",
                  "splice": [("c2", c2["reg_field"], posctl_val)],
                  "note": "redirect c2's operand register (low6 %d->%d), detection-capability positive control"
                  % (low6_2, wrong_low6)})
    if kernel == "adjacent":
        natB1 = rec1["fields"]["opflags"]
        natB2 = rec2["fields"]["opflags"]
        cases.append({"name": "candB_flip_c1", "item": "CAND_B",
                      "splice": [("c1", "opflags", natB1 ^ 0x1)],
                      "note": "flip CAND_B (opflags bit0) on c1 only"})
        cases.append({"name": "candB_flip_c2", "item": "CAND_B",
                      "splice": [("c2", "opflags", natB2 ^ 0x1)],
                      "note": "flip CAND_B (opflags bit0) on c2 only"})
        cases.append({"name": "candB_flip_both", "item": "CAND_B",
                      "splice": [("c1", "opflags", natB1 ^ 0x1), ("c2", "opflags", natB2 ^ 0x1)],
                      "note": "flip CAND_B (opflags bit0) on both c1 and c2"})
    return cases


REPEAT_N = 3


def full_case_list():
    """Every (kernel, case, repeat_index) tuple in the frozen capture order."""
    out = []
    i = 0
    for kernel in KERNELS:
        for case in make_cases(kernel):
            for rep in range(REPEAT_N):
                out.append({"i": i, "kernel": kernel, "rep": rep, **case})
                i += 1
    return out


def build_splice_args(kernel, case, main_hex_map):
    """Turn a case's abstract (site, field, value) list into concrete
    `_agc.main@OFF=HEX` args, re-assembling from the FROZEN anchor hex (not
    from a live re-decode) so every case's splice is traceable to the exact
    committed anchor. main_hex_map: {"c1": current_hex, "c2": current_hex}
    (post any earlier splice in the same case -- sites are independent, so in
    practice always the anchor hex)."""
    anc = ANCHORS[kernel]
    args = []
    changed_total = []
    for site, field, val in case["splice"]:
        off = anc[site]["offset"]
        cur_hex = main_hex_map[site]
        new_hex, changed, _old = _splice_field(cur_hex, field, val)
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
