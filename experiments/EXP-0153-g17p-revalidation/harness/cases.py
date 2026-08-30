#!/usr/bin/env python3
"""EXP-0153 case matrix: the seven revalidation arms, declared once.

Each arm re-runs, on **G17P**, a specific load-bearing claim established on
**M4/G16G**, using the SAME carrier, the SAME input vectors and the SAME
construction as the M4 experiment, so that a disagreement can only be the
hardware (or the G17P compiler's carrier layout, which is measured, not
assumed).

  A  device_load destination rule ....................... EXP-0141 (synth)
  B  falu2 source-class model + inline float immediate .. EXP-0138 (uni)
  C  native 64-bit integer ADD ......................... EXP-0146 (u64)
  D  register-file model (aliasing / fault bound) ....... EXP-0112 + EXP-0139
  E  ibfe offset LITERAL vs width mod-32 ................ EXP-0139 (bfe, shr)
  F  mov_imm is 7-bit; imm_top=1 does not write ......... EXP-0140 (uni)
  G  instruction-length rule corrections (corpus) ....... EXP-0148 (desk-side,
                                                          analysis/tokenize_corpus.py)

Two case kinds:

* `synth`  -- a COMPLETE hand-assembled AGX program (`isadb.assemble()` only,
  never a captured byte string) spliced over the carrier's compiled
  `_agc.main`. CODEX step 3's strongest level: an independently generated
  encoding executed on hardware.
* `splice` -- a single located instruction inside one of our own compiled MSL
  carriers has ONE field changed. Used where the operand plumbing is itself
  what is under test (arms C and E).

Oracles are host-computed in `carriers.py` / here, never read off a GPU run.
Every arm carries at least one pre-registered falsifier (`expect_match=False`).

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is introspected.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
import carriers as C  # noqa: E402
import anchors as A  # noqa: E402
import isadb  # noqa: E402

M32 = C.M32
M64 = C.M64

# ---------------------------------------------------------------------------
# shared register plan
# ---------------------------------------------------------------------------
SLOT_OUT, SLOT_MEM = 0, 1

# --- arm A (synth carrier), EXP-0141 verbatim -------------------------------
V_LOAD = C.MEM_F32[1]                  # -8.5
K_SMALL = H.imm_value(1.5)             # 1.5 exactly
ALU_ORACLE = {0: [V_LOAD + K_SMALL, None, None, None, 8.0]}   # out0 = -7.0, canary out4
D_ALU = 8                              # falu2i dst
D_CAN = 10                             # canary register
CANARY_VALUE = 8.0

# --- arms B / D-falu2 / F (uni carrier), EXP-0138 verbatim ------------------
D_B = 6                                # destination for the instruction under test
R_CTL = 11                             # control register (26.0), never written
R_SRCA = 0                             # 5.0
SEED_A = H.SEED[R_SRCA]                # 5.0
SEED_CTL = H.SEED[R_CTL]               # 26.0
UNI_M4 = {6: 101.0, 7: 202.0, 8: 303.0, 9: 404.0}   # M4 uniform-index map (a PREDICTION here)

# --- arm D-iadd2 (dag carrier), EXP-0139 verbatim ---------------------------
DAG_SENTINEL_REG = 13
DAG_R_IDX = 15
DAG_R_DST = 6
DAG_IADD_N = 2
DAG_SEED = {0: 10, 1: 21, 2: 22, 3: 23, 4: 24, 5: 25, 6: 99,
            7: 27, 8: 28, 9: 29, 10: 30, 11: 31, 12: 32, 13: 33, 14: 34, 15: 0}
DAG_R6_SENTINEL = DAG_SEED[DAG_R_DST]          # 99: iadd2 wrote somewhere else
DAG_BASE_SUM = DAG_SEED[0] + DAG_SEED[DAG_IADD_N]     # 32
IADD2_SRCA_R0_FIXED = 0xA8    # HW-VALIDATED byte+7 constant (EXP-0139 M1)
IADD2_BASE_FIELDS = dict(addsub=1, lenbit=1, srcB_reg_hi=0, b2_bit0=0,
                         store_en=1, b2_fmt=0x15, dst=(DAG_R_DST << 1),
                         opmode=2, srcB_imm=4 * DAG_IADD_N, srcB_imm_hi=0,
                         srcB_ext=0, srcA=IADD2_SRCA_R0_FIXED,
                         opc_tail=0x17, opc_tail2=5)

# --- arm F (uni carrier read as u32), EXP-0140 verbatim ---------------------
F_POISON = 7                # every GPR pre-seeded to this before a MOV test
F_D = 6                     # destination under test
F_CTL = 5                   # control register, must stay F_POISON
F_SENT_REG = 12             # sentinel register, written by falu2i (NOT mov_imm)
F_SENT_VAL = 26.0
F_SENT_BITS = 0x41D00000    # f32 bits of 26.0
F_TESTVAL = 99

REG7 = list(range(128))


# ===========================================================================
# helpers shared by every arm
# ===========================================================================
def _case(arm, carrier, instr, field, value, note="", oracle=None,
          expect_match=None, kind="synth", prog=None, splice=None, ibytes="",
          dtype=None, roundtrip=False):
    c = {"arm": arm, "carrier": carrier, "instr": instr, "field": field,
         "value": value, "note": note, "oracle": oracle,
         "expect_match": expect_match, "kind": kind, "ibytes": ibytes,
         "dtype": dtype}
    if kind == "synth":
        # CODEX step 10 round trip, RECORDED per case rather than asserted: a
        # swept value may legitimately re-tokenize the instruction, and the
        # hardware -- not tools/agx-isa -- is the authority on what bytes mean.
        try:
            H.assert_round_trip(prog)
            c["rt"] = True
        except AssertionError:
            c["rt"] = False
        if roundtrip and not c["rt"]:
            raise AssertionError("control case %s/%s failed round trip" % (arm, field))
        c["prog"] = prog.hex()
    else:
        c["splice"] = [[off, b.hex()] for off, b in splice]
    return c


# ===========================================================================
# ARM A -- device_load destination (EXP-0141)
# ===========================================================================
def _canary(idx):
    """EXP-0141's integrity sentinel: out[4] = 8.0, written BEFORE the
    instruction under test and through a path (mov_imm + falu2i + store) that
    does not involve device_load at all."""
    return [H.mov_imm(idx, 0),
            H.falu2i_raw(D_CAN, idx, CANARY_VALUE, mods=0),
            H.device_store(idx, SLOT_OUT, data_reg=D_CAN, idx_off=1)]


def prog_alu(mainlen, R=7, dst_lo=1, dst_ext9=1, extmode=None, ld=None, st=None,
             D=D_ALU):
    """canary; device_load -> r{R}; falu2i(D = r{R} + 1.5); store out[0] = D.
    out[0] == -7.0 iff the load landed in r{R}."""
    ld = dict(ld or {})
    st = dict(st or {})
    idx = H.pick_idx_reg(R, D, D_CAN)
    lkw = dict(index_reg=idx, base_slot=SLOT_MEM,
               extmode=2 * R if extmode is None else extmode,
               dst_lo=dst_lo, dst_ext9=dst_ext9, idx_off=1)
    lkw.update(ld)
    skw = dict(index_reg=idx, base_slot=SLOT_OUT, data_reg=D, idx_off=0)
    skw.update(st)
    load = H.device_load(**lkw)
    store = H.device_store(**skw)
    body = _canary(idx) + [load, H.falu2i_raw(D, R, 1.5), store]
    return H.build_program(body, mainlen), load, store


def arm_A(mainlen):
    arms = []
    ctl = []
    p, ld, _ = prog_alu(mainlen, R=7)
    ctl.append(_case("A_CTRL", "synth", "device_load", "_baseline", 0,
                     "EXP-0141's HW-VALIDATED M4 construction, unmutated. "
                     "M4: out0 == -7.0.", ALU_ORACLE, True, "synth", p,
                     ibytes=ld.hex(), roundtrip=True))
    p, ld, _ = prog_alu(mainlen, R=7, dst_lo=0, dst_ext9=0)
    ctl.append(_case("A_CTRL", "synth", "device_load", "_falsifier_dst00", 0,
                     "PRE-REGISTERED TO FAIL: on M4 (0,0) breaks the load "
                     "(silent zero -> out0 == 1.5).",
                     ALU_ORACLE, False, "synth", p, ibytes=ld.hex()))
    p, ld, _ = prog_alu(mainlen, R=7, extmode=0)
    ctl.append(_case("A_CTRL", "synth", "device_load", "_falsifier_extmode0", 0,
                     "PRE-REGISTERED TO FAIL: extmode=0 targets r0 while the "
                     "consumer reads r7.", ALU_ORACLE, False, "synth", p,
                     ibytes=ld.hex()))
    arms.append({"arm": "A_CTRL", "carrier": "synth", "instr": "device_load",
                 "field": "_controls", "cases": ctl,
                 "doc": "Baseline + two pre-registered falsifiers for arm A."})

    # A1/A2 -- dst_lo and dst_ext9, exhaustive, at two independent targets
    for R in (7, 20):
        cases = []
        for v in range(4):
            prog, load, _ = prog_alu(mainlen, R=R, dst_lo=v, dst_ext9=1)
            cases.append(_case("A_dst_lo_R%d" % R, "synth", "device_load",
                               "dst_lo", v,
                               "dst_ext9 held at 1, target r%d. M4: only v==1 works."
                               % R, ALU_ORACLE, (v == 1), "synth", prog,
                               ibytes=load.hex()))
        arms.append({"arm": "A_dst_lo_R%d" % R, "carrier": "synth",
                     "instr": "device_load", "field": "dst_lo", "cases": cases,
                     "doc": "dst_lo 0..3 EXHAUSTIVE at target r%d." % R})
        cases = []
        for v in range(128):
            prog, load, _ = prog_alu(mainlen, R=R, dst_lo=1, dst_ext9=v)
            cases.append(_case("A_dst_ext9_R%d" % R, "synth", "device_load",
                               "dst_ext9", v,
                               "dst_lo held at 1, target r%d. M4 rule: v & 1 == 1."
                               % R, ALU_ORACLE, bool(v & 1), "synth", prog,
                               ibytes=load.hex()))
        arms.append({"arm": "A_dst_ext9_R%d" % R, "carrier": "synth",
                     "instr": "device_load", "field": "dst_ext9", "cases": cases,
                     "doc": "dst_ext9 0..127 EXHAUSTIVE at target r%d." % R})

    # A3 -- the full 2-D product, the case that killed "the pair encodes R"
    cases = []
    for lo in range(4):
        for e9 in range(128):
            prog, load, _ = prog_alu(mainlen, R=7, dst_lo=lo, dst_ext9=e9)
            cases.append(_case("A_dst_pair", "synth", "device_load", "dst_pair",
                               (lo << 7) | e9, "dst_lo=%d dst_ext9=%d" % (lo, e9),
                               ALU_ORACLE, (lo == 1 and bool(e9 & 1)), "synth",
                               prog, ibytes=load.hex()))
    arms.append({"arm": "A_dst_pair", "carrier": "synth", "instr": "device_load",
                 "field": "dst_pair", "cases": cases,
                 "doc": "FULL 2-D (dst_lo, dst_ext9) product, all 512 encodable "
                        "combinations at r7. M4: exactly 64 accepted, "
                        "v & 0x181 == 0x81."})

    # A4 -- extmode dense, each value paired with a consumer reading r(v>>1).
    # This is the R-reachability test: M4 says R in 0..63 only, R >= 64 zeroes.
    cases = []
    for v in range(256):
        R = v >> 1
        prog, load, _ = prog_alu(mainlen, R=R, extmode=v)
        cases.append(_case("A_extmode", "synth", "device_load", "extmode", v,
                           "consumer srcA_reg = r%d. M4: works iff v < 128." % R,
                           ALU_ORACLE, v < 128, "synth", prog, ibytes=load.hex()))
    arms.append({"arm": "A_extmode", "carrier": "synth", "instr": "device_load",
                 "field": "extmode", "cases": cases,
                 "doc": "extmode 0..255 DENSE, each paired with a consumer that "
                        "reads r(extmode>>1). Tests extmode = 2*R over the whole "
                        "8-bit field, including odd values (bit 0 don't-care on "
                        "M4) and the R >= 64 region (silent zero on M4)."})
    return arms


# ===========================================================================
# ARM B / D-falu2 / F -- MODE-A programs in the uniform carrier (EXP-0138)
# ===========================================================================
def modeA(mainlen, instr_bytes, dst_reg=D_B, pre=None, post=None):
    """seed r0..r12 (falu2i from the never-written r14); write the SENTINEL
    out[12] = r11 BEFORE the instruction under test; run the instruction;
    read back out[0] = r{dst}, out[4] = r11 (control), out[8] = r0."""
    body = [H.mov_imm(H.R_IDX, 0)]
    body += [H.seed(r, v) for r, v in sorted(H.SEED.items())]
    body += [H.store_word(12, R_CTL)]            # sentinel, pre-test
    body += list(pre or [])
    body += [instr_bytes]
    body += list(post or [])
    body += [H.store_word(0, dst_reg),
             H.store_word(4, R_CTL),
             H.store_word(8, R_SRCA)]
    return H.build_program(body, mainlen)


def _uni_oracle(w0):
    """out[0] = w0 (None = unscored), out[4] = 26.0 control, out[8] = 5.0,
    out[12] = 26.0 sentinel."""
    o = [None] * 16
    o[0] = w0
    o[4] = SEED_CTL
    o[8] = SEED_A
    o[12] = SEED_CTL
    return {0: o}


def minifloat(k):
    """EXP-0138's inline 8-bit minifloat: srcB_reg = 64 + k in the non-GPR
    class. e = k>>3, m = k&7; value = m * 2^-5 (e == 0) else (8+m) * 2^(e-6)."""
    e, m = k >> 3, k & 7
    return float(m) * (2.0 ** -5) if e == 0 else float(8 + m) * (2.0 ** (e - 6))


def gpr_value(v):
    """Predicted GPR content for a 7-bit register field value under EXP-0112's
    M4 aliasing rule: R resolves to r(R mod 64) for R in [64,112]. Unseeded
    registers read exactly 0.0 (EXP-0087)."""
    return H.SEED.get(v % 64, 0.0)


def arm_B(mainlen):
    arms = []
    # B0 -- controls
    ctl = []
    ib = H.falu2_raw(D_B, R_SRCA, 2, opsel=4, opflags5=0, mod_lo=0)
    ctl.append(_case("B_CTRL", "uni", "falu2", "_baseline", 0,
                     "mod_lo=0, srcA=r0 (5.0), srcB=r2 (3.0). M4: 8.0.",
                     _uni_oracle(H.f32(SEED_A + H.SEED[2])), True, "synth",
                     modeA(mainlen, ib), ibytes=ib.hex(), roundtrip=True))
    ctl.append(_case("B_CTRL", "uni", "falu2", "_falsifier_oracle", 0,
                     "PRE-REGISTERED TO FAIL: the correct program judged "
                     "against an unreachable oracle -- proves match detection.",
                     _uni_oracle(H.f32(SEED_A + H.SEED[2] + 1.0)), False,
                     "synth", modeA(mainlen, ib), ibytes=ib.hex()))
    ib2 = H.falu2_raw(D_B, R_SRCA, 2, opsel=4, opflags5=0, mod_lo=2)
    ctl.append(_case("B_CTRL", "uni", "falu2", "_refuter_modlo2_unbound", 2,
                     "PRE-REGISTERED REFUTER (EXP-0138's own): mod_lo=2 with "
                     "srcB_reg=2 -- an unbound non-GPR index -- must NOT give "
                     "the GPR answer 8.0. M4 gave 5.0.",
                     _uni_oracle(H.f32(SEED_A + H.SEED[2])), False, "synth",
                     modeA(mainlen, ib2), ibytes=ib2.hex()))
    arms.append({"arm": "B_CTRL", "carrier": "uni", "instr": "falu2",
                 "field": "_controls", "cases": ctl,
                 "doc": "Baseline, oracle falsifier, and EXP-0138's own "
                        "pre-registered mod_lo refuter."})

    # B1 -- mod_lo dense over 4 operand configurations x 2 ops (EXP-0138's G1)
    def modlo_pred(v, sa, sb, op):
        a = 0.0 if (v & 1) else H.SEED.get(sa, 0.0)
        b = (UNI_M4.get(sb, 0.0) if (v & 6) == 2 else 0.0) if (v & 6) \
            else H.SEED.get(sb, 0.0)
        return H.f32(a + b) if op == 4 else H.f32(a * b)

    cases = []
    for op in (4, 5):
        for sa, sb in ((0, 2), (0, 6), (6, 2), (0, 3)):
            for v in range(8):
                ib = H.falu2_raw(D_B, sa, sb, opsel=op, opflags5=0, mod_lo=v)
                cases.append(_case("B_modlo", "uni", "falu2", "mod_lo", v,
                                   "srcA_reg=%d srcB_reg=%d opsel=%d. M4 model: "
                                   "bit0 = srcA class (1 -> reads 0.0); "
                                   "bits[2:1] = srcB class (0 GPR, 1 non-GPR, "
                                   "2/3 read 0.0, bit2 dominates bit1)."
                                   % (sa, sb, op),
                                   _uni_oracle(modlo_pred(v, sa, sb, op)), True,
                                   "synth", modeA(mainlen, ib), ibytes=ib.hex()))
    arms.append({"arm": "B_modlo", "carrier": "uni", "instr": "falu2",
                 "field": "mod_lo", "cases": cases,
                 "doc": "falu2.mod_lo 0..7 DENSE x 4 operand configurations x "
                        "{fadd, fmul} = 64 cases, scored against EXP-0138's "
                        "REPLACEMENT source-class model (not its refuted "
                        "pre-registration)."})

    # B2 -- srcB_reg 0..127 DENSE in the NON-GPR class (mod_lo = 2).
    # 0..63 should be the non-GPR operand file (M4: our four constants at
    # indices 6..9); 64..127 should be the inline minifloat immediate.
    cases = []
    for v in range(128):
        ib = H.falu2_raw(D_B, R_SRCA, v, opsel=4, opflags5=0, mod_lo=2)
        if v < 64:
            pred = H.f32(SEED_A + UNI_M4.get(v, 0.0))
            note = ("non-GPR file index %d; M4 map put our bound float4 at "
                    "6..9 = 101/202/303/404 (a PREDICTION here: the G17P "
                    "container may place them elsewhere)." % v)
        else:
            k = v - 64
            pred = H.f32(SEED_A + minifloat(k))
            note = ("inline minifloat k=%d -> %r (M4 HW points: k = 0, 2, 3, "
                    "31, 32, 48, 56, 61, 62, 63)." % (k, minifloat(k)))
        cases.append(_case("B_srcB_nongpr", "uni", "falu2", "srcB_reg", v, note,
                           _uni_oracle(pred), True, "synth",
                           modeA(mainlen, ib), ibytes=ib.hex()))
    arms.append({"arm": "B_srcB_nongpr", "carrier": "uni", "instr": "falu2",
                 "field": "srcB_reg@mod_lo=2", "cases": cases,
                 "doc": "srcB_reg 0..127 DENSE with mod_lo=2 (the non-GPR "
                        "class). Covers BOTH halves of EXP-0138's find: the "
                        "operand-file index map (0..63) and the inline 8-bit "
                        "minifloat immediate (64..127), including all ten M4 "
                        "HW-confirmed k values."})
    return arms


def arm_D_falu2(mainlen):
    """Register-file model, GPR class: srcB_reg 0..127 DENSE at mod_lo=0.
    Re-tests EXP-0112's r(R mod 64) aliasing and the 126/127 fault, AND
    EXP-0138's 'bit6 inert in GPR mode' claim, on one sweep."""
    cases = []
    for v in range(128):
        ib = H.falu2_raw(D_B, R_SRCA, v, opsel=4, opflags5=0, mod_lo=0)
        pred = H.f32(SEED_A + gpr_value(v))
        cases.append(_case("D_falu2_srcB", "uni", "falu2", "srcB_reg", v,
                           "GPR class. M4: r(R mod 64) for R in [64,112]; "
                           "126/127 FAULT.",
                           _uni_oracle(pred), v not in (126, 127), "synth",
                           modeA(mainlen, ib), ibytes=ib.hex()))
    return [{"arm": "D_falu2_srcB", "carrier": "uni", "instr": "falu2",
             "field": "srcB_reg@mod_lo=0", "cases": cases,
             "doc": "srcB_reg 0..127 DENSE in the GPR class. The direct G17P "
                    "re-test of EXP-0112's aliasing rule and fault bound."}]


