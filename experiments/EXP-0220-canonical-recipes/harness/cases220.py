#!/usr/bin/env python3
"""EXP-0220 case matrix -- the OPERAND CLASSES AND CONTEXTS A COMPILER SELECTS.

Gate D: "a canonical recipe must cover the operand classes and context the
compiler will actually select".  This file enumerates them explicitly, so the
claim can be audited against the list rather than against a headline.

Every case is a COMPLETE GENERATED PROGRAM.  Each one carries:
  * a host oracle over every byte the program is predicted to touch;
  * a full architectural state dump (r0..r23);
  * a Gate B pre-registered detection-power control in its own arm;
  * `expect_match` -- false for the pre-registered FALSIFIERS, which must FAIL.

Case order in this file is the CANONICAL order.  run220.py dispatches in a
shuffled/reversed order (Gate E) and records the order actually used.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import synth220 as S      # noqa: E402
import prog220 as P       # noqa: E402

RA, RB, RD = 1, 2, 0                 # default srcA / srcB / dst
RC = 3                               # scratch for re-reads
PROBE_OFF = 700                      # extra probe store  -> out byte 11200
PROBE_OFF2 = 701
PROBE_OFF3 = 702
CASE_OFF = 600                       # default idx_off for a store under test
JA, JB = 40, 77                      # mem indices for the two float operands
INLINE_ONE = 24                      # inline-immediate code whose magnitude is 1.0

# EXP-0141 / EXP-0092: index_reg values that FAULT, and 112 which is
# nondeterministic.  Declared hazards; dispatched only in the named hazard arm.
IDXREG_HAZARD = [96, 97, 100, 111, 112, 120, 127]


# ---------------------------------------------------------------------------
R_JUNK = 13          # a mov_imm-seeded register: its bits read as a denormal


def alu_operand(pg, dst, k, salt):
    """Materialise a float operand with NO device_load anywhere in its chain.

    step 1  dst = junk * 0.0        (srcB_class 2 reads the constant 0.0)
    step 2  dst = dst + inline(k)   (EXP-0138's inline 8-bit minifloat)

    So the value is exactly `inline_srcB_value(k, neg=1)` and its PROVENANCE is
    purely ALU.  This matters: EXP-0220's own pilot (work/pilot/p02) shows the
    `mod_hi = 0xC` requirement is NOT a property of srcA alone -- a falu2 whose
    srcB is a live load result needs it too -- so an "ALU-sourced" arm that
    still loads one operand is not testing what it claims to."""
    pg.falu2(dst, "fmul", R_JUNK, srcB_class=2, mod_hi=0xC, opflags=0b000,
             salt=salt + "z")
    pg.falu2(dst, "fadd", dst, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=k,
             srcB_neg=1, mod_hi=0xC, opflags=0b000, salt=salt + "v")
    return dst


def _std_falu2_body(pg, alu_sourced, ja=JA, jb=JB, ra=RA, rb=RB):
    """Seed srcA/srcB with the stated OPERAND PROVENANCE.

    `alu_sourced=False` -> both operands are LIVE device_load results, the
    context in which EXP-0101 H1 / EXP-0167 found `mod_hi = 0xC` mandatory.
    `alu_sourced=True`  -> neither operand touches memory at all."""
    if alu_sourced:
        alu_operand(pg, ra, 40, "aa")          # inline code 40 -> 4.0
        alu_operand(pg, rb, 51, "ab")          # inline code 51 -> 12.0
    else:
        pg.load_f(ra, ja)
        pg.load_f(rb, jb)
    return pg


def _new(slots, salt, offnatural=True, seed_high=True):
    pg = P.Prog(slots, salt, offnatural=offnatural)
    pg.prologue(seed_high=seed_high)
    return pg


# ---------------------------------------------------------------------------
# builders, keyed by case["kind"]
# ---------------------------------------------------------------------------
def b_ctl_norun(c, slots, clen):
    """Nothing but `stop`.  Pre-registered prediction: the out buffer is
    UNTOUCHED -- every byte still poison.  This is the control that separates
    'our bytes ran' from 'the carrier ran'."""
    pg = P.Prog(slots, c["name"])
    return pg


def b_ctl_baseline(c, slots, clen):
    """Prologue + state dump only.  Gate B detection-power control for the
    entire observation path: sentinel + 24 register slots must all appear."""
    return _new(slots, c["name"])


def b_ctl_move(c, slots, clen):
    """Two cases differing ONLY in the operand value.  Their observables must
    differ -- the arm's proof that it can see a change at all."""
    pg = _new(slots, c["name"])
    pg.load_f(RA, c["ja"])
    pg.load_f(RB, JB)
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, load_sourced=True, opflags=0b010)
    return pg


