#!/usr/bin/env python3
"""EXP-0138 case matrix: per-field sweeps of the float-ALU families.

Two execution modes (both HW-PROBE on the local M4, both proven in this
experiment's pilot, PROGRESS.md Milestone 1):

  MODE A  a fully hand-built program replaces the whole `_agc.main` of
          `kernels/carrier.metal` (or `carrier_uni.metal` for the uniform
          arm): seed r0..r12 with 13 distinct exact minifloat constants,
          execute ONE instruction under test, then store (a) the register
          the instruction should have written, (b) an untouched control
          register, (c) one of the source registers. Every operand is under
          our control, so a register-descriptor sweep has a real per-value
          oracle.

  MODE B  ONE instruction is spliced in place inside a compiled carrier from
          `kernels/probes.metal`, with its own load/store scaffolding intact.
          Used for the families whose operands cannot be seeded by hand
          (fp16 and the SFU/copysign forms).

ORACLE POLICY (pre-registered):
  * `predict` gives a host-computed expected value for EVERY case.
  * `expect_match=True`  -> a real pre-registered prediction. These are the
    cases that can support a `hardware-run` claim.
  * `expect_match=False` -> either a deliberate REFUTER (pre-registered to
    fail, so the method is shown to be able to see a difference) or an
    EXPLORATORY value for which no semantics were pre-registered; the
    prediction recorded is the null hypothesis "this field does not change
    the result", and a mismatch is the finding.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is introspected.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402

RD = H.reg_desc
SEED = H.SEED
D = 6                      # destination register for MODE A cases
R_CTL = 11                 # control register (26.0), must stay untouched
R_SRCA = 0                 # 5.0
R_SRCB = 2                 # 3.0
R_SRCC = 4                 # 7.0
A, Bv, C = SEED[0], SEED[2], SEED[4]           # 5.0, 3.0, 7.0
CTL = SEED[R_CTL]                               # 26.0

# uniform file contents bound at buffer(2) in the uniform arm; the pilot
# (PROGRESS.md M1.5) located them at uniform-register indices 6..9.
UNI_VALS = [101.0, 202.0, 303.0, 404.0]
UNI = {6: 101.0, 7: 202.0, 8: 303.0, 9: 404.0}

# MODE-B carriers: (kernel function, fast_math, offset, anchor bytes, input
# values, output words, decode). Offsets were pinned by byte search in the
# pilot; run.py re-verifies each anchor byte-for-byte before the first case.
MEM_F32 = [4.0, 3.0, 0.5, 7.0, 9.0, 11.0, 13.0, 0.25]
MEM_F32_CS = [5.0, -3.0, 0.5, 7.0, 9.0, 11.0, 13.0, 0.25]
MEM_F16 = [5.0, 3.0, 0.5, 7.0, 9.0, 11.0, 13.0, 0.25]
# the saturating/fma half carriers need operands whose result does NOT
# clamp, or every case would read back 1.0 and the sweep could not tell
# "field changed the operand" from "field did nothing".
MEM_F16S = [0.25, 0.5, 0.125, 0.0625, 0.375, 0.75, 0.1875, 0.03125]

CARRIERS_B = {
    "half_alu":       dict(src="probes.metal", fn="k_hadd",     fast=False, off=0x2a,
                           anchor="10041c0200c0", mem=MEM_F16, pack="<e", nout=8, dec="half"),
    "half_alu_ext8":  dict(src="probes.metal", fn="k_hsat",     fast=False, off=0x2a,
                           anchor="10041c0201000082", mem=MEM_F16S, pack="<e", nout=8, dec="half"),
    "half_alu_fma12": dict(src="probes.metal", fn="k_hfmaabs",  fast=False, off=0x42,
                           anchor="10041e058302000000800100", mem=MEM_F16S, pack="<e", nout=8, dec="half"),
    "copysign":       dict(src="probes.metal", fn="k_copysign", fast=False, off=0x30,
                           anchor="07c28800", mem=MEM_F32_CS, pack="<f", nout=16, dec="f32"),
    "fspecial":       dict(src="probes.metal", fn="k_rsqrtf",   fast=True,  off=0x12,
                           anchor="af0156020200b0400000", mem=MEM_F32, pack="<f", nout=16, dec="f32"),
    "fspecial_est":   dict(src="probes.metal", fn="k_rsqrtn",   fast=False, off=0x12,
                           anchor="1981250b00c2", mem=MEM_F32, pack="<f", nout=16, dec="f32"),
}


def _seed_prologue():
    return [H.mov_imm(H.R_IDX, 0)] + [H.seed(r, v) for r, v in sorted(SEED.items())]


def modeA(instr_bytes, dst_reg=D, extra_probe=None):
    """prologue + instruction + 3 readback stores + stop, padded to the
    carrier length by the caller (run.py knows the region length)."""
    body = _seed_prologue() + [instr_bytes,
                               H.store_word(0, dst_reg),
                               H.store_word(4, R_CTL),
                               H.store_word(8, R_SRCA)]
    if extra_probe is not None:
        body.append(H.store_word(12, extra_probe))
    body.append(H.stop())
    return body


def case(instr, field, value, mode, carrier, ib, oracle, expect_match,
         note="", dst_reg=D, extra_probe=None, group=None):
    return {"instr": instr, "field": field, "value": value, "mode": mode,
            "carrier": carrier, "instr_bytes": ib.hex(),
            "oracle": oracle, "expect_match": bool(expect_match),
            "note": note, "dst_reg": dst_reg, "extra_probe": extra_probe,
            "group": group or instr}


# ---------------------------------------------------------------------------
# value sets
# ---------------------------------------------------------------------------
def desc_sweep():
    """All 256 values of an 8-bit operand-descriptor byte."""
    return list(range(256))


REG7 = sorted(set(list(range(0, 16)) + [16, 24, 31, 32, 40, 48, 63, 64, 66, 67,
                                        95, 96, 112, 120, 125, 126, 127]))


def reg_value(v):
    """Predicted GPR content for a 7-bit register-field value, per EXP-0112's
    HW-VALIDATED aliasing rule: R resolves to r(R mod 64) for R in [64,112];
    126/127 fault the command buffer."""
    return SEED.get(v % 64, 0.0)


def desc_value(v):
    """Predicted GPR content for an 8-bit `(reg<<1)|is32` descriptor byte,
    with bit7 the HW-TESTED-INERT top bit (EXP-0099/0119)."""
    return SEED.get(((v >> 1) & 0x3F), 0.0)


# ---------------------------------------------------------------------------
# per-family anchors and pre-registered baselines (all from this experiment's
# own pilot, PROGRESS.md Milestone 1 / work/pilot/baselines.py, re-derived in
# every gated run by the family's own `_base` case).
# ---------------------------------------------------------------------------
BASE = {                       # (w0, w8 = r0 after the instruction)
    "falu2":           (8.0, 5.0),
    "falu2i":          (8.0, 5.0),
    "falu2_ext":       (8.0, 5.0),
    "falu2_srcmod10":  (8.0, 5.0),
    "falu_srcmod12b":  (8.0, 5.0),
    "falu3":          (22.0, 0.0),
    "falu3_ext":      (22.0, 0.0),
    "falu3_srcmod12": (22.0, 5.0),
    "falu_acc":        (8.0, 0.0),
}
FADD, FMUL = A + Bv, A * Bv                    # 8.0, 15.0
FMA = A * Bv + C                               # 22.0


def _bytes_of(field_sub, mk):
    return mk(**field_sub)


def byte_sweeps(nbytes, anchor_val):
    """For a wide tail field, sweep each constituent BYTE over 0..255 with the
    others held at their anchor value. A 32/48-bit field cannot be swept
    exhaustively; per-byte is what an emitter actually needs and it keeps the
    per-byte semantics separable."""
    out = []
    for bi in range(nbytes):
        for v in range(256):
            nv = (anchor_val & ~(0xFF << (8 * bi))) | (v << (8 * bi))
            out.append((bi, v, nv))
    return out


def build_cases():
    cs = []
    add = cs.append

    # =====================================================================
    # G1  falu2.mod_lo  -- PRIORITY 1. Runs in the UNIFORM carrier so the
    # pre-registered "reads the uniform register file" hypothesis is live.
    # H-MODLO (pre-registered, from this experiment's own pilot + EXP-M4-14's
    # A18 half_alu observation): mod_lo bit0 makes srcA read the UNIFORM
    # register file at the index in srcA_reg; bit1 makes srcB read it at the
    # index in srcB_reg; bit2 behaves like bit1. Uniform indices 6..9 hold
    # {101,202,303,404} (bound at buffer(2)); every other index reads 0.
    # =====================================================================
    def modlo_pred(v, sa_reg, sb_reg, op):
        a = UNI.get(sa_reg, 0.0) if (v & 1) else SEED.get(sa_reg, 0.0)
        b = UNI.get(sb_reg, 0.0) if (v & 6) else SEED.get(sb_reg, 0.0)
        return H.f32(a + b) if op == 4 else H.f32(a * b)

    for op in (4, 5):
        for sa, sb in ((0, 2), (0, 6), (6, 2), (0, 3)):
            for v in range(8):
                ib = H.falu2_raw(D, sa, sb, opsel=op, opflags5=0, mod_lo=v)
                pred = modlo_pred(v, sa, sb, op)
                add(case("falu2", "mod_lo", v, "A", "carrier_uni", ib,
                         {"w0": pred}, True,
                         note="H-MODLO srcA_reg=%d srcB_reg=%d opsel=%d" % (sa, sb, op),
                         group="G1_falu2_modlo"))
    # uniform-file map: mod_lo=2, srcB_reg swept over the whole 7-bit space
    for v in REG7:
        ib = H.falu2_raw(D, 0, v, opsel=4, opflags5=0, mod_lo=2)
        add(case("falu2", "mod_lo", 2, "A", "carrier_uni", ib,
                 {"w0": H.f32(A + UNI.get(v, 0.0))}, v not in (126, 127),
                 note="uniform-file index map, srcB_reg=%d" % v,
                 group="G1_falu2_unimap"))
    # REFUTER (pre-registered to differ from the anchor): mod_lo=2 with an
    # UNBOUND uniform index must NOT give the GPR answer 8.0.
    add(case("falu2", "mod_lo", 2, "A", "carrier_uni",
             H.falu2_raw(D, 0, 2, opsel=4, opflags5=0, mod_lo=2),
             {"w0": FADD}, False,
             note="REFUTER: predicted 5.0 (uniform[2] unbound), NOT the 8.0 anchor",
             group="G1_refuter"))

    # =====================================================================
    # G2  falu2i.imm_flag / ctrl_lo / mods
    # =====================================================================
    for v in (0, 1):
        ib = H.falu2i_raw(D, 0, 3.0, opflags4=0, imm_flag=v)
        add(case("falu2i", "imm_flag", v, "A", "carrier", ib,
                 {"w0": FADD if v == 1 else None}, v == 1,
                 note="anchor imm_flag=1 -> 5+3; 0 clears b1 bit0 (exploratory)",
                 group="G2_falu2i"))
    for v in range(128):
        ib = H.falu2i_raw(D, 0, 3.0, opflags4=0, ctrl_lo=v)
        add(case("falu2i", "ctrl_lo", v, "A", "carrier", ib,
                 {"w0": FADD}, (v & 3) == 0,
                 note="null hypothesis: inert. bits0/1 are the 0x09-group LENGTH selector (EXP-0119)",
                 group="G2_falu2i"))
    for v in range(256):
        ib = H.falu2i_raw(D, 0, 3.0, opflags4=0, mods=v)
        add(case("falu2i", "mods", v, "A", "carrier", ib,
                 {"w0": FADD}, False,
                 note="exploratory (mods was isolated-byte-diff at 0x00/0xC0 only)",
                 group="G2_falu2i"))

    # =====================================================================
    # G3/G4/G7/G8  the falu2-shaped families: falu2_ext (8B), falu2_srcmod10
    # (10B), falu3_srcmod12 (12B, 3-source), falu_srcmod12b (12B, 2-source).
    # Identical field layout, so one generator drives all four.
    # =====================================================================
    SHAPES = {
        "falu2_ext": dict(mk=H.falu2_ext_raw, tail="ext_tail", ntail=2,
                          tail_anchor=0x8000, opsel_ok=(4, 5), base=FADD,
                          kw=dict(opflags5=0, ext_tail=0x8000)),
        "falu2_srcmod10": dict(mk=H.falu2_srcmod10_raw, tail="ext_srcmod", ntail=4,
                               tail_anchor=0x00008000, opsel_ok=(4, 5), base=FADD,
                               kw=dict(opflags5=0)),
        "falu3_srcmod12": dict(mk=H.falu3_srcmod12_raw, tail="ext_srcmod", ntail=6,
                               tail_anchor=0x080000002, opsel_ok=(6,), base=FMA,
                               kw=dict(opflags5=0, opsel=6)),
        "falu_srcmod12b": dict(mk=H.falu_srcmod12b_raw, tail="ext_srcmod", ntail=6,
                               tail_anchor=0x000000008000, opsel_ok=(0,), base=FADD,
                               kw=dict(opflags5=0, opsel=0)),
    }
    for mn, S in SHAPES.items():
        mk, kw, base = S["mk"], S["kw"], S["base"]
        G = "G_" + mn

        def build(**over):
            f = dict(kw); f.update(over)
            return mk(f.pop("dst", D), f.pop("srcA_reg7", 0), f.pop("srcB_reg7", 2), **f)

        add(case(mn, "_baseline", 0, "A", "carrier", build(), {"w0": base}, True,
                 note="family anchor", group=G))
        # dst (4-bit): the result must appear in the register the field names.
        for v in range(16):
            add(case(mn, "dst", v, "A", "carrier", build(dst=v), {"w0": base}, True,
                     note="result read back from r%d" % v, dst_reg=v, group=G))
        # srcA_size / srcB_size (1 bit)
        for fld in ("srcA_size", "srcB_size"):
            for v in (0, 1):
                add(case(mn, fld, v, "A", "carrier", build(**{fld: v}),
                         {"w0": base if v == 1 else None}, v == 1,
                         note="1=32-bit (anchor); 0=16-bit read (exploratory)", group=G))
        # srcA_reg / srcB_reg (7 bits)
        for fld, other in (("srcA_reg7", "srcB"), ("srcB_reg7", "srcA")):
            name = "srcA_reg" if fld.startswith("srcA") else "srcB_reg"
            for v in REG7:
                a = reg_value(v) if name == "srcA_reg" else A
                b = reg_value(v) if name == "srcB_reg" else Bv
                if mn == "falu3_srcmod12":
                    pred = H.f32(a * b + C)
                else:
                    pred = H.f32(a * b) if kw.get("opsel") == 5 else H.f32(a + b)
                add(case(mn, name, v, "A", "carrier", build(**{fld: v}),
                         {"w0": pred}, v not in (126, 127),
                         note="EXP-0112 aliasing rule r(R mod 64); 126/127 predicted to FAULT",
                         group=G))
        # opsel (3 bits)
        for v in range(8):
            if mn == "falu_srcmod12b" and v == 4:
                continue       # EXP-0119: corrupts an unrelated register. NOT swept.
            pred = {4: FADD, 5: FMUL, 6: FMA, 0: FADD}.get(v)
            add(case(mn, "opsel", v, "A", "carrier", build(opsel=v),
                     {"w0": pred}, v in S["opsel_ok"],
                     note="db enum 4=fadd 5=fmul 6=fma; others exploratory", group=G))
        # opflags (5 bits) -- bit19 release srcA, bit20 release srcB, bit21 publish
        for v in range(32):
            add(case(mn, "opflags", v, "A", "carrier", build(opflags5=v),
                     {"w0": base}, v in (0, 1, 2, 3),
                     note="EXP-0086/0099: bits19/20 release sources (own result unaffected), "
                          "bits22/23 silent corruptors", group=G))
        # ctrl (7 bits): bits0/1 ARE the length selector for this group
        anchor_ctrl = {"falu2_ext": 1, "falu2_srcmod10": 2,
                       "falu3_srcmod12": 3, "falu_srcmod12b": 3}[mn]
        for v in range(128):
            add(case(mn, "ctrl", v, "A", "carrier", build(ctrl=v),
                     {"w0": base}, (v & 3) == anchor_ctrl,
                     note="bits0/1 = 0x09-group LENGTH selector (anchor %d)" % anchor_ctrl,
                     group=G))
        # srcB_imm (1 bit)
        anchor_bimm = 1 if mn == "falu3_srcmod12" else 0
        for v in (0, 1):
            add(case(mn, "srcB_imm", v, "A", "carrier", build(srcB_imm=v),
                     {"w0": base}, v == anchor_bimm, note="anchor=%d" % anchor_bimm, group=G))
        # mod_lo (3 bits) -- H-MODLO, run in the UNIFORM carrier
        for v in range(8):
            a = 0.0 if (v & 1) else A            # uniform[0] is unbound
            b = 0.0 if (v & 6) else Bv           # uniform[2] is unbound
            pred = H.f32(a * b + C) if mn == "falu3_srcmod12" else H.f32(a + b)
            add(case(mn, "mod_lo", v, "A", "carrier_uni", build(mod_lo=v),
                     {"w0": pred}, True, note="H-MODLO uniform-source hypothesis", group=G))
        # srcB_neg (1 bit)
        anchor_neg = 1 if mn == "falu3_srcmod12" else 0
        for v in (0, 1):
            if mn == "falu3_srcmod12":
                pred = H.f32(A * Bv + C) if v == 1 else None
            else:
                pred = H.f32(A - Bv) if v == 1 else FADD
            add(case(mn, "srcB_neg", v, "A", "carrier", build(srcB_neg=v),
                     {"w0": pred}, pred is not None,
                     note="1 = negate srcB (HW-VALIDATED on falu2, EXP-M4-10)", group=G))
        # mod_hi (4 bits): EXP-0105 found falu2 bit44 a silent corruptor
        for v in range(16):
            add(case(mn, "mod_hi", v, "A", "carrier", build(mod_hi=v),
                     {"w0": 0.0 if (v & 1) else base}, True,
                     note="H: bit44 (value bit0) silently corrupts to 0 (EXP-0105 on falu2)",
                     group=G))
        # the wide tail, byte by byte
        for bi, v, nv in byte_sweeps(S["ntail"], S["tail_anchor"]):
            add(case(mn, S["tail"], nv, "A", "carrier", build(**{S["tail"]: nv}),
                     {"w0": base}, False,
                     note="tail byte+%d = 0x%02x (exploratory; null hypothesis inert)" % (6 + bi, v),
                     group=G))
    return cs


def build_cases_2():
    """falu3 / falu3_ext / falu_acc (MODE A) and every MODE-B family."""
    cs = []
    add = cs.append

    # =====================================================================
    # G5/G6  falu3 (8B) and falu3_ext (10B).
    # H-FALU3-LAYOUT (pre-registered, from this experiment's own anchor
    # analysis): db.json's field NAMES for this family are off by one slot.
    # By falu2-family analogy and the `k_fma` anchor `09 01 1e 05 81 08 02 c0`
    # (fma(a0,a1,a2) with a0=r0,a1=r2,a2=r4), the real roles are
    #   byte0 high nibble (`dst_lo`) = DESTINATION
    #   byte+1 (`dst`)               = first source descriptor
    #   byte+3 (`srcA`)              = second source descriptor
    #   byte+4 (`srcB`)              = a control byte whose low 2 bits are the
    #                                  0x09-group LENGTH selector
    #   byte+5 (`srcC`)              = third source descriptor
    # Each is tested by a dense 0..255 sweep with a per-value oracle.
    # =====================================================================
    F3 = {"falu3": dict(mk=H.falu3_raw, b4=0x81, tailname="ctrl", ntail=1,
                        tail_anchor=0x02, extra=("srcmods", 0xC0)),
          "falu3_ext": dict(mk=H.falu3_ext_raw, b4=0x82, tailname="ext", ntail=4,
                            tail_anchor=0x80000002, extra=None)}
    for mn, S in F3.items():
        G = "G_" + mn
        mk, b4 = S["mk"], S["b4"]

        def build(dst_lo=D, dst=RD(0), op=0x1e, srcA=RD(2), srcB=b4, srcC=RD(4, 0), **kw):
            if mn == "falu3":
                return mk(dst_lo, dst, op, srcA, srcB, srcC,
                          ctrl=kw.get("ctrl", 0x02), srcmods=kw.get("srcmods", 0x00))
            return mk(dst_lo, dst, op, srcA, srcB, srcC, ext=kw.get("ext", 0x80000002))

        add(case(mn, "_baseline", 0, "A", "carrier", build(), {"w0": FMA}, True,
                 note="family anchor (srcmods/ext at the non-saturating value)", group=G))
        for v in range(16):
            add(case(mn, "dst_lo", v, "A", "carrier", build(dst_lo=v), {"w0": FMA}, True,
                     note="H-FALU3-LAYOUT: byte0 high nibble is the DESTINATION",
                     dst_reg=v, group=G))
        for v in range(256):
            add(case(mn, "dst", v, "A", "carrier", build(dst=v),
                     {"w0": H.f32(desc_value(v) * Bv + C)}, True,
                     note="H-FALU3-LAYOUT: byte+1 is the FIRST SOURCE descriptor", group=G))
        for v in range(256):
            add(case(mn, "op", v, "A", "carrier", build(op=v), {"w0": FMA}, v == 0x1e,
                     note="opcode byte+2 (exploratory away from the 0x1e anchor)", group=G))
        for v in range(256):
            add(case(mn, "srcA", v, "A", "carrier", build(srcA=v),
                     {"w0": H.f32(A * desc_value(v) + C)}, True,
                     note="H-FALU3-LAYOUT: byte+3 is the SECOND SOURCE descriptor", group=G))
        for v in range(256):
            add(case(mn, "srcB", v, "A", "carrier", build(srcB=v), {"w0": FMA},
                     (v & 3) == (b4 & 3),
                     note="H-FALU3-LAYOUT: byte+4 is a CONTROL byte; low 2 bits are the "
                          "0x09-group LENGTH selector, so most values re-length the op", group=G))
        for v in range(256):
            add(case(mn, "srcC", v, "A", "carrier", build(srcC=v),
                     {"w0": H.f32(A * Bv + desc_value(v))}, True,
                     note="H-FALU3-LAYOUT: byte+5 is the THIRD SOURCE descriptor", group=G))
        if mn == "falu3":
            for v in range(256):
                add(case(mn, "ctrl", v, "A", "carrier", build(ctrl=v), {"w0": FMA}, v == 0x02,
                         note="byte+6 (exploratory)", group=G))
            for v in range(256):
                pred = H.f32(-(A * Bv) + C) if (v & 0x08) else FMA
                add(case(mn, "srcmods", v, "A", "carrier", build(srcmods=v),
                         {"w0": pred}, False,
                         note="H: bit3 negates the a*b product (EXP-M4-13 own-MSL byte-diff)",
                         group=G))
        else:
            for bi, v, nv in byte_sweeps(4, 0x80000002):
                pred = H.f32(min(FMA, 1.0)) if (bi == 3 and (v & 0x02)) else FMA
                add(case(mn, "ext", nv, "A", "carrier", build(ext=nv), {"w0": pred}, False,
                         note="tail byte+%d = 0x%02x; H: byte+9 bit1 = saturate, bit7 = op-valid"
                              % (6 + bi, v), group=G))

    # =====================================================================
    # G9  falu_acc (4B compact accumulate)
    # =====================================================================
    G = "G_falu_acc"
    add(case("falu_acc", "_baseline", 0, "A", "carrier",
             H.falu_acc_raw(D, RD(0), RD(2), op=0), {"w0": FADD}, True,
             note="family anchor", group=G))
    for v in range(16):
        add(case("falu_acc", "dst", v, "A", "carrier",
                 H.falu_acc_raw(v, RD(0), RD(2), op=0), {"w0": FADD}, True,
                 note="byte0 high nibble = destination", dst_reg=v, group=G))
    for v in range(256):
        add(case("falu_acc", "srcA", v, "A", "carrier",
                 H.falu_acc_raw(D, v, RD(2), op=0),
                 {"w0": H.f32(desc_value(v) + Bv)}, True,
                 note="byte+1 first source descriptor", group=G))
    for v in range(256):
        add(case("falu_acc", "srcB", v, "A", "carrier",
                 H.falu_acc_raw(D, RD(0), v, op=0),
                 {"w0": H.f32(A + desc_value(v))}, True,
                 note="byte+3 second source descriptor", group=G))
    for v in (0, 1):
        add(case("falu_acc", "op", v, "A", "carrier",
                 H.falu_acc_raw(D, RD(0), RD(2), op=v),
                 {"w0": FADD if v == 0 else FMUL}, True,
                 note="db enum 0=fadd_acc 1=fmul_acc", group=G))
    return cs


# ---------------------------------------------------------------------------
# MODE-B live-operand tables. `desc -> value` for each carrier, read off the
# carrier's own compiled anchor + its device_load extmodes (pilot M1.6).
# ---------------------------------------------------------------------------
LIVE = {
    "half_alu":       {0x04: MEM_F16[0], 0x02: MEM_F16[1]},
    "half_alu_ext8":  {0x04: MEM_F16S[0], 0x02: MEM_F16S[1]},
    "half_alu_fma12": {0x04: MEM_F16S[0], 0x05: MEM_F16S[1], 0x02: MEM_F16S[2]},
}


def build_cases_3():
    """MODE-B families (fp16, copysign, SFU) + the falu2_uni uniform arm."""
    cs = []
    add = cs.append

    def caseB(instr, field, value, ib, oracle, expect, note, group=None):
        return case(instr, field, value, "B", instr, ib, oracle, expect,
                    note=note, group=group or ("GB_" + instr))

    # ---------------- copysign (4B) -------------------------------------
    CS_BASE = H.f32(abs(MEM_F32_CS[0]) * (-1.0 if MEM_F32_CS[1] < 0 else 1.0))   # -5.0
    anchor = bytes.fromhex("07c28800")
    add(caseB("copysign", "_baseline", 0, anchor, {"o0": CS_BASE}, True, "family anchor"))
    for v in range(256):
        add(caseB("copysign", "operands", v, anchor[:3] + bytes([v]),
                  {"o0": CS_BASE}, False,
                  "byte+3 operand descriptor; null hypothesis = inert"))
    # FALSIFIER / structure probe: byte+1 and byte+2 are db MATCH constants,
    # not fields. At least one value here MUST change the output, or the whole
    # copysign arm proves nothing about the method's sensitivity.
    for bi, base in ((1, 0xC2), (2, 0x88)):
        for v in range(256):
            b = bytearray(anchor); b[bi] = v
            add(caseB("copysign", "_match_b%d" % bi, v, bytes(b), {"o0": CS_BASE}, False,
                      "FALSIFIER/structure: db models byte+%d as a fixed match constant" % bi,
                      group="GB_copysign_falsifier"))

    # ---------------- half_alu (6B) --------------------------------------
    ha = bytes.fromhex("10041c0200c0")
    hb = LIVE["half_alu"]
    HA_BASE = H.f32(hb[0x04] + hb[0x02])
    add(caseB("half_alu", "_baseline", 0, ha, {"o0": HA_BASE}, True, "family anchor"))
    for v in range(256):
        b = bytearray(ha); b[1] = v
        add(caseB("half_alu", "dst", v, bytes(b),
                  {"o0": H.f32(hb.get(v, 0.0) + hb[0x02])}, True,
                  "H-HALF-LAYOUT: byte+1 is the FIRST SOURCE descriptor, not dst "
                  "(the destination is byte0's high nibble, exactly as in falu2)"))
    for v in range(32):
        b = bytearray(ha); b[2] = (ha[2] & 0x07) | (v << 3)
        add(caseB("half_alu", "opflags", v, bytes(b), {"o0": HA_BASE}, v in (0, 1, 2, 3),
                  "bits19..23; falu2's contract is bit19/20 = release source"))
    for v in range(16):
        b = bytearray(ha); b[0] = (v << 4) | 0x00
        add(caseB("half_alu", "_byte0_hi", v, bytes(b), {"o0": HA_BASE}, v == 1,
                  "db models byte0 as a FIXED 0x10 match; H-HALF-LAYOUT says its high "
                  "nibble is the destination register (anchor value 1)",
                  group="GB_half_alu_byte0"))

    # ---------------- half_alu_ext8 (8B) ---------------------------------
    he = bytes.fromhex("10041c0201000082")
    hbe = LIVE["half_alu_ext8"]
    HE_BASE = H.f32(min(hbe[0x04] + hbe[0x02], 1.0))
    add(caseB("half_alu_ext8", "_baseline", 0, he, {"o0": HE_BASE}, True, "family anchor"))
    for v in range(256):
        b = bytearray(he); b[1] = v
        add(caseB("half_alu_ext8", "dst", v, bytes(b),
                  {"o0": H.f32(min(hbe.get(v, 0.0) + hbe[0x02], 1.0))}, True,
                  "H-HALF-LAYOUT: byte+1 = first source descriptor"))
    for v in range(32):
        b = bytearray(he); b[2] = (he[2] & 0x07) | (v << 3)
        add(caseB("half_alu_ext8", "opflags", v, bytes(b), {"o0": HE_BASE}, v in (0, 1, 2, 3),
                  "bits19..23"))
    for v in (0, 1):
        b = bytearray(he); b[7] = (he[7] & ~0x01) | v
        add(caseB("half_alu_ext8", "b7_lo", v, bytes(b), {"o0": HE_BASE}, v == 0,
                  "byte+7 bit0"))
    for v in range(32):
        b = bytearray(he); b[7] = (he[7] & ~0x7C) | ((v & 0x1F) << 2)
        add(caseB("half_alu_ext8", "b7_mid", v, bytes(b), {"o0": HE_BASE}, v == 0,
                  "byte+7 bits2..6"))

    # ---------------- half_alu_fma12 (12B) -------------------------------
    # emit_unsafe: its length over-consumes the following leader, so the
    # trailing `ext` field is NOT swept (a sweep there would really be
    # sweeping the next instruction). Only the two leading-parcel fields.
    hf = bytes.fromhex("10041e058302000000800100")
    hbf = LIVE["half_alu_fma12"]
    HF_BASE = H.f32(abs(hbf[0x04]) * hbf[0x05] + hbf[0x02])
    add(caseB("half_alu_fma12", "_baseline", 0, hf, {"o0": HF_BASE}, True, "family anchor"))
    for v in range(256):
        b = bytearray(hf); b[1] = v
        add(caseB("half_alu_fma12", "dst", v, bytes(b),
                  {"o0": H.f32(abs(hbf.get(v, 0.0)) * hbf[0x05] + hbf[0x02])}, True,
                  "H-HALF-LAYOUT: byte+1 = first source descriptor"))
    for v in range(32):
        b = bytearray(hf); b[2] = (hf[2] & 0x07) | (v << 3)
        add(caseB("half_alu_fma12", "opflags", v, bytes(b), {"o0": HF_BASE}, v in (0, 1, 2, 3),
                  "bits19..23"))

    # ---------------- fspecial (10B, fast-math single SFU op) ------------
    fs = bytes.fromhex("af0156020200b0400000")
    X = MEM_F32[0]                                   # 4.0
    import math
    FN_MAP = {(1, 1): 1.0 / math.sqrt(X), (1, 0): 1.0 / X, (1, 2): 2.0 ** X,
              (0, 0): math.floor(X), (0, 1): math.sqrt(X), (0, 2): math.log2(X)}
    FS_BASE = H.f32(FN_MAP[(1, 1)])
    add(caseB("fspecial", "_baseline", 0, fs, {"o0": FS_BASE}, True, "family anchor rsqrt(4)=0.5"))
    for v in (0, 1):
        b = bytearray(fs); b[0] = (fs[0] & 0x7F) | (v << 7)
        pred = FN_MAP.get((v, 1))
        add(caseB("fspecial", "fn_hi", v, bytes(b),
                  {"o0": H.f32(pred) if pred is not None else FS_BASE},
                  (v, 1) in FN_MAP,
                  "0=direct(sqrt/log2/round) 1=reciprocal(rcp/rsqrt/exp2)"))
    for v in range(16):
        b = bytearray(fs); b[1] = (fs[1] & 0xF0) | v
        pred = FN_MAP.get((1, v))
        add(caseB("fspecial", "fnclass", v, bytes(b),
                  {"o0": H.f32(pred) if pred is not None else FS_BASE},
                  (1, v) in FN_MAP and v in (1, 2),
                  "function select; the anchor's fnsel/precsel is the std-f32 datapath, "
                  "so only the classes that share it are pre-registered"))
    for v in range(16):
        b = bytearray(fs); b[1] = (fs[1] & 0x0F) | (v << 4)
        add(caseB("fspecial", "dst", v, bytes(b), {"o0": FS_BASE}, v == 0,
                  "byte+1 high nibble = destination GPR; only dst=0 is read back "
                  "by the carrier's own store"))
    for name, bi in (("src_cache", 2), ("src", 3), ("src_class", 4), ("src_ext", 5),
                     ("fnsel", 6), ("precsel", 7), ("roundmode", 8), ("sched_flag", 9)):
        for v in range(256):
            b = bytearray(fs); b[bi] = v
            add(caseB("fspecial", name, v, bytes(b), {"o0": FS_BASE}, v == fs[bi],
                      "byte+%d; null hypothesis = inert away from the anchor value 0x%02x"
                      % (bi, fs[bi])))

    # ---------------- fspecial_est (6B) ----------------------------------
    fe = bytes.fromhex("1981250b00c2")
    FE_BASE = H.f32(1.0 / math.sqrt(X))
    add(caseB("fspecial_est", "_baseline", 0, fe, {"o0": FE_BASE}, True,
              "family anchor: the NR seed inside a full no-fast-math rsqrt(4)"))
    for v in range(16):
        b = bytearray(fe); b[0] = (fe[0] & 0x0F) | (v << 4)
        add(caseB("fspecial_est", "dst", v, bytes(b), {"o0": FE_BASE}, v == 1,
                  "byte0 high nibble = destination (anchor r1)"))
    for name, bi in (("srcA", 1), ("subop", 3), ("b4", 4), ("b5", 5)):
        for v in range(256):
            b = bytearray(fe); b[bi] = v
            add(caseB("fspecial_est", name, v, bytes(b), {"o0": FE_BASE}, v == fe[bi],
                      "byte+%d; null hypothesis = inert away from the anchor value 0x%02x"
                      % (bi, fe[bi])))

    # ---------------- falu2_uni (6B, MODE A in the uniform carrier) ------
    # No compiler-emitted anchor exists (pilot round 4 hunted one across 42
    # kernels and found only a MIS-TOKENIZED instance). Constructed from
    # db.json's own descriptor: srcA = the never-written r14 (0.0), so the
    # result is the uniform operand alone.
    for v in REG7:
        ib = isa_uni(v)
        add(case("falu2_uni", "usrc", v, "A", "carrier_uni", ib,
                 {"w0": UNI.get(v, 0.0)}, v not in (126, 127),
                 note="constructed falu2_uni; predicted = uniform file at index v "
                      "(6..9 hold 101/202/303/404)", group="G_falu2_uni"))
    for name, rng in (("dst", range(16)), ("opsel", range(8)), ("opflags", range(32)),
                      ("srcA_size", (0, 1)), ("ctrl_lo", range(128)), ("mods", range(256))):
        for v in rng:
            kw = {name: v}
            ib = isa_uni(6, **kw)
            add(case("falu2_uni", name, v, "A", "carrier_uni", ib,
                     {"w0": UNI[6]}, name == "dst",
                     note="constructed falu2_uni, usrc=6 (uniform 101.0)",
                     dst_reg=(v if name == "dst" else D), group="G_falu2_uni"))
    for v in REG7:
        ib = isa_uni(6, srcA_reg=v)
        add(case("falu2_uni", "srcA_reg", v, "A", "carrier_uni", ib,
                 {"w0": H.f32(UNI[6] + reg_value(v))}, v not in (126, 127),
                 note="srcA is the GPR operand added to the uniform", group="G_falu2_uni"))
    return cs


def isa_uni(usrc, dst=D, opsel=4, opflags=0, srcA_size=1, srcA_reg=14,
            ctrl_lo=0, mods=0xC0):
    import isadb
    return isadb.assemble("falu2_uni", {
        "dst": dst & 0xF, "usrc": usrc & 0xFF, "opsel": opsel & 0x7,
        "opflags": opflags & 0x1F, "srcA_size": srcA_size & 1,
        "srcA_reg": srcA_reg & 0x7F, "ctrl_lo": ctrl_lo & 0x7F,
        "uni_mode": 1, "mods": mods & 0xFF,
    })


def all_cases():
    cs = build_cases() + build_cases_2() + build_cases_3()
    for i, c in enumerate(cs):
        c["i"] = i
    return cs