# ===========================================================================
# ARM F -- mov_imm (EXP-0140), read back as u32
# ===========================================================================
F_DTYPE = {0: C.U32}


def _f_oracle(wD, wCTL=F_POISON):
    o = [None] * 16
    o[0] = wD
    o[4] = wCTL
    o[12] = F_SENT_BITS
    return {0: o}


def f_prog(mainlen, test_instr, pad=0):
    """mov_imm-seed r0..r13 to F_POISON (r14 stays unwritten = 0, r15 is the
    store index); write the SENTINEL out[12] = r12 = 26.0f via falu2i -- a path
    that does NOT use mov_imm; run the mov_imm under test; then read back."""
    body = [H.mov_imm(j, F_POISON) for j in range(14)]
    body += [H.mov_imm(H.R_IDX, 0)]
    body += [H.falu2i_raw(F_SENT_REG, H.R_UNWRITTEN, F_SENT_VAL, opflags4=0),
             H.store_word(12, F_SENT_REG)]
    body += [test_instr]
    body += [H.mov_imm(H.R_PAD, 0)] * pad
    body += [H.store_word(0, F_D), H.store_word(4, F_CTL)]
    return H.build_program(body, mainlen)


def arm_F(mainlen):
    arms = []
    ctl = []
    ib = H.mov_imm(F_D, F_TESTVAL)
    ctl.append(_case("F_CTRL", "uni", "mov_imm", "_baseline", F_TESTVAL,
                     "mov_imm(r6, 99). M4: out0 == 99, control stays 7.",
                     _f_oracle(F_TESTVAL), True, "synth",
                     f_prog(mainlen, ib), ibytes=ib.hex(), dtype=F_DTYPE,
                     roundtrip=True))
    ctl.append(_case("F_CTRL", "uni", "mov_imm", "_falsifier_oracle", F_TESTVAL,
                     "PRE-REGISTERED TO FAIL: correct program, unreachable oracle.",
                     _f_oracle(F_TESTVAL + 1), False, "synth",
                     f_prog(mainlen, ib), ibytes=ib.hex(), dtype=F_DTYPE))
    arms.append({"arm": "F_CTRL", "carrier": "uni", "instr": "mov_imm",
                 "field": "_controls", "cases": ctl,
                 "doc": "Baseline + oracle falsifier for arm F."})

    # F1 -- imm7 0..127 DENSE against a POISONED read-back buffer.
    # Also the first HARDWARE test of imm7 == 12, which M4 found does not
    # TOKENIZE under the current length rule (a decoder property; EXP-0140
    # explicitly did not test whether the hardware agrees).
    cases = []
    for v in range(128):
        ib = H.mov_imm(F_D, v)
        note = "mov_imm(r6, %d)" % v
        if v == 12:
            note += (" -- M4 DECODER DEFECT: imm7 == 12 does not tokenize "
                     "(byte+1 == 0x0C looks like the 4-byte 0x?c preamble). "
                     "EXP-0140 did not test the HARDWARE; this case does.")
        cases.append(_case("F_imm7", "uni", "mov_imm", "imm7", v, note,
                           _f_oracle(v), True, "synth", f_prog(mainlen, ib),
                           ibytes=ib.hex(), dtype=F_DTYPE))
    arms.append({"arm": "F_imm7", "carrier": "uni", "instr": "mov_imm",
                 "field": "imm7", "cases": cases,
                 "doc": "imm7 0..127 DENSE with a poisoned read-back buffer, "
                        "so 'wrote 0' and 'did not write' are distinguishable."})

    # F2 -- the imm_top boundary, PAIRED padded/unpadded.
    # M4: with imm_top=1 the instruction does not write at all; unpadded it
    # also consumes the following 2-byte instruction, so the read-back store
    # addresses the wrong word. The pair separates the two explanations.
    cases = []
    for imm8 in (128, 129, 140, 200, 255):
        ib = H.mov_imm_raw(F_D, imm8)
        cases.append(_case("F_imm_top", "uni", "mov_imm", "imm8_unpadded", imm8,
                           "imm_top=1, NO padding. M4: destination not written "
                           "AND the next 2-byte instruction is consumed.",
                           _f_oracle(F_POISON), None, "synth",
                           f_prog(mainlen, ib, pad=0), ibytes=ib.hex(),
                           dtype=F_DTYPE))
        cases.append(_case("F_imm_top", "uni", "mov_imm", "imm8_padded", imm8,
                           "imm_top=1 with 4 B of inert padding after it. M4: "
                           "the destination KEEPS its previous value (7), which "
                           "is why the immediate is 7 bits, not a silent zero.",
                           _f_oracle(F_POISON), True, "synth",
                           f_prog(mainlen, ib, pad=2), ibytes=ib.hex(),
                           dtype=F_DTYPE))
    arms.append({"arm": "F_imm_top", "carrier": "uni", "instr": "mov_imm",
                 "field": "imm_top", "cases": cases,
                 "doc": "imm_top=1 at five immediates, each in a PAIRED "
                        "padded/unpadded form -- EXP-0140's decisive control."})
    return arms