def b_f2_class(c, slots, clen):
    pg = _new(slots, c["name"])
    _std_falu2_body(pg, c["alu_sourced"])
    kw = dict(opflags=0b010, load_sourced=not c["alu_sourced"])
    cls = c["srcB_class"]
    if cls == "gpr":
        kw.update(srcB_class=S.SRCB_CLASS_GPR, srcB_reg=RB)
    elif cls == "inline":
        kw.update(srcB_class=S.SRCB_CLASS_NONGPR, inline_k=c["k"])
    elif cls == "uniform":
        kw.update(srcB_class=S.SRCB_CLASS_NONGPR, srcB_reg=c["k"], srcB_reg_top=0)
    elif cls == "zero2":
        kw.update(srcB_class=2, srcB_reg=RB)
    elif cls == "zero3":
        kw.update(srcB_class=3, srcB_reg=RB)
    kw["srcB_neg"] = c["neg"]
    pg.falu2(RD, c["op"], RA, **kw)
    return pg


def b_f2_dst(c, slots, clen):
    """dst sweep r0..r15.  dst == r15 is the index register, so the result is
    rescued into r0 and the index restored before the dump -- otherwise every
    later store would address off the end of the buffer."""
    d = c["dst"]
    pg = _new(slots, c["name"])
    _std_falu2_body(pg, False)
    pg.falu2(d, "fadd", RA, srcB_reg=RB, load_sourced=True, opflags=0b010)
    if d == P.R_IDX:
        pg.falu2(RD, "fadd", d, srcB_class=2, opflags=0b000, salt="rescue")
        pg.movi(P.R_IDX, 0)
    return pg


def b_f2_srca(c, slots, clen):
    r = c["srcA_reg"]
    pg = _new(slots, c["name"])
    pg.load_f(r, c["ja"])
    pg.falu2(RD if r != RD else 4, "fmul", r,
             srcB_class=S.SRCB_CLASS_NONGPR, inline_k=INLINE_ONE, srcB_neg=1,
             load_sourced=True, opflags=0b010)
    pg.store(r, PROBE_OFF, tag="probe_srcA")
    return pg


def b_f2_srcb(c, slots, clen):
    """srcB_reg sweep.  srcA lives in a register the sweep can never name, so
    the two operands can never collide -- at srcB_reg == srcA the case would
    otherwise load one register twice and test nothing."""
    r = c["srcB_reg"]
    a = 10 if r != 10 else 11
    pg = _new(slots, c["name"])
    pg.load_f(a, JA)
    pg.load_f(r, c["jb"])
    d = RD if r != RD else 4
    pg.falu2(d, "fadd", a, srcB_reg=r, srcB_class=S.SRCB_CLASS_GPR,
             load_sourced=True, opflags=0b010)
    pg.store(r, PROBE_OFF, tag="probe_srcB")
    return pg


def b_f2_opflags(c, slots, clen):
    """opflags truth table.  DOCUMENTED MODEL (EXP-0086/0089/0099/0119):
    bit0 = release src0, bit1 = release src1, bit2 = destination publication,
    bits 3/4 = silent corruptors (EXP-0105).  After the tested instruction each
    source is READ AGAIN through a fresh falu2 with opflags = 0, so a released
    register is visible as a zero read rather than inferred."""
    v = c["opflags"]
    pg = _new(slots, c["name"])
    pg.load_f(RA, JA)
    pg.load_f(RB, JB)
    # The prediction is ALWAYS the TRUTHFUL one, including for the values the
    # documented model calls corruptors.  That is what makes the `corrupt`
    # bucket falsifiable: a "corruptor" that delivers the correct answer refutes
    # the model instead of being quietly excused by an unpredicted oracle.
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, load_sourced=True, opflags=v)
    # re-read both sources through an INDEPENDENT path (opflags = 0, srcB reads
    # the constant 0.0), so a released register is SEEN as a zero read rather
    # than inferred from the state dump alone.
    pg.falu2(4, "fadd", RA, srcB_class=2, opflags=0b000, salt="rr_a")
    pg.falu2(5, "fadd", RB, srcB_class=2, opflags=0b000, salt="rr_b")
    return pg


