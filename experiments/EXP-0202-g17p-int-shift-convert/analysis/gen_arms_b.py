#!/usr/bin/env python3
"""EXP-0202 AMENDMENT (v3) arm generator -> harness/arms202b.json.

Supersedes `analysis/gen_arms.py` for the GATED CONFIRMATION pair. It keeps every
v1 arm and adds what `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` requires:

* section 6 (register lifecycle / operand provenance) -- five new
  `shift_amt_move` carriers whose staged amount is produced by a DIFFERENT
  producer class: ALU, thread-position system value, SIMD lane index, an
  overwrite/intervening-ALU lifetime, and a control-flow merge. The v1 set had
  only one producer class in practice, because the compiler lowered the
  thread-invariant amount through a GPR and emitted bytes identical to the
  memory-load carrier.
* section 6 (sources and destinations) -- a SECOND, DISJOINT readback plan for
  `ibitcount.dst`: `pc_dump` keeps four mutually distinct live values per lane at
  fixed store indices, so a redirected destination shows up instead of being
  invisible.

`analysis/gen_arms.py` and `harness/arms202.json` are left untouched: run02
executed against them.

EXP-0202 arm generator.

Reads the pre-freeze census (`raw/prefreeze/census.json`) for OFFSETS and
COMPILED FIELD VALUES -- facts about our own compiled code, not results -- and
emits the exact arm list the gated runs execute. Its sha256 goes into
CAPTURE_CONTRACT.json and into every run's env.json.

Three arm roles, and the gate needs all three (PRE_REGISTRATION.md sections 5-6):

  target      the field under test
  control     a field on the SAME instruction occurrence already at emitter
              grade. It must MOVE in both runs, and at least one of its values
              must FAIL the oracle. An arm whose control does neither has no
              detection power and cannot establish liveness OR inertness.
  dimension   a control in the DIMENSION the target field is believed to select,
              on a DIFFERENT descriptor. `b_alu10_lo7.src_flag` is bit 15 of the
              same 7+1 byte+1 split, with the same enum, in the same 0x?b family
              -- and the compiler emits BOTH values of it in our carriers while
              emitting only 0 for `shift_amt_move.src_flag`. That is the positive
              control FIELD-SWEEP-PROTOCOL section 9 rule 1 demands.

CLEAN-ROOM: derived only from our own compiled MSL.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import carriers202 as C     # noqa: E402

import carriers202b          # noqa: E402,F401  (adds the v3 carriers)

CENSUS = json.loads((EXP / "raw" / "prefreeze" / "census_b.json").read_text())

SR_SET = [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 32, 64, 96, 126, 127]
OPDESC_SET = list(range(16)) + [0x84, 0x85, 0xC0, 0xFF]
MODE_SET = list(range(12)) + [0x54, 0x56, 0x00, 0xFF]

# 24 fixed asymmetric interior samples for the 40-bit joint arm. Generated once
# by a seeded PRNG and PASTED HERE so the arm file is a constant, not a program
# whose output depends on a Python version's RNG.  seed = 20260830.
JOINT_INTERIOR = [
    0x0F1E2D3C4B, 0x5A69788796, 0xA5B4C3D2E1, 0xFEDCBA9876, 0x0123456789,
    0x8000000001, 0x7FFFFFFFFE, 0xAAAAAAAAAA, 0x5555555555, 0xF0F0F0F0F0,
    0x0F0F0F0F0F, 0xCCCCCCCCCC, 0x3333333333, 0xDEADBEEF12, 0x1234ABCDEF,
    0xFF00FF00FF, 0x00FF00FF00, 0xC0FFEE0BAD, 0x0BADC0FFEE, 0x9E3779B97F,
    0x6A09E667F3, 0xBB67AE8584, 0x3C6EF372FE, 0xA54FF53A5F,
]


def occs(mn):
    out = []
    for name, rec in sorted(CENSUS["carriers"].items()):
        hs = [h for h in rec.get("occurrences", {}).get(mn, [])
              if h["tokenizer_agrees"]]
        for i, h in enumerate(hs):
            out.append((name, i, h))
    return out


ARMS = []


def add(arm, carrier, instr, field, off, ilen, start, width, values, role,
        occ, base, note, **kw):
    a = {"arm": arm, "carrier": carrier, "instr": instr, "field": field,
         "off": off, "len": ilen, "start": start, "width": width,
         "values": list(values), "role": role, "occ": occ,
         "baseline_field_value": base, "note": note,
         "group": kw.pop("group", "misc")}
    a.update(kw)
    ARMS.append(a)


# ------------------------------------------------------------------ shift_amt_move
SAM = occs("shift_amt_move")
COMPOSITE = {("sam_gpr", 0), ("sam_uni", 0), ("sam_mix", 0), ("sam_uni2", 0),
             ("sam_alu", 0), ("sam_sys", 0)}
SRSWEEP = {("sam_gpr", 0), ("sam_uni", 0), ("sam_alu", 0)}
for name, i, h in SAM:
    fv, off, ln = h["field_values"], h["off"], h["len"]
    tag = "SAM/%s#%d" % (name, i)
    b1 = (fv["src_reg"] | (fv["src_flag"] << 7))
    if (name, i) in COMPOSITE:
        add(tag + "/byte1", name, "shift_amt_move", "_byte1_composite", off, ln,
            8, 8, range(256), "composite", i, b1,
            "byte+1 dense: src_reg(7) and src_flag(1) SWEPT JOINTLY, so the "
            "128-index profile at src_flag=0 can be compared against the "
            "profile at src_flag=1 -- the two-file comparison the field's own "
            "dimension demands, at no extra dispatch",
            group="sam", oracle_rule="exact_iff_compiled")
    ks = SR_SET if (name, i) in SRSWEEP else [fv["src_reg"]]
    for k in ks:
        pre = ([] if k == fv["src_reg"] else
               [{"off": off, "len": ln, "start": 8, "width": 7, "value": k}])
        add("%s/src_flag@sr%d" % (tag, k), name, "shift_amt_move", "src_flag",
            off, ln, 15, 1, [0, 1], "target", i, fv["src_flag"],
            "src_flag at source index %d: the modelled dimension is WHICH FILE "
            "supplies the staged amount, so the index is held fixed and the "
            "file bit is the only thing that moves" % k,
            group="sam", prepatch=pre, oracle_rule="exact_iff_compiled")
    add(tag + "/kind", name, "shift_amt_move", "kind", off, ln, 20, 4,
        range(16), "control", i, fv["kind"],
        "CONTROL: `kind` is hardware-run on G17P (EXP-0154/0181), ok only at 1 "
        "and 3; it must move and must fail the oracle somewhere",
        group="sam", oracle_rule="control")
    add(tag + "/op_desc", name, "shift_amt_move", "op_desc", off, ln, 24, 8,
        OPDESC_SET, "control", i, fv["op_desc"],
        "CONTROL: `op_desc` is hardware-run on G17P (EXP-0154), ok at only 4 of "
        "256 values", group="sam", oracle_rule="control")

# --------------------------- the SAME-DIMENSION positive control: b_alu10_lo7
for ex in CENSUS.get("srcflag_family_census", {}).get("b_alu10_lo7", {}).get("examples", []):
    name, off = ex["carrier"], ex["off"]
    raw = bytes.fromhex(ex["bytes"])
    v = int.from_bytes(raw, "little")
    sf = (v >> 15) & 1
    sr = (v >> 8) & 0x7F
    tag = "BALU/%s@%d" % (name, off)
    add(tag + "/src_flag", name, "b_alu10_lo7", "src_flag", off, 10, 15, 1,
        [0, 1], "dimension", 0, sf,
        "SAME-DIMENSION POSITIVE CONTROL. bit 15 of byte+1, identical 7+1 split "
        "and identical enum to shift_amt_move.src_flag, in the same 0x?b "
        "family -- and the compiler emits BOTH values of it across our carriers "
        "while emitting only 0 for shift_amt_move. If this moves, the "
        "source-class dimension is demonstrably observable on this harness and "
        "an inert reading of shift_amt_move.src_flag means something.",
        group="balu", oracle_rule="exact_iff_compiled")
    add(tag + "/src_reg", name, "b_alu10_lo7", "src_reg", off, 10, 8, 7,
        list(range(16)) + [32, 64, 96, 127], "control", 0, sr,
        "CONTROL: the index within whichever file src_flag selects",
        group="balu", oracle_rule="control")

# ---------------------------------------------------------------------- irotate
ROT = occs("irotate")
AMOUNT_ARMS = {("rot_k5", 0), ("rot_k13", 0), ("rot_k19", 0), ("rot_alu", 0)}
BYTEWISE = {("rot_k5", 0), ("rot_alu", 0)}
JOINT = {("rot_k5", 0), ("cvt_i64", 0)}
for name, i, h in ROT:
    off, ln = h["off"], h["len"]
    raw = bytes.fromhex(h["bytes"])
    tag = "ROT/%s#%d" % (name, i)
    b6 = raw[6]
    if (name, i) in AMOUNT_ARMS:
        low2 = b6 & 3
        v2a = {}
        for v in range(256):
            if (v & 3) == low2 and (v >> 2) <= 32:
                v2a[str(v)] = (32 - (v >> 2)) % 32
        add(tag + "/operands_b6", name, "irotate", "operands", off, ln, 48, 8,
            range(256), "target", i, b6,
            "byte+6 of the 40-bit operand blob. The census byte-diff over "
            "rotate amounts {1,5,7,13,19,31} showed byte+6 is the ONLY byte "
            "that moves with the amount, at byte+6 = 4*(32-K). This arm carries "
            "an EXACT per-value host oracle -- the rotate-by-K vector the model "
            "predicts -- for the 33 values the model covers, and `unmodelled` "
            "elsewhere. Up to 32 distinct predictions in one arm.",
            group="rot", oracle_rule="rot_amount", value_to_amount=v2a,
            sub="byte+6", post=("alu" if name == "rot_alu" else None))
    if (name, i) in BYTEWISE:
        for bi, st in ((3, 24), (4, 32), (5, 40), (7, 56)):
            add("%s/operands_b%d" % (tag, bi), name, "irotate", "operands", off,
                ln, st, 8, range(256), "target", i, raw[bi],
                "byte+%d of the 40-bit operand blob, dense 0..255 with the other "
                "four bytes at their compiled value (BYTE-WISE MARGINAL)" % bi,
                group="rot", oracle_rule="exact_iff_compiled", sub="byte+%d" % bi)
    if (name, i) in JOINT:
        base = int.from_bytes(raw[3:8], "little")
        vals = ([0, 1, 2, (1 << 40) - 2, (1 << 40) - 1]
                + [1 << k for k in range(40)]
                + [base, (base - 1) & ((1 << 40) - 1), (base + 1) & ((1 << 40) - 1)]
                + [v & ((1 << 40) - 1) for v in JOINT_INTERIOR])
        seen, uniq = set(), []
        for v in vals:
            if v not in seen:
                seen.add(v)
                uniq.append(v)
        add(tag + "/operands_joint", name, "irotate", "operands", off, ln, 24,
            40, uniq, "target", i, base,
            "THE JOINT 40-BIT ARM. FIELD-SWEEP-PROTOCOL 3.3's w>8 bar has never "
            "been met for this field -- the current row says outright that the "
            "40-bit field was never swept jointly and its max/max-1 were never "
            "encoded. Boundaries {0,1,2,max-1,max}, all 40 powers of two, the "
            "compiled value and +/-1, and 24 fixed asymmetric interior samples. "
            "PRE-REGISTERED ABORT at 3 genuine hangs, reported PARTIAL.",
            group="rot", oracle_rule="exact_iff_compiled", sub="joint40",
            hang_budget=3)
    add(tag + "/b2", name, "irotate", "b2", off, ln, 16, 8, [0x54, 0x56],
        "control", i, raw[2],
        "CONTROL: b2 is hardware-run on G17P over its two legal values and "
        "ASYMMETRIC (EXP-0172)", group="rot", oracle_rule="control")
    add(tag + "/tail8", name, "irotate", "tail", off, ln, 64, 8, range(16),
        "control", i, raw[8],
        "CONTROL: byte+8 of `tail`; the M4 accept set is (v & 0xb7) == 0xb0, so "
        "most values must break the result", group="rot", oracle_rule="control")

# -------------------------------------------------------------------- ibitcount
PC = occs("ibitcount")
DSTARMS = {("pc_store", 0), ("pc_alu", 0), ("pc_two", 0), ("iu_ctz", 0),
           ("pc_dump", 0)}
for name, i, h in PC:
    fv, off, ln = h["field_values"], h["off"], h["len"]
    tag = "PC/%s#%d" % (name, i)
    if (name, i) in DSTARMS:
        add(tag + "/dst", name, "ibitcount", "dst", off, ln, 24, 8, range(256),
            "target", i, fv["dst"],
            "dst = reg<<1. PRE-REGISTERED per-value prediction: the following "
            "store still reads the COMPILED register, so the program reproduces "
            "the host vector IFF dst == the compiled value and is broken "
            "otherwise. `iunary.dst` -- the same byte -- faults reproducibly at "
            "192-241 and 243-255 on M4; the G17P behaviour of that region is a "
            "secondary pre-registered question. No abort path.",
            group="pc", oracle_rule="exact_iff_compiled")
    add(tag + "/cache", name, "ibitcount", "cache", off, ln, 17, 1, [0, 1],
        "target", i, fv["cache"],
        "cache = byte+2 bit 1, the RESULT-ROUTING bit (0x54 consumed by a "
        "following ALU / 0x56 standalone writeback). Our carriers span the "
        "routing dimension AND the compiler emits BOTH values across them, so "
        "the dimension is demonstrated rather than asserted. Both directions "
        "are tested: baseline 1 on seven occurrences, baseline 0 on two.",
        group="pc", oracle_rule="exact_iff_compiled")
    add(tag + "/op_enable", name, "ibitcount", "op_enable", off, ln, 32, 8,
        range(16), "control", i, fv["op_enable"],
        "CONTROL: op_enable is hardware-run; bit 1 alone gates the op, so half "
        "these values must break the result", group="pc", oracle_rule="control")
    add(tag + "/srcdesc", name, "ibitcount", "srcdesc", off, ln, 48, 8,
        range(16), "control", i, fv["srcdesc"],
        "CONTROL: srcdesc is hardware-run; 0x00 degenerates the op to identity "
        "and bit 6 must be set for the GPR source to be read",
        group="pc", oracle_rule="control")

# ------------------------------------------------------------------------ iunary
# SYNTHESIS. Our census of 50 authored kernels found ZERO boundary-aligned
# `iunary`-tokenizing instructions, and EXP-0139 found zero in 30 more. The only
# way to reach the fields is to build the encoding: EXP-0139 located
# byte+1 = 0x2d with byte+2 = 0x22 as a byte0==0x27 8-byte member that tokenizes
# as `iunary` (NOT `ibitcount`) and still computes. We rewrite an 8-byte
# `ibitcount` occurrence into that form IN PLACE, keeping its operand bytes, and
# sweep on top of it. The arm's own baseline is the synthesized form with no
# field mutation, so if the synthesis does not compute on G17P the arm is barred.
IU_BASE_B1, IU_BASE_OPSEL = 0x2D, 0x22
for name, i in (("pc_store", 0), ("pc_alu", 0)):
    h = [x for x in occs("ibitcount") if x[0] == name and x[1] == i][0][2]
    off, ln = h["off"], h["len"]
    tag = "IU/%s#%d" % (name, i)
    # BOTH bytes are prepatched on BOTH arms, so each arm's OWN baseline is the
    # complete synthesized `27 2d 22 ..` form and the gate can bar the arm if the
    # synthesis does not compute on G17P. (The field patch is applied after the
    # prepatch and overrides it, so prepatching the swept byte is harmless.)
    pre_both = [{"off": off, "len": ln, "start": 8, "width": 8, "value": IU_BASE_B1},
                {"off": off, "len": ln, "start": 16, "width": 8, "value": IU_BASE_OPSEL}]
    add(tag + "/b1", name, "iunary", "b1", off, ln, 8, 8, range(256), "target",
        i, IU_BASE_B1,
        "byte+1 of the SYNTHESIZED `27 2d 22 ..` iunary form, dense 0..255. "
        "Values that re-tokenize as `ibitcount` or anything else are recorded "
        "and excluded from `encodable_range`.",
        group="iu", prepatch=pre_both, oracle_rule="exact_iff_compiled")
    add(tag + "/opsel", name, "iunary", "opsel", off, ln, 16, 8, range(256),
        "target", i, IU_BASE_OPSEL,
        "byte+2 of the SYNTHESIZED iunary form, dense 0..255. db.json's enum "
        "names 0x56 int-unary/convert, 0x22 rt/interp, 0x10 convert, 0x26 "
        "convert2, 0x07 logic.",
        group="iu", prepatch=pre_both, oracle_rule="exact_iff_compiled")
    add(tag + "/src", name, "iunary", "src", off, ln, 40, 8, range(16),
        "control", i, h["field_values"]["src"],
        "CONTROL on the synthesized instruction: `src` (byte+5, reg<<2) is "
        "hardware-run for this space (EXP-0139); pointing it at an unwritten "
        "register must break the result",
        group="iu", prepatch=pre_both, oracle_rule="control")

# ----------------------------------------------------------------------- cvt_f2i
CVT = occs("cvt_f2i")
B9ARMS = {("cvt_alu", 0), ("cvt_rnd", 0), ("cvt_s32", 0), ("cvt_v4", 0),
          ("cvt_v4", 1), ("iu_h2i", 0)}
for name, i, h in CVT:
    fv, off, ln = h["field_values"], h["off"], h["len"]
    tag = "CVT/%s#%d" % (name, i)
    if (name, i) in B9ARMS:
        add(tag + "/b9", name, "cvt_f2i", "b9", off, ln, 72, 8, range(256),
            "target", i, fv["b9"],
            "byte+9, modelled 'reserved 0x00'. EXP-0168 refused it as "
            "INERT-SINGLE (256/256 ok, one distinct payload) and EXP-0184's five "
            "carriers all varied DESTINATION WIDTH/SIGN -- byte+8's dimension, "
            "not byte+9's. These six occurrences span RESULT ROUTING (mode 0x54 "
            "and 0x56), CONVERT OP (0xb4/0x96/0xac), SOURCE CLASS (2 and 3), "
            "SOURCE WIDTH (float and half) and four destination registers. The "
            "oracle is the LIVE model, so the data can refute it.",
            group="cvt", oracle_rule="exact_iff_compiled")
        add(tag + "/dst", name, "cvt_f2i", "dst", off, ln, 24, 8, range(16),
            "control", i, fv["dst"],
            "CONTROL: cvt_f2i.dst is hardware-run on G17P (EXP-0168, 190 of 256 "
            "values moved)", group="cvt", oracle_rule="control")
        add(tag + "/mode", name, "cvt_f2i", "mode", off, ln, 16, 8, MODE_SET,
            "control", i, fv["mode"],
            "CONTROL: byte+2 is the result-routing/source-cache mode, "
            "hardware-run on M4 dense (EXP-0144)", group="cvt",
            oracle_rule="control")

sgn = [x for x in CVT if x[0] == "cvt_sgn"][0]
add("CVT/cvt_sgn#0/signflag", "cvt_sgn", "cvt_f2i", "signflag", sgn[2]["off"],
    sgn[2]["len"], 56, 8, range(256), "instruction_semantics", 0,
    sgn[2]["field_values"]["signflag"],
    "H8, the instruction-level claim. EXP-0013 established on M4/A18 that bit 6 "
    "(0x40) of byte+7 selects signed vs unsigned and never re-ran it on G17P. "
    "Lane 7 of this carrier's input is 2^31+2^8, outside int32's range, so a "
    "signed and an unsigned convert CANNOT agree there and the two hypotheses "
    "are separated by an observed-vs-observed comparison against the arm's own "
    "unmutated baseline.", group="cvt", oracle_rule="exact_iff_compiled")

doc = {"_generated_by": "analysis/gen_arms_b.py",
       "_census": "raw/prefreeze/census_b.json",
       "n_arms": len(ARMS),
       "n_cases": sum(len(a["values"]) for a in ARMS),
       "arms": ARMS}
p = EXP / "harness" / "arms202b.json"
p.write_text(json.dumps(doc, indent=1, sort_keys=True))
byg = {}
for a in ARMS:
    byg[a["group"]] = byg.get(a["group"], 0) + len(a["values"])
print("arms=%d cases=%d" % (doc["n_arms"], doc["n_cases"]))
print("per group:", byg)
print("wrote", p)