# ===========================================================================
# ARM D-iadd2 -- the register fault bound in a different family (EXP-0139)
# ===========================================================================
def dag_prog(mainlen, **over):
    f = dict(IADD2_BASE_FIELDS)
    f.update(over)
    instr = isadb.assemble("iadd2", f)
    body = [H.mov_imm(r, DAG_SEED[r]) for r in range(16)]
    # SENTINEL: out[4] = r13 = 33, stored BEFORE the iadd2 under test.
    body += [H.store_word(4, DAG_SENTINEL_REG, index_reg=DAG_R_IDX)]
    body += [instr, H.store_word(0, DAG_R_DST, index_reg=DAG_R_IDX)]
    return H.build_program(body, mainlen), instr


def dag_oracle(w0):
    o = [None] * 8
    o[0] = w0
    o[4] = DAG_SEED[DAG_SENTINEL_REG]
    return {0: o}


def dst_relocation_oracle(dst_field):
    """EXP-0139's pre-registered model. `dst` is (reg<<1)|size. Under
    EXP-0112's M4 aliasing rule R in [64,112] resolves to r(R mod 64), so the
    sum reaches the store's r6 iff the effective register is 6; otherwise r6
    keeps its mov_imm sentinel 99. EXP-0139 REFUTED the aliasing half here
    (dst = 140/141 is reg 70 and did NOT alias to r6) and found reg >= 96
    faults reproducibly -- both of which this arm re-measures on G17P."""
    reg = dst_field >> 1
    eff = (reg % 64) if 64 <= reg <= 112 else reg
    return DAG_BASE_SUM if eff == DAG_R_DST else DAG_R6_SENTINEL