def b_f2_modhi(c, slots, clen):
    v = c["mod_hi"]
    alu = c["alu_sourced"]
    pg = _new(slots, c["name"])
    _std_falu2_body(pg, alu)
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, mod_hi=v, opflags=0b000)
    return pg


def b_f2_ctrl(c, slots, clen):
    v = c["ctrl"]
    pg = _new(slots, c["name"])
    _std_falu2_body(pg, False)
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, ctrl=v, load_sourced=True,
             opflags=0b000)
    return pg


def b_f2_size(c, slots, clen):
    """b16 operands read the LOW HALF of the register (EXP-0006).  The operands
    come from the PACKED-HALF mem words, not from the (j+1)/4 codewords whose
    low half is all zero -- otherwise a b16 arm reads 0.0 for both operands and
    passes by construction (the section 5a detection-power pitfall)."""
    pg = _new(slots, c["name"])
    _std_falu2_body(pg, False, ja=c["ja"], jb=c["jb"])
    pg.falu2(RD, c["op"], RA, srcB_reg=RB, srcA_size=c["sa"], srcB_size=c["sb"],
             load_sourced=True, opflags=0b000)
    return pg


def b_f2_regtop(c, slots, clen):
    pg = _new(slots, c["name"])
    _std_falu2_body(pg, False)
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, srcA_reg_top=c["at"], srcB_reg_top=c["bt"],
             load_sourced=True, opflags=0b010)
    return pg


def b_f2_inline(c, slots, clen):
    pg = _new(slots, c["name"])
    pg.load_f(RA, JA)
    pg.falu2(RD, c["op"], RA, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=c["k"],
             srcB_neg=c["neg"], load_sourced=True, opflags=0b010)
    return pg


def b_f2_opsel(c, slots, clen):
    pg = _new(slots, c["name"])
    _std_falu2_body(pg, False)
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, opsel=c["opsel"], load_sourced=True,
             opflags=0b010, predict=c["opsel"] in (4, 5))
    return pg


def b_f2_special(c, slots, clen):
    pg = _new(slots, c["name"])
    pg.load_f(RA, c["ja"])
    pg.load_f(RB, c["jb"])
    pg.falu2(RD, c["op"], RA, srcB_reg=RB, load_sourced=True, opflags=0b010)
    return pg


def b_f2_falsifier(c, slots, clen):
    """Pre-registered to FAIL: the program computes fadd, the oracle predicts
    fmul.  If this case MATCHES, the comparator has no detection power and the
    whole arm is `carrier-undecidable`."""
    pg = _new(slots, c["name"])
    _std_falu2_body(pg, False)
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, load_sourced=True, opflags=0b010,
             predict=False)
    a, b = pg.rbits(RA), pg.rbits(RB)
    pg.set_reg(RD, P.fbits(S.bits_f32(a) * S.bits_f32(b)))
    return pg


# ---------------------------------------------------------------------------
# device_store arms
# ---------------------------------------------------------------------------
def b_s0_slot(c, slots, clen):
    """base_slot -> bound-buffer mapping, by HARDWARE PROBE.  The only store in
    the program is the probe itself, and all three buffers are read back, so the
    answer comes from where the data lands -- not from a compiled donor."""
    pg = P.Prog({"out": 0, "mem": 1, "imem": 2}, c["name"])
    pg.movi(P.R_IDX, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    S.device_store(pg.E, P.R_IDX, 10, c["slot"], P.R_SENT,
                   salt=c["name"], offnatural=False)
    pg.writes.append(("probe", None, None, "slot%d" % c["slot"]))
    return pg


def _ds_seed(pg, forwarded):
    """Seed the data register.  `forwarded` selects the DATA SOURCE CLASS:
    a live device_load result (addr_mode bit1 REQUIRED) vs an ALU-computed
    value (bit1 inert)."""
    pg.load_f(RA, JA)
    if not forwarded:
        pg.falu2(RA, "fmul", RA, srcB_class=S.SRCB_CLASS_NONGPR,
                 inline_k=INLINE_ONE, srcB_neg=1, load_sourced=True,
                 opflags=0b010, salt="aluify")
    return RA


def b_ds_stformat(c, slots, clen):
    pg = _new(slots, c["name"])
    pg.load_f(RA, JA)
    pg.load_f(RA + 1, JA + 1)
    pg.load_f(RA + 2, JA + 2)
    pg.load_f(RA + 3, JA + 3)
    pg.falu2(RA, "fmul", RA, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=INLINE_ONE,
             srcB_neg=1, load_sourced=True, opflags=0b010, salt="aluify")
    pg.store(RA, CASE_OFF, st_format=c["st_format"], tag="under_test",
             predict=c["st_format"] in P.ST_FORMAT_SHAPE)
    return pg


def b_ds_addrmode(c, slots, clen):
    """EXP-0141's context rule, tested as a PREDICTION rather than assumed:
    with a live load-result source, only addr_mode values with bit1 SET deliver
    the data; the other 128 store zero.  With an ALU-computed source the field
    is inert over all 256."""
    fwd = c["forwarded"]
    v = c["addr_mode"]
    pg = _new(slots, c["name"])
    R = _ds_seed(pg, fwd)
    pg.store(R, CASE_OFF, addr_mode=v, tag="under_test")
    return pg


def b_ds_extmode(c, slots, clen):
    v = c["extmode"]
    R = (v >> 1) & 0x3F
    pg = _new(slots, c["name"])
    pg.load_f(RA, JA)
    pg.falu2(RA, "fmul", RA, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=INLINE_ONE,
             srcB_neg=1, load_sourced=True, opflags=0b010, salt="aluify")
    # every register the sweep can name is given a KNOWN value, so a wrong
    # decode of extmode shows up as the wrong codeword rather than as a blank.
    for r in c["seed_regs"]:
        pg.load_f(r, 200 + r, salt="dsseed%d" % r)
    pg.falu2(11, "fmul", R_JUNK, srcB_class=2, mod_hi=0xC, opflags=0b000,
             salt="segap")            # separate the last seed load from the store
    known = (v % 2 == 0) and (v <= 126)
    pg.store(RA, CASE_OFF, extmode=v, tag="under_test", predict=known)
    return pg


def b_ds_indexreg(c, slots, clen):
    """index_reg sweep.  Registers above r15 cannot be reached by `mov_imm`
    (its dst is a 4-bit nibble), so they are seeded by a `device_load` -- and
    then ONE independent ALU instruction separates the load from the store,
    because EXP-0220's D12 shows a store whose index register is a live load
    result addresses with the STALE value."""
    ir = c["index_reg"]
    pg = _new(slots, c["name"])
    R = _ds_seed(pg, False)
    if ir < 16:
        pg.movi(ir, c["idxval"])
    else:
        pg.load_i(ir, c["idxval"], salt="idxseed%d" % ir)
        pg.falu2(11, "fmul", R_JUNK, srcB_class=2, mod_hi=0xC, opflags=0b000,
                 salt="idxgap")
    pg.store(R, c["idx_off"], index_reg=ir, tag="under_test")
    pg.movi(P.R_IDX, 0)                       # restore before the dump
    return pg


def b_ds_lifetime(c, slots, clen):
    """The three index-register lifetime rules, each as its own prediction:

      release      after a store, the register named by index_reg reads 0
      reuse        a SECOND store reusing that register therefore addresses
                   with index 0
      live_load    a store whose index register was written by the immediately
                   preceding device_load addresses with the STALE value
      gapped_load  one intervening instruction makes the loaded value visible
    """
    v = c["variant"]
    pg = _new(slots, c["name"])
    R = _ds_seed(pg, False)
    if v == "release":
        pg.movi(4, 22)
        pg.store(R, 300, index_reg=4, tag="under_test")
    elif v == "reuse":
        pg.movi(4, 22)
        pg.store(R, 300, index_reg=4, tag="first")
        pg.store(R, 301, index_reg=4, tag="under_test")
    elif v == "live_load":
        pg.movi(6, 22)
        pg.load_i(6, 33)
        pg.store(R, 302, index_reg=6, tag="under_test")
    else:
        pg.movi(7, 22)
        pg.load_i(7, 34)
        pg.falu2(11, "fmul", R_JUNK, srcB_class=2, mod_hi=0xC, opflags=0b000,
                 salt="lgap")
        pg.store(R, 303, index_reg=7, tag="under_test")
    pg.movi(P.R_IDX, 0)
    return pg


def b_ds_idxoff(c, slots, clen):
    pg = _new(slots, c["name"])
    R = _ds_seed(pg, False)
    pg.store(R, c["idx_off"], tag="under_test")
    return pg


def b_ds_slot(c, slots, clen):
    """Store into each BOUND buffer.  The data must land in the buffer the slot
    names and nowhere else -- read back all three."""
    pg = _new(slots, c["name"])
    R = _ds_seed(pg, False)
    pg.store(R, c["idx_off"], base=c["base"], tag="under_test")
    return pg


def b_ds_space(c, slots, clen):
    v = c["space"]
    pg = _new(slots, c["name"])
    R = _ds_seed(pg, False)
    if v & 0x02:
        # EXP-0141 / EXP-0100: bit1 selects THREADGROUP space, so a device
        # buffer must NOT be written.  Predicted extent unknown -> the case is
        # scored on the device buffer staying poison at the target address.
        pg.store_predicted(R, CASE_OFF, [], space=v, tag="under_test")
    else:
        pg.store(R, CASE_OFF, space=v, tag="under_test")
    return pg


def b_ds_inert(c, slots, clen):
    pg = _new(slots, c["name"])
    R = _ds_seed(pg, False)
    pg.store(R, CASE_OFF, tag="under_test", **{c["field"]: c["value"]})
    return pg


def b_ds_falsifier(c, slots, clen):
    """Pre-registered to FAIL: the store is correct, the oracle predicts the
    value from a DIFFERENT register."""
    pg = _new(slots, c["name"])
    R = _ds_seed(pg, False)
    pg.load_f(RB, JB)
    wrong = pg.rbits(RB)
    import struct as _s
    pg.store_predicted(R, CASE_OFF, _s.pack("<I", wrong), tag="under_test")
    return pg


def b_f2_prov(c, slots, clen):
    """OPERAND PROVENANCE x mod_hi x DISTANCE.

    Section 6 ("register lifecycle and operand provenance") makes this a
    required dimension: "if behaviour depends on how or when a register was
    defined, document the lifecycle rule and do not misattribute it to an
    encoding bit".  EXP-0220's pilot found exactly such a dependence -- the
    `mod_hi = 0xC` requirement follows the LIVE LOAD RESULT, not srcA -- so this
    arm measures it as a 4 x 5 x 3 matrix rather than assuming either reading.

    `gap` inserts that many independent ALU instructions between the last load
    and the instruction under test, which is the axis that separates "live
    forward" from "register provenance"."""
    prov, mh, gap = c["prov"], c["mod_hi"], c["gap"]
    pg = _new(slots, c["name"])
    if prov == "alu_both":
        alu_operand(pg, RA, 40, "pa")
        alu_operand(pg, RB, 51, "pb")
    elif prov == "load_both":
        pg.load_f(RA, JA)
        pg.load_f(RB, JB)
    elif prov == "load_srcA":
        alu_operand(pg, RB, 51, "pb")
        pg.load_f(RA, JA)
    else:                                     # load_srcB
        alu_operand(pg, RA, 40, "pa")
        pg.load_f(RB, JB)
    for g in range(gap):
        pg.falu2(6 + g, "fmul", R_JUNK, srcB_class=2, mod_hi=0xC, opflags=0b000,
                 salt="gap%d" % g)
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, mod_hi=mh, opflags=0b000)
    return pg