def arm_D_iadd2(mainlen):
    cases = []
    prog, instr = dag_prog(mainlen)
    cases.append(_case("D_iadd2_dst", "dag", "iadd2", "_baseline", -1,
                       "unmutated: r0 + r2 = 32 into r6. M4 baseline.",
                       dag_oracle(DAG_BASE_SUM), True, "synth", prog,
                       ibytes=instr.hex(), roundtrip=True))
    cases.append(_case("D_iadd2_dst", "dag", "iadd2", "_falsifier_oracle", -1,
                       "PRE-REGISTERED TO FAIL: correct program, unreachable oracle.",
                       dag_oracle(DAG_BASE_SUM + 1), False, "synth", prog,
                       ibytes=instr.hex()))
    for v in range(256):
        prog, instr = dag_prog(mainlen, dst=v)
        reg = v >> 1
        note = "dst = (reg<<1)|size, reg = %d." % reg
        if reg >= 96:
            note += " M4 (EXP-0139): reg >= 96 FAULTS reproducibly."
        elif 64 <= reg <= 112:
            note += (" M4 (EXP-0139): EXP-0112's r(R mod 64) aliasing does NOT "
                     "hold for iadd2.dst -- reg 70 did not alias to r6.")
        cases.append(_case("D_iadd2_dst", "dag", "iadd2", "dst", v, note,
                           dag_oracle(dst_relocation_oracle(v)),
                           None, "synth", prog, ibytes=instr.hex()))
    return [{"arm": "D_iadd2_dst", "carrier": "dag", "instr": "iadd2",
             "field": "dst", "cases": cases,
             "doc": "iadd2.dst 0..255 DENSE with a relocation oracle. Answers "
                    "both halves of the register-model question on G17P: where "
                    "the fault boundary is, and whether mod-64 aliasing holds "
                    "for this field."}]