BUILDERS = {
    "f2_prov": b_f2_prov,
    "ds_lifetime": b_ds_lifetime,
    "ctl_norun": b_ctl_norun, "ctl_baseline": b_ctl_baseline, "ctl_move": b_ctl_move,
    "f2_class": b_f2_class, "f2_dst": b_f2_dst, "f2_srca": b_f2_srca,
    "f2_srcb": b_f2_srcb, "f2_opflags": b_f2_opflags, "f2_modhi": b_f2_modhi,
    "f2_ctrl": b_f2_ctrl, "f2_size": b_f2_size, "f2_regtop": b_f2_regtop,
    "f2_inline": b_f2_inline, "f2_opsel": b_f2_opsel, "f2_special": b_f2_special,
    "f2_falsifier": b_f2_falsifier,
    "s0_slot": b_s0_slot,
    "ds_stformat": b_ds_stformat, "ds_addrmode": b_ds_addrmode,
    "ds_extmode": b_ds_extmode, "ds_indexreg": b_ds_indexreg,
    "ds_idxoff": b_ds_idxoff, "ds_slot": b_ds_slot, "ds_space": b_ds_space,
    "ds_inert": b_ds_inert, "ds_falsifier": b_ds_falsifier,
}


# ---------------------------------------------------------------------------
# kinds that deliberately carry NO integrity sentinel: `ctl_norun` predicts an
# untouched buffer, and `s0_slot`'s only store IS the measurement.
NO_SENTINEL = {"s0_slot", "ctl_norun"}