# ===========================================================================
# ARM C -- the native 64-bit ADD (EXP-0146), splice
# ===========================================================================
C_ADD_REPEATS = 5


def arm_C(anchor):
    """`anchor` = (offset_in_main, length, bytes) of the single `iadd2` inside
    the compiled k_u64sub. Only ONE field changes: `addsub`."""
    off, ln, base = anchor
    sub = {2: [(a - b) & M64 for a, b in zip(C.U64_A, C.U64_B)]}
    add = {2: [(a + b) & M64 for a, b in zip(C.U64_A, C.U64_B)]}
    bogus = {2: [(v + 1) & M64 for v in sub[2]]}
    flipped = A.set_field(base, "iadd2", "addsub", 1 - A.get_field(base, "iadd2", "addsub"))
    cases = [
        _case("C_i64add", "u64", "iadd2", "_baseline", -1,
              "unmutated `ulong a - b`: ONE iadd2 between an 8-byte "
              "device_load pair and an 8-byte device_store.",
              sub, True, "splice", splice=[(off, base)], ibytes=base.hex()),
        _case("C_i64add", "u64", "iadd2", "_falsifier_oracle", -1,
              "PRE-REGISTERED TO FAIL: correct program, unreachable oracle.",
              bogus, False, "splice", splice=[(off, base)], ibytes=base.hex()),
    ]
    for i in range(C_ADD_REPEATS):
        cases.append(_case("C_i64add", "u64", "iadd2", "addsub", i,
                           "byte0 %s -> %s (EXP-0146's falsifier F3). M4: an "
                           "EXACT 64-bit add with carry across the word "
                           "boundary. Repetition %d/%d."
                           % (hex(base[0]), hex(flipped[0]), i + 1, C_ADD_REPEATS),
                           add, True, "splice", splice=[(off, flipped)],
                           ibytes=flipped.hex()))
    return [{"arm": "C_i64add", "carrier": "u64", "instr": "iadd2",
             "field": "addsub", "cases": cases,
             "doc": "One bit of one instruction. 12 input rows per dispatch "
                    "including 2^63+2^63, 0x7FFF..F+1, "
                    "0xFFFFFFFF00000000+0xFFFFFFFF and 0xFFFF..E+3."}]


# ===========================================================================
# ARM E -- ibfe offset (LITERAL) vs width (mod 32) (EXP-0139), splice
# ===========================================================================
def ibfe_offset_model(off):
    return {2: [((a >> off) & 0xFF) if off < 32 else 0 for a in C.A_IN]}


def ibfe_offset_mod32_model(off):
    """The COMPETING model EXP-0139 rejected (NIR's 'mask offset mod 32'),
    scored on the same data by analysis/verdicts.py."""
    return {2: [(a >> (off % 32)) & 0xFF for a in C.A_IN]}


def ibfe_width_model(w):
    if w % 32 == 0:
        return {2: [(a >> 4) & M32 for a in C.A_IN]}
    return {2: [(a >> 4) & ((1 << (w % 32)) - 1) for a in C.A_IN]}


def ibfe_width_clamp_model(w):
    """The competing model EXP-0139 PRE-REGISTERED and then refuted."""
    ww = 32 if w >= 32 else w
    if ww == 0 or ww >= 32:
        return {2: [(a >> 4) & M32 for a in C.A_IN]}
    return {2: [(a >> 4) & ((1 << ww) - 1) for a in C.A_IN]}


def arm_E(anchor_bfe, anchor_shr):
    arms = []
    off, ln, base = anchor_bfe
    nat_off = A.get_field(base, "ibfe", "offset")
    nat_w = A.get_field(base, "ibfe", "width")
    ctl = [
        _case("E_CTRL", "bfe", "ibfe", "_baseline", -1,
              "unmutated `extract_bits(a, 4u, 8u)`; natural offset=%d width=%d."
              % (nat_off, nat_w), C.CARRIERS["bfe"]["oracle"], True, "splice",
              splice=[(off, base)], ibytes=base.hex()),
        _case("E_CTRL", "bfe", "ibfe", "_falsifier_oracle", -1,
              "PRE-REGISTERED TO FAIL: correct program, unreachable oracle.",
              {2: [(v + 0x5A5A5A) & M32 for v in C.CARRIERS["bfe"]["oracle"][2]]},
              False, "splice", splice=[(off, base)], ibytes=base.hex()),
    ]
    arms.append({"arm": "E_CTRL", "carrier": "bfe", "instr": "ibfe",
                 "field": "_controls", "cases": ctl,
                 "doc": "Baseline + falsifier for the ibfe carrier."})

    ow = A.field_span("ibfe", "offset")[1]
    ww = A.field_span("ibfe", "width")[1]
    cases = []
    for v in range(1 << ow):
        blob = A.set_field(base, "ibfe", "offset", v)
        cases.append(_case("E_offset", "bfe", "ibfe", "offset", v,
                           "M4 model: LITERAL -- o = (a >> %d) & 0xFF, and 0 "
                           "for v >= 32 (the field shifts out entirely). The "
                           "mod-32 model fitted only 32/64 on M4." % v,
                           ibfe_offset_model(v), True, "splice",
                           splice=[(off, blob)], ibytes=blob.hex()))
    arms.append({"arm": "E_offset", "carrier": "bfe", "instr": "ibfe",
                 "field": "offset", "cases": cases,
                 "doc": "ibfe.offset 0..%d DENSE, scored against the LITERAL "
                        "model. The mod-32 competitor is scored on the same "
                        "records by analysis/verdicts.py." % ((1 << ow) - 1)})

    cases = []
    for v in range(1 << ww):
        blob = A.set_field(base, "ibfe", "width", v)
        cases.append(_case("E_width", "bfe", "ibfe", "width", v,
                           "M4 model: width TAKEN MOD 32 (fitted 64/64); the "
                           "literal-clamp model fitted only 37/64. w == 0 mod "
                           "32 is the no-mask case.",
                           ibfe_width_model(v), True, "splice",
                           splice=[(off, blob)], ibytes=blob.hex()))
    arms.append({"arm": "E_width", "carrier": "bfe", "instr": "ibfe",
                 "field": "width", "cases": cases,
                 "doc": "ibfe.width 0..%d DENSE, scored against the mod-32 "
                        "model; the literal-clamp competitor is scored on the "
                        "same records offline." % ((1 << ww) - 1)})

    # adversarial second carrier: the SAME field in a DIFFERENT lowering
    off2, ln2, base2 = anchor_shr
    nat2 = A.get_field(base2, "ibfe", "offset")
    cases = [
        _case("E_shr", "shr", "ibfe", "_baseline", -1,
              "unmutated `a >> b` (a different ibfe lowering); natural offset=%d."
              % nat2, C.CARRIERS["shr"]["oracle"], True, "splice",
              splice=[(off2, base2)], ibytes=base2.hex()),
    ]
    for v in range(1 << ow):
        blob = A.set_field(base2, "ibfe", "offset", v)
        cases.append(_case("E_shr", "shr", "ibfe", "offset", v,
                           "adversarial cross-check in a second lowering; "
                           "scored against the UNMUTATED output (inertness), "
                           "so the accepted set is the finding.",
                           C.CARRIERS["shr"]["oracle"], (v == nat2), "splice",
                           splice=[(off2, blob)], ibytes=blob.hex()))
    arms.append({"arm": "E_shr", "carrier": "shr", "instr": "ibfe",
                 "field": "offset", "cases": cases,
                 "doc": "ibfe.offset swept in a SECOND, independent lowering "
                        "of the same instruction -- EXP-0139's adversarial "
                        "cross-check, repeated on G17P."})
    return arms


# ===========================================================================
# assembly
# ===========================================================================
def build_all(mainlens, anchors):
    """mainlens: {carrier: _agc.main length as compiled ON THIS TARGET}.
    anchors:   {'u64': (off,len,bytes), 'bfe': ..., 'shr': ...}."""
    arms = []
    arms += arm_A(mainlens["synth"])
    arms += arm_B(mainlens["uni"])
    arms += arm_D_falu2(mainlens["uni"])
    arms += arm_F(mainlens["uni"])
    arms += arm_D_iadd2(mainlens["dag"])
    arms += arm_C(anchors["u64"])
    arms += arm_E(anchors["bfe"], anchors["shr"])
    return arms