def _c(kind, name, arm, **kw):
    """`predicted_bucket` is the Gate C BEHAVIOUR BUCKET this case is
    pre-registered to land in, chosen before any output is seen:

      exact    every touched byte is predicted and must agree;
      corrupt  the documented model says this value corrupts -- the case must
               come out NOT exact, and a clean result REFUTES the model;
      measure  a discovery case: no prediction is made, only recorded.
    """
    d = {"kind": kind, "name": name, "arm": arm, "expect_match": True,
         "hazard": False, "expect_sentinel": kind not in NO_SENTINEL,
         "predicted_bucket": "exact"}
    d.update(kw)
    return d


def build_cases(include_hazard=False):
    cs = []

    # ---- S0: base_slot by hardware probe (must run first, everything else
    #          depends on the mapping it establishes) ------------------------
    for s in range(0, 8):
        # S0 MEASURES the slot -> bound-buffer mapping; it is scored by where
        # the probe store landed, not against a predicted byte map.
        cs.append(_c("s0_slot", "s0_slot%02d" % s, "S0", slot=s,
                     predicted_bucket="measure"))

    # ---- controls -------------------------------------------------------
    cs.append(_c("ctl_norun", "ctl_norun", "CTL"))
    cs.append(_c("ctl_baseline", "ctl_baseline", "CTL"))
    for ja in (40, 41, 300):
        cs.append(_c("ctl_move", "ctl_move_j%d" % ja, "CTL", ja=ja))
    cs.append(_c("f2_falsifier", "ctl_falsifier_falu2", "CTL", expect_match=False,
                 predicted_bucket="refute"))
    cs.append(_c("ds_falsifier", "ctl_falsifier_store", "CTL", expect_match=False,
                 predicted_bucket="refute"))

    # ---- A: falu2 operand classes ---------------------------------------
    for op in ("fadd", "fmul"):
        for cls in ("gpr", "inline", "uniform", "zero2", "zero3"):
            for neg in (0, 1):
                for alu in (False, True):
                    cs.append(_c("f2_class",
                                 "f2_class_%s_%s_n%d_%s" % (op, cls, neg,
                                                            "alu" if alu else "load"),
                                 "A1-operand-class", op=op, srcB_class=cls, neg=neg,
                                 alu_sourced=alu, k=INLINE_ONE if cls == "inline" else 7,
                                 predicted_bucket="measure" if cls == "uniform" else "exact"))
    for d in range(16):
        cs.append(_c("f2_dst", "f2_dst%02d" % d, "A2-dst", dst=d))
    for r in range(64):
        cs.append(_c("f2_srca", "f2_srca%02d" % r, "A3-srcA_reg",
                     srcA_reg=r, ja=(40 + r) % 512))
    for r in range(64):
        cs.append(_c("f2_srcb", "f2_srcb%02d" % r, "A4-srcB_reg",
                     srcB_reg=r, jb=(120 + r) % 512))
    for v in range(32):
        cs.append(_c("f2_opflags", "f2_opflags%02d" % v, "A5-opflags", opflags=v,
                     predicted_bucket="exact" if (v & 0b11000) == 0 else "corrupt"))
    for alu in (False, True):
        for v in range(16):
            # `_std_falu2_body` places the tested instruction IMMEDIATELY after
            # the loads in the load-sourced arm (gap 0) and after a pure-ALU
            # chain in the other, so the rule above applies directly.
            ok = ((v & 1) == 0) and (alu or v == 0xC)
            cs.append(_c("f2_modhi", "f2_modhi_%s_%02d" % ("alu" if alu else "load", v),
                         "A6-mod_hi", mod_hi=v, alu_sourced=alu,
                         predicted_bucket="exact" if ok else "corrupt"))
    for v in range(0, 128, 4):                      # bits 0/1 = length selector: held 0
        cs.append(_c("f2_ctrl", "f2_ctrl%03d" % v, "A7-ctrl", ctrl=v,
                     predicted_bucket="exact" if (v & 0x60) == 0 else "corrupt"))
    for op in ("fadd", "fmul"):
        for sa in (0, 1):
            for sb in (0, 1):
                for n in range(4):
                    cs.append(_c("f2_size",
                                 "f2_size_%s_a%d_b%d_p%d" % (op, sa, sb, n),
                                 "A8-operand-size", op=op, sa=sa, sb=sb,
                                 ja=528 + n, jb=532 + n,
                                 predicted_bucket="exact" if (sa == 1 and sb == 1)
                                 else "measure"))
    for at in (0, 1):
        for bt in (0, 1):
            cs.append(_c("f2_regtop", "f2_regtop_a%d_b%d" % (at, bt),
                         "A9-reg_top", at=at, bt=bt))
    for op in ("fadd", "fmul"):
        for k in range(64):
            for neg in (0, 1):
                cs.append(_c("f2_inline", "f2_inline_%s_k%02d_n%d" % (op, k, neg),
                             "A10-inline-immediate", op=op, k=k, neg=neg))
    for o in range(8):
        cs.append(_c("f2_opsel", "f2_opsel%d" % o, "A11-opsel", opsel=o,
                     predicted_bucket="exact" if o in (4, 5) else "measure"))
    for prov in ("load_both", "load_srcA", "load_srcB", "alu_both"):
        for mh in (0x0, 0x4, 0x8, 0xC, 0xE):
            for gap in (0, 1, 2):
                    # CORRECTED by EXP-0220's own pre-freeze diagnostics D7/D9 and
                # by the p03 pilot, BEFORE the contract is frozen:
                #   mod_hi bit0 set    -> the destination is NOT written (D9);
                #   bits 2 AND 3 set   -> required only while a device_load
                #                         result is still IN FLIGHT (gap == 0).
                live_load = (prov != "alu_both") and gap == 0
                ok = ((mh & 1) == 0) and ((mh == 0xC) or not live_load)
                cs.append(_c("f2_prov",
                             "f2_prov_%s_m%02x_g%d" % (prov, mh, gap),
                             "A13-operand-provenance", prov=prov, mod_hi=mh, gap=gap,
                             predicted_bucket="exact" if ok else "corrupt"))

    SPECIAL = list(range(512, 528))
    for op in ("fadd", "fmul"):
        for j in SPECIAL:
            # NaN payload propagation and overflow-to-infinity are NOT claimed
            # bit-for-bit against a host double: those two are recorded only.
            v = P.MEM[j]
            # NaN payloads, overflow to infinity and DENORMALS are recorded, not
            # claimed: p07 showed a denormal result flushing to zero, so a host
            # double cannot be the oracle for them.
            risky = (v != v) or v in (float("inf"), float("-inf")) \
                or abs(v) > 3.0e38 or (v != 0.0 and abs(v) < 1.2e-38)
            cs.append(_c("f2_special", "f2_special_%s_j%d" % (op, j),
                         "A12-ieee-boundary", op=op, ja=j, jb=JB,
                         predicted_bucket="measure" if risky else "exact"))

    # ---- B: device_store operand classes --------------------------------
    for f in (17, 1, 33, 25, 29, 23, 0, 255):
        cs.append(_c("ds_stformat", "ds_stformat%03d" % f, "B1-st_format", st_format=f,
                     predicted_bucket="exact" if f in P.ST_FORMAT_SHAPE else "measure"))
    for fwd in (False, True):
        for v in range(256):
            cs.append(_c("ds_addrmode",
                         "ds_addrmode_%s_%03d" % ("fwd" if fwd else "alu", v),
                         "B2-addr_mode-context", addr_mode=v, forwarded=fwd))
    # every register the extmode sweep can name gets a UNIQUE codeword, so a
    # wrong decode shows up as the wrong codeword rather than as a blank.
    # PREDICTION (pre-registered): data register = (extmode >> 1) & 0x3F, i.e.
    # EXP-0112's HW-validated mod-64 GPR aliasing rule applied to the 7-bit
    # extmode/2 index -- which is also what makes the documented `2*R | 0xC0`
    # form land on r(32+R).  extmode 252..255 select r126/r127, which EXP-0112
    # recorded as FAULTING; they are declared hazards.
    # Registers r24..r95 are seeded by device_load (mov_imm cannot reach them),
    # so every value the sweep can name has a UNIQUE codeword.
    #   even v <= 126 -> the documented `extmode = 2*R` rule, gated `exact`;
    #   odd v         -> pre-registered `corrupt` (bit0 is NOT a don't-care here);
    #   v >= 128      -> `measure`: whether the 7-bit index reaches r64..r95, or
    #                    aliases mod 64 as EXP-0112 found for a falu2 SOURCE, is
    #                    exactly what this sub-arm is here to record.
    SEEDS = list(range(24, 96))
    for v in range(256):
        cs.append(_c("ds_extmode", "ds_extmode%03d" % v, "B3-extmode",
                     extmode=v, seed_regs=SEEDS, hazard=(v >= 252),
                     predicted_bucket=("corrupt" if v & 1 else
                                       ("exact" if v <= 126 else "measure"))))
    for ir in list(range(24)) + [32, 48, 63, 64, 80, 95]:
        iv = (7 + ir) % 64
        if iv == 12:                      # mov_imm imm7 == 12 does not tokenize
            iv = 13
        cs.append(_c("ds_indexreg", "ds_indexreg%03d" % ir, "B4-index_reg",
                     index_reg=ir, idxval=iv, idx_off=CASE_OFF))
    for ir in IDXREG_HAZARD:
        cs.append(_c("ds_indexreg", "ds_indexreg_hz%03d" % ir, "B4H-index_reg-hazard",
                     index_reg=ir, idxval=3, idx_off=CASE_OFF, hazard=True))
    OFFS = sorted(set([0, 1, 2, 3, 4, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 255,
                       256, 511, 512, 1023, 1024, 1025, 1535, 2046, 2047,
                       599, 601, 799, 801] ) - P.RESERVED_OFFS)
    for o in OFFS:
        cs.append(_c("ds_idxoff", "ds_idxoff%04d" % o, "B5-idx_off", idx_off=o))
    for base, off in (("out", CASE_OFF), ("mem", 5), ("imem", 6)):
        cs.append(_c("ds_slot", "ds_slot_%s" % base, "B6-base_slot",
                     base=base, idx_off=off))
    for v in (0, 2, 4, 6, 20, 22, 84, 252, 254, 255):
        # bit1 selects THREADGROUP space (EXP-0141/EXP-0100).  What a
        # threadgroup-space store does to a DEVICE buffer bound at that slot is
        # not predicted here, only recorded.
        cs.append(_c("ds_space", "ds_space%03d" % v, "B7-space", space=v,
                     predicted_bucket="measure" if (v & 0x02) else "exact"))
    # Each field's ACCEPTED-SET RULE is stated first, then boundary values on
    # both sides of it are dispatched: a rule that only ever sees values inside
    # its own accepted set cannot be refuted (section 5a).
    TAIL = (("access_desc", [0, 1, 0x20, 0x21, 0x5A, 0x80, 0xFE, 0xFF],
             lambda v: True),                       # EXP-0141 inert 256/256
            ("reserved7", [0, 1, 0x5A, 0x80, 0xFF], lambda v: True),
            ("reserved13", [0, 1, 0x5A, 0x80, 0xFF], lambda v: True),
            ("st_format_ext", [0, 1, 0x1F, 0x40, 0x60, 0x7F],
             lambda v: v & 0x60 == 0),              # EXP-0141 exact mask
            ("st_desc_hi", [0, 0x04, 0x0A, 0x24, 0x2E, 0x11, 0x3F],
             lambda v: v & 0x11 == 0),              # EXP-0141 exact mask
            ("elem_size", [0x11, 0x17, 0x27, 0x37, 0x00, 0x01, 0xFF],
             lambda v: v in S.DS_ELEM_OK))
    for field, vals, ok in TAIL:
        for v in vals:
            cs.append(_c("ds_inert", "ds_%s_%03d" % (field, v), "B8-descriptor-tail",
                         field=field, value=v,
                         predicted_bucket="exact" if ok(v) else "corrupt"))

    # ---- B9: the index-register LIFETIME rules (EXP-0220 D10/D11/D12) -------
    for n in ("release", "reuse", "live_load", "gapped_load"):
        cs.append(_c("ds_lifetime", "ds_lifetime_%s" % n, "B9-index-lifetime",
                     variant=n))

    if not include_hazard:
        cs = [c for c in cs if not c["hazard"]]
    for i, c in enumerate(cs):
        c["i"] = i
    return cs


# kinds whose whole point is that the out buffer stays untouched, or that the
# ONLY store in the program is the one under test.  A state dump would defeat
# both, so it is omitted and the case is scored on the buffers directly.
NO_DUMP = {"s0_slot", "ctl_norun"}


def build_program_for(case, slots, carrier_len):
    pg = BUILDERS[case["kind"]](case, slots, carrier_len)
    if case["kind"] not in NO_DUMP:
        pg.dump()
    prog = pg.finish(carrier_len)
    return pg, prog


if __name__ == "__main__":
    cs = build_cases()
    import collections
    print("total cases:", len(cs))
    for arm, n in sorted(collections.Counter(c["arm"] for c in cs).items()):
        print("  %-26s %4d" % (arm, n))
