#!/usr/bin/env python3
"""EXP-0119 shared case matrix: register LIFETIME field map (successor to
EXP-0086/0089/0099). Single source of truth imported by run.py, verify.py,
analysis.py. See PRE_REGISTRATION.md for the falsifier design each group
answers (H1-H4 per the dispatch) and PROGRESS.md for the pilot-phase
evidence that shaped this frozen matrix (every non-trivial construction
below was smoke-tested on real M4 hardware in `work/pilot_*` before this
file was frozen; the pilot itself caught two real bugs -- documented inline
where relevant -- that would otherwise have produced wrong oracles).

Two case "modes":
  MODE A (the overwhelming majority): a fully HAND-ASSEMBLED straight-line
    program (via isa_helpers.py's isadb.assemble()-based builders), spliced
    whole into carrier.metal's `_agc.main` region at offset 0
    (isa_helpers.build_program). Full control over instruction order and
    every field; independent of compiler scheduling. Proven fully
    deterministic in EXP-0099 and in every one of this experiment's own
    pilot runs.
  MODE B (H2_CACHEBYTE_* only): byte-field splice into a REAL COMPILED
    kernel's specific instruction offsets (kernels/lit17_unpack.metal,
    lit17_cvt.metal -- reused verbatim from EXP-0089, recompiled fresh in
    this experiment's own tree and reverified byte-identical to EXP-0089's
    recorded anchors before use). Used ONLY for unpack_convert/cvt_i2f,
    whose register-addressing fields are NOT independently validated for
    hand construction (EXP-0089's own positive-control gap) -- reusing a
    compiler-proven anchor and touching only its already-free `cache`/
    `mode` byte keeps this experiment inside validated territory.

REGISTER-ADDRESSING SCOPE (repeated from isa_helpers.py -- READ IT): this
experiment owns LIFETIME, not ADDRESSING (EXP-0113 owns addressing). Every
MODE A family used here has an independently HW-VALIDATED register field
for hand construction; iadd2/falu_compact4/falu_acc/ilogic/ibfins were
deliberately excluded (their addressing is STRUCTURAL/byte-diff-only or, for
iadd2, explicitly "not independently re-derived anywhere in this project"
per EXP-0090/EXP-0112's own builders) -- see isa_helpers.py docstring for
the full reasoning. `ibitcount` (H2/H3) is the one NEW family added here,
independently HW-VALIDATED for dst/src addressing by direct hardware splice
in EXP-M4-14 (A18) and RE-CONFIRMED on M4 by this experiment's own pilot
(seeding a register via falu2i and reading back its exact popcount).

IMMEDIATE PALETTE (frozen; see isa_helpers.imm_value -- the minifloat
immediate codec clamps/rounds outside a narrow safe range, discovered
during this experiment's own pilot phase, see PROGRESS.md "pilot bug 2"):
  V  = imm_value(30.0)  = 30.0   seed value for the primary test register
  K2 = imm_value(20.0)  = 20.0   first later-reader's increment
  K3 = imm_value(8.0)   = 8.0    the H4 "fresh rewrite" value
  K4 = imm_value(12.0)  = 12.0   second/third later-reader's increment
  ONE = imm_value(1.0)  = 1.0    falu3_srcmod12's companion multiplicative-identity seed
All four are independently confirmed EXACT round-trip fixed points (no
rounding) -- see PROGRESS.md's imm_value sweep table.

REGISTER PLAN: R_IDX=15 (index reg, always 0), R_UNWRITTEN=14 (never
written, reads 0.0 -- EXP-0087), R3=3 (primary seeded test register),
R5=5 (falu3_srcmod12's companion "1.0" seed), R0/R1/R2/R4=throwaway dst
registers for producers/readers, R6=6 (pressure-test dummy target),
R7=7 (deliberately never written -- "other register" control),
R9=9 (memop-intervening's throwaway load target), pad_dst=13 (never a
live target).

WORD-SLOT CONVENTION (device_store's idx_off unit = 4 words = 16 bytes,
HW-VALIDATED EXP-0090/re-confirmed this experiment's pilot): idx_off=0 ->
word0, 1 -> word4, 2 -> word8, 3 -> word12. Every case's oracle keys are
these absolute word indices into the 16-word output buffer.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only: assemble/disassemble/decode_one)
import isa_helpers as H  # noqa: E402

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
CARRIER_LEN = 170          # kernels/carrier.metal's _agc.main length, MODE A
OUT_WORDS = 16              # words read back from buffer(0)
MEM_WORDS = list(range(8))  # buffer(1) content (unused by every MODE A case;
                             # carrier.metal's own arithmetic never executes)

# Per-kernel buffer-role/IO config, keyed by case["kernel"]. carrier.metal's
# signature is (device float* out [[buffer(0)]], device float* mem
# [[buffer(1)]]) -- output first. lit17_unpack.metal/lit17_cvt.metal
# (reused verbatim from EXP-0089) declare the OPPOSITE order (device
# uint*/int* a [[buffer(0)]], device float* out [[buffer(1)]]) -- input
# first -- and need the EXACT input values EXP-0089 compiled against (their
# baseline oracle strings "0.50000763, 6.0000305" / "1244, 1254" depend on
# these specific inputs). CAUGHT IN THIS EXPERIMENT'S OWN SMOKE TEST
# (PROGRESS.md "pilot bug 4"): an earlier version of case_exec.py hardcoded
# carrier.metal's buffer order for every kernel, silently binding
# lit17_unpack/lit17_cvt's INPUT to the OUTPUT slot (and vice versa) --
# every MODE B case ran successfully (STATUS OK) but read back all-zero
# output, which without this table would have looked like "the field sweep
# has no effect" rather than "the harness is reading the wrong buffer".
KERNEL_IO = {
    "carrier": {"out_buf": 0, "in_buf": 1, "in_pack": "f32", "in_vals": MEM_WORDS, "out_words": OUT_WORDS},
    "lit17_unpack": {"out_buf": 1, "in_buf": 0, "in_pack": "u32", "in_vals": [0x70001000], "out_words": 2},
    "lit17_cvt": {"out_buf": 1, "in_buf": 0, "in_pack": "i32", "in_vals": [1234], "out_words": 2},
}

V = H.imm_value(30.0)
K2 = H.imm_value(20.0)
K3 = H.imm_value(8.0)
K4 = H.imm_value(12.0)
ONE = H.imm_value(1.0)
assert (V, K2, K3, K4, ONE) == (30.0, 20.0, 8.0, 12.0, 1.0), "immediate palette drifted from its frozen fixed points"

R_IDX = H.R_IDX
R_UNW = H.R_UNWRITTEN
R3, R5, R6, R7, R9 = 3, 5, 6, 7, 9


def seed_r3():
    """r3 = V, via falu2i(srcA=UNWRITTEN, k=V) -- HW-VALIDATED path
    (EXP-0087 MOVE-04: unwritten reads exactly 0.0)."""
    return H.falu2i_raw(R3, R_UNW, V, opflags4=0)


def seed_r5_one():
    """r5 = 1.0 (falu3_srcmod12's multiplicative-identity companion)."""
    return H.falu2i_raw(R5, R_UNW, ONE, opflags4=0)


def reader(dst, k, srcA_reg=R3, opflags4=0):
    """A separate, later falu2i reading srcA_reg (default r3) again."""
    return H.falu2i_raw(dst, srcA_reg, k, opflags4=opflags4)


def store(dst_word_idx, data_reg):
    """Store `data_reg` to absolute output-buffer WORD index `dst_word_idx`
    (0,4,8,12 -- this experiment's slot convention). device_store's own
    `idx_off` field is in units of 4 WORDS (16 bytes), HW-VALIDATED
    EXP-0090/re-confirmed this experiment's pilot -- word_index =
    idx_off*4. CAUGHT IN THIS EXPERIMENT'S OWN SMOKE TEST (PROGRESS.md
    "pilot bug 3"): an earlier version of this helper passed the WORD
    index straight through as `idx_off`, silently writing out of the
    declared output-buffer bounds (idx_off=4 -> word16, one past a
    16-word buffer) and leaving the intended word4 slot at its
    zero-initialized default -- which looked exactly like a plausible
    but WRONG "corrupted to zero" result. `dst_word_idx` must be a
    multiple of 4."""
    assert dst_word_idx % 4 == 0, "store() takes an absolute WORD index (0,4,8,12,...), not idx_off"
    return H.device_store(R_IDX, dst_word_idx // 4, 0, data_reg=data_reg)


# ---------------------------------------------------------------------------
# MODE A program builder
# ---------------------------------------------------------------------------
def modeA_program(instrs):
    body = [H.mov_imm(R_IDX, 0)] + instrs + [H.stop()]
    prog = H.build_program(body, CARRIER_LEN)
    H.assert_round_trip(prog)   # CODEX step 10 gate: every case round-trips before it can be queued
    return prog


def case(name, group, instrs, oracle, notes, kernel="carrier", splice_pairs=None):
    """One case record. MODE A: `instrs` is a list of instruction bytes,
    `splice_pairs` is None (whole-program replace at offset 0). MODE B:
    `instrs` is None, `splice_pairs` is [(abs_offset, hex_bytes), ...] and
    `kernel` names the compiled kernel to splice into."""
    if splice_pairs is None:
        prog = modeA_program(instrs)
        splices = [(0, prog.hex())]
    else:
        splices = splice_pairs
    return {"name": name, "group": group, "kernel": kernel, "splices": splices,
            "oracle": {str(k): v for k, v in oracle.items()}, "notes": notes}


# ---------------------------------------------------------------------------
# H1 -- bits 15/31 in NEW contexts (falu2i, falu2_ext, falu3_srcmod12,
# register pressure). Baseline finding under test throughout: EXP-0099
# HW-VALIDATED that falu2's srcA_reg/srcB_reg top bit (field value 67 vs 3)
# is INERT for addressing (reads r3 either way) and for retention (only
# opflags bit19/20 controls that) -- ONLY in the register-register 6-byte
# form. This group asks: does that hold in every OTHER context a compiler
# could emit the same base-layout fields in?
# ---------------------------------------------------------------------------
def build_h1():
    cs = []
    # H1_FALU2I: srcA_reg field value {3,67} x opflags bit0 (=instr bit20 for
    # THIS family -- falu2i has no srcB, so there is only one release flag;
    # see isa_helpers.py falu2i_raw docstring on the bit19-vs-bit20 position
    # nuance) {0,1}. Producer's OWN result (word0) answers addressing;
    # reader's result (word4, ALWAYS field=3, ALWAYS retain) answers whether
    # being read via field=67 has any retention side effect.
    for X in (3, 67):
        for b in (0, 1):
            instrs = [seed_r3(),
                      H.falu2i_raw(0, X, K2, opflags4=b),
                      store(0, 0),
                      reader(1, K2),
                      store(4, 1)]
            own = V + K2   # bit15 PREDICTED inert (H1 baseline hypothesis, EXP-0099-established
                            # for the register-register form): field=67 reads r3=V here too
            later = K2 if b else V + K2        # b=1 (bit20 set) predicted to release/corrupt r3 for the LATER read
            cs.append(case("h1_falu2i_X%d_b%d" % (X, b), "H1_FALU2I", instrs,
                           {0: own, 4: later},
                           "falu2i srcA_reg=%d (bit15=%d), opflags bit0(instr bit20)=%d; "
                           "word0=own(addressing), word4=later-read(retention)" % (X, X >> 6, b)))

    # H1_FALU2EXT: same falsifier, in the 8-byte falu2_ext sibling. srcA
    # sub-group: srcB held at R_UNWRITTEN (own result = srcA_val+0, directly
    # reveals addressing). srcB sub-group: srcA held at R_UNWRITTEN (own
    # result = 0+srcB_val).
    for X in (3, 67):
        for b19 in (0, 1):
            instrs = [seed_r3(),
                      H.falu2_ext_raw(0, X, R_UNW, opflags5=b19),
                      store(0, 0),
                      reader(1, K2),
                      store(4, 1)]
            own = V + 0.0
            later = K2 if b19 else V + K2
            cs.append(case("h1_falu2ext_srcA_X%d_b19_%d" % (X, b19), "H1_FALU2EXT", instrs,
                           {0: own, 4: later},
                           "falu2_ext srcA_reg=%d(bit15=%d) srcB=UNWRITTEN, opflags bit0(bit19)=%d"
                           % (X, X >> 6, b19)))
    for Y in (3, 67):
        for b20 in (0, 1):
            instrs = [seed_r3(),
                      H.falu2_ext_raw(0, R_UNW, Y, opflags5=(b20 << 1)),
                      store(0, 0),
                      reader(1, K2),
                      store(4, 1)]
            own = 0.0 + V
            later = K2 if b20 else V + K2
            cs.append(case("h1_falu2ext_srcB_Y%d_b20_%d" % (Y, b20), "H1_FALU2EXT", instrs,
                           {0: own, 4: later},
                           "falu2_ext srcA=UNWRITTEN srcB_reg=%d(bit31=%d), opflags bit1(bit20)=%d"
                           % (Y, Y >> 6, b20)))

    # H1_FALU3SRCMOD12: 12-byte 3-source sibling. srcB held at r5=1.0
    # (multiplicative identity) so the forced-fma own-result directly
    # reveals srcA's value (pilot-confirmed: srcA=67 with srcB=r5 gives
    # 30.0, byte-for-byte matching srcA=3 -- see PROGRESS.md).
    for X in (3, 67):
        for b19 in (0, 1):
            instrs = [seed_r3(), seed_r5_one(),
                      H.falu3_srcmod12_raw(0, X, R5, opflags5=b19),
                      store(0, 0),
                      reader(1, K2),
                      store(4, 1)]
            own = V   # srcA_val * 1.0 (+ ext_srcmod-derived ~0, pilot-confirmed)
            later = K2 if b19 else V + K2
            cs.append(case("h1_falu3sm12_srcA_X%d_b19_%d" % (X, b19), "H1_FALU3SRCMOD12", instrs,
                           {0: own, 4: later},
                           "falu3_srcmod12 srcA_reg=%d(bit15=%d) srcB=r5(1.0), opflags bit0(bit19)=%d"
                           % (X, X >> 6, b19)))
    for Y in (3, 67):
        for b20 in (0, 1):
            instrs = [seed_r3(), seed_r5_one(),
                      H.falu3_srcmod12_raw(0, R5, Y, opflags5=(b20 << 1)),
                      store(0, 0),
                      reader(1, K2),
                      store(4, 1)]
            own = V   # 1.0 * srcB_val (+ ~0) -- SAME formula, commuted; NOT independently
                       # piloted for the srcB slot specifically (srcA slot was piloted) --
                       # an explicitly disclosed extrapolation, flagged in RESULTS.md if wrong.
            later = K2 if b20 else V + K2
            cs.append(case("h1_falu3sm12_srcB_Y%d_b20_%d" % (Y, b20), "H1_FALU3SRCMOD12", instrs,
                           {0: own, 4: later},
                           "falu3_srcmod12 srcA=r5(1.0) srcB_reg=%d(bit31=%d), opflags bit1(bit20)=%d "
                           "[own-result formula EXTRAPOLATED from the srcA slot's pilot-confirmed "
                           "behavior, not independently piloted for srcB]" % (Y, Y >> 6, b20)))

    # H1_PRESSURE: base falu2 (already-validated addressing), srcA field
    # {3,67} x opflags bit19 {0,1}, with 15 intervening independent
    # falu2i writes (to r6) between producer and later reader.
    for X in (3, 67):
        for b19 in (0, 1):
            dummies = [H.falu2i_raw(R6, R_UNW, H.imm_value(1.0 + i * 1.0 if (1.0 + i) <= 16 else 1.0), opflags4=0)
                       for i in range(15)]
            instrs = [seed_r3(),
                      H.falu2_raw(0, X, R_UNW, opflags5=b19)] + dummies + [
                      store(0, 0),
                      reader(1, K2),
                      store(4, 1)]
            own = V + 0.0
            later = K2 if b19 else V + K2
            cs.append(case("h1_pressure_X%d_b19_%d" % (X, b19), "H1_PRESSURE", instrs,
                           {0: own, 4: later},
                           "falu2 srcA_reg=%d(bit15=%d), opflags bit0(bit19)=%d, 15 intervening "
                           "independent writes before the later reader" % (X, X >> 6, b19)))
    return cs


# ---------------------------------------------------------------------------
# H2 -- per-family lifetime field map
# ---------------------------------------------------------------------------
def build_h2():
    cs = []

    # H2_FALU2EXT_OPFLAGS: sweep all 5 opflags bits individually on the
    # falu2_ext producer (srcA=r3, srcB=UNWRITTEN), later-read discipline.
    for bit in range(5):
        val = 1 << bit
        instrs = [seed_r3(),
                  H.falu2_ext_raw(0, R3, R_UNW, opflags5=val),
                  store(0, 0),
                  reader(1, K2),
                  store(4, 1)]
        cs.append(case("h2_falu2ext_opflags_bit%d" % bit, "H2_FALU2EXT_OPFLAGS", instrs,
                       {0: None, 4: (K2 if bit == 0 else None)},   # bit0 is the ONE falsifiable
                                              # prediction (matches falu2's own opflags bit19
                                              # contract, EXP-0086/89/99); bits1-4 EXPLORATORY,
                                              # no a priori prediction (own-result word0 also
                                              # exploratory throughout -- pilot showed it drops
                                              # to 0.0 at bits3/4, an unexplained side effect)
                       "falu2_ext opflags bit%d=1 (instr bit%d); srcA=r3,srcB=UNWRITTEN; "
                       "bit0(instr bit19) PREDICTED to corrupt word4 to %.1f matching falu2's own "
                       "contract (EXP-0086/89/99); bits1-4 EXPLORATORY, no prediction" % (bit, 19 + bit, K2)))
    instrs = [seed_r3(), H.falu2_ext_raw(0, R3, R_UNW, opflags5=0), store(0, 0), reader(1, K2), store(4, 1)]
    cs.append(case("h2_falu2ext_opflags_baseline", "H2_FALU2EXT_OPFLAGS", instrs,
                   {0: V, 4: V + K2}, "baseline, opflags=0 (retain)"))
    instrs = [seed_r3(), H.falu2_ext_raw(0, R3, R_UNW, opflags5=0), store(0, 0),
              reader(1, K2, srcA_reg=4), store(4, 1)]   # reader points at r4 (never written) -- detection PC
    cs.append(case("h2_falu2ext_opflags_positive_control", "H2_FALU2EXT_OPFLAGS", instrs,
                   {0: V, 4: K2}, "positive control: reader redirected to r4 (never written) -- "
                   "proves the harness detects a wrong-register read"))

    # H2_SRCMOD12B_NOLOOP: falu_srcmod12b (12-byte 2-source sibling), OUTSIDE
    # a loop -- separates EXP-0089's confound (was corruption-scope-widening
    # caused by the loop, or by the 12-byte FORM itself?).
    #
    # PILOT FINDING (PROGRESS.md "pilot bug/finding 5"): `opsel_mod` is an
    # UNTYPED ('mod', not a typed opcode enum) field for this family, unlike
    # falu2_ext's. This experiment's first attempt copied falu2/falu2_ext's
    # convention (opsel=4="fadd") uncritically; on real hardware, opsel=4 is
    # NOT a valid encoding for THIS family -- it corrupted an entirely
    # UNRELATED, independently-seeded register (r6) that the instruction
    # never references, decisively distinguishing "invalid encoding, broad
    # undefined corruption" from a genuine srcA-retention effect. A sweep of
    # opsel_mod 0-7 (pilot, PROGRESS.md) found opsel_mod=0 alone gives a
    # clean own-result=srcA (a move-like op) AND leaves an UNRELATED
    # register (r6) intact -- values 1,2,3,5,6,7 give a different but
    # UNRELATED-register-safe own-result (0.0), and 4 uniquely reaches
    # r6. This group therefore uses opsel_mod=0 (the one value independently
    # confirmed NOT to corrupt an unrelated register), matching this
    # experiment's own safety discipline of never generalizing a field
    # value across families without confirmation. With opsel_mod=0, the
    # opflags contract PILOT-CONFIRMED to be IDENTICAL to falu2's: bit0
    # (instr bit19) corrupts a later reader, bits1-2 do not.
    for bit, label in ((0, "opflags_bit0_b19"), (1, "opflags_bit1_b20"), (2, "opflags_bit2_b21")):
        val = 1 << bit
        instrs = [seed_r3(),
                  H.falu_srcmod12b_raw(0, R3, R_UNW, opflags5=val, opsel_mod=0),
                  store(0, 0),
                  reader(1, K2),
                  store(4, 1)]
        cs.append(case("h2_srcmod12b_noloop_%s" % label, "H2_SRCMOD12B_NOLOOP", instrs,
                       {0: V, 4: (K2 if bit == 0 else V + K2)},
                       "falu_srcmod12b (12B, NO loop, opsel_mod=0 -- the one pilot-confirmed-"
                       "benign value) opflags bit%d=1 (instr bit%d); PREDICTION (matches falu2's "
                       "own bit19/20/21 contract, pilot-CONFIRMED): bit0 corrupts word4 to %.1f, "
                       "bits1-2 leave it at %.1f" % (bit, 19 + bit, K2, V + K2)))
    instrs = [seed_r3(), H.falu_srcmod12b_raw(0, R3, R_UNW, opflags5=0, opsel_mod=0),
              store(0, 0), reader(1, K2), store(4, 1)]
    cs.append(case("h2_srcmod12b_noloop_baseline", "H2_SRCMOD12B_NOLOOP", instrs,
                   {0: V, 4: V + K2}, "baseline, opflags=0 (retain), opsel_mod=0"))
    instrs = [seed_r3(), H.falu2i_raw(R6, R_UNW, K4, opflags4=0),
              H.falu_srcmod12b_raw(0, R3, R_UNW, opflags5=0, opsel_mod=0), store(0, 0),
              reader(1, K2, srcA_reg=R6), store(4, 1)]
    cs.append(case("h2_srcmod12b_noloop_positive_control", "H2_SRCMOD12B_NOLOOP", instrs,
                   {0: V, 4: K4 + K2}, "positive control: reader redirected to r6 (separately "
                   "seeded to %.1f)" % K4))
    # SAFETY: single hang-candidate case, isolated, LAST in the whole matrix
    # (enforced by full_case_list's ordering, not here). ctrl_hi5 bit0 =
    # absolute instruction bit 34 = the SAME bit position (relative bit2 of
    # the 7-bit ctrl field) that hung the GPU in EXP-0089's loop_boundary
    # (12-byte form, INSIDE a loop). This tests whether the hang requires
    # loop repetition or is intrinsic to the 12-byte form + this bit alone.
    # Uses opsel_mod=0 (this group's confirmed-benign base) so a hang/fault,
    # if it occurs, is attributable to ctrl_hi5 alone, not to opsel=4's
    # already-confirmed separate corruption mode.
    instrs = [seed_r3(),
              H.falu_srcmod12b_raw(0, R3, R_UNW, opflags5=0, opsel_mod=0, ctrl_hi5=1),
              store(0, 0), reader(1, K2), store(4, 1)]
    cs.append(case("h2_srcmod12b_noloop_ctrl_bit2_HANGPROBE", "H2_SRCMOD12B_NOLOOP", instrs,
                   {0: None, 4: None},
                   "SAFETY: exploratory hang-candidate. ctrl_hi5 bit0 (absolute instr bit34) "
                   "flipped OUTSIDE a loop -- EXP-0089 found this exact bit position HANGS the "
                   "GPU when the SAME 12-byte form executes INSIDE a real loop (loop_boundary). "
                   "No oracle prediction; a hang/fault here is a valid, expected, first-class "
                   "result. MUST be the last case executed in the whole matrix (enforced by "
                   "full_case_list order) so a hang costs no other case's data."))

    # H2_DEVSTORE_ADDRMODE: does device_store's addr_mode bit1 (the SAME
    # 0x54/0x56 literal-bit-position mechanism, db.json's own enum) affect
    # (a) the stored memory CONTENT or (b) the source register's later ALU
    # reuse? word8 = stored content (device_store then read back via the
    # host-side buffer, no GPU re-read needed); word4 = later ALU reread.
    for addr_mode, label in ((0x54, "normal"), (0x56, "mismatched")):
        instrs = [seed_r3(),
                  H.device_store(R_IDX, 2, 0, data_reg=R3, addr_mode=addr_mode),
                  reader(1, K2),
                  store(4, 1)]
        cs.append(case("h2_devstore_addrmode_%s" % label, "H2_DEVSTORE_ADDRMODE", instrs,
                       {8: V, 4: V + K2},
                       "device_store addr_mode=0x%02x (bit1=%d, db.json: 0x54 'ALU-computed data' "
                       "vs 0x56 'direct live load-result data'); source r3 is genuinely "
                       "ALU-computed (falu2i), so 0x56 asserts a semantically WRONG class -- "
                       "does that corrupt the stored bytes (word8) or the source register's "
                       "later reuse (word4)? PREDICTION: both correct (inert), refuted by any "
                       "deviation" % (addr_mode, (addr_mode >> 1) & 1)))
    instrs = [seed_r3(), H.device_store(R_IDX, 2, 0, data_reg=R_UNW, addr_mode=0x54), reader(1, K2), store(4, 1)]
    cs.append(case("h2_devstore_addrmode_positive_control", "H2_DEVSTORE_ADDRMODE", instrs,
                   {8: 0.0, 4: V + K2},
                   "positive control: store R_UNWRITTEN instead of r3 -- proves the store "
                   "genuinely reflects its source register (word8 must read 0.0, not stale r3)"))

    # H2_CACHEBYTE_UNPACK / H2_CACHEBYTE_CVTI2F: MODE B, byte-splice into
    # the reused, recompiled, byte-identical-to-EXP-0089 anchors.
    cs += build_h2_cachebyte("lit17_unpack", "H2_CACHEBYTE_UNPACK",
                              c1_off=0x12, c1_hex="1704560401000eaa",
                              c2_off=0x1a, c2_hex="1704540001001cca",
                              field_name="cache", out_words=2,
                              baseline_oracle={"0": H.f32(0.50000763), "1": H.f32(6.0000305)})
    cs += build_h2_cachebyte("lit17_cvt", "H2_CACHEBYTE_CVTI2F",
                              c1_off=0x12, c1_hex="a707560003048e60",
                              c2_off=0x1a, c2_hex="a70754020304ac20",
                              field_name="mode", out_words=2,
                              baseline_oracle={"0": 1244.0, "1": 1254.0})
    return cs


def build_h2_cachebyte(kernel, group, c1_off, c1_hex, c2_off, c2_hex, field_name, out_words,
                        baseline_oracle):
    """MODE B splice cases for the OTHER bits (not bit1=literal bit17,
    already HW-VALIDATED corrupting by EXP-0089) of unpack_convert's `cache`
    / cvt_i2f's `mode` byte -- both proven-free 8-bit `mod` fields whose
    bit1 is the literal bit-17 mechanism. Reuses EXP-0089's exact
    compiler-emitted anchor bytes/offsets, reverified byte-identical in
    this experiment's own tree (PROGRESS.md). c1 = first/earlier reader
    (natural value has bit1=1, 0x56); c2 = second/later reader (bit1=0,
    0x54). Oracle keys are OUT WORD indices as EXP-0089 recorded them
    (kernel-specific: lit17_unpack out[0]/out[1] words 0/1; lit17_cvt same)
    -- unlike MODE A's word0/word4/word8/word12 convention, these are
    compiler-controlled compact adjacent floats, matching EXP-0089's own
    schema exactly for direct comparability."""
    cs = []

    def splice_case(name, bitmask, site, extra_note, oracle):
        rec1 = isadb.decode_one(bytes.fromhex(c1_hex), 0)[0]
        rec2 = isadb.decode_one(bytes.fromhex(c2_hex), 0)[0]
        off, hexbytes, rec = (c1_off, c1_hex, rec1) if site == "c1" else (c2_off, c2_hex, rec2)
        nat = rec["fields"][field_name]
        newval = nat ^ bitmask
        flds = dict(rec["fields"]); flds[field_name] = newval
        newhex = isadb.assemble(rec["mnemonic"], flds).hex()
        cs.append(case(name, group, None,
                       oracle,
                       "%s %s XOR 0x%02x on %s (nat=0x%02x -> 0x%02x); %s" %
                       (kernel, field_name, bitmask, site, nat, newval, extra_note),
                       kernel=kernel, splice_pairs=[(off, newhex)]))

    # baseline (no splice) -- real, falsifiable, KNOWN-IN-ADVANCE oracle
    # (EXP-0089's own recorded compiler-natural values, HW-VALIDATED,
    # re-verified byte-identical in this experiment's own recompile,
    # PROGRESS.md)
    cs.append(case("%s_baseline" % group.lower(), group, None,
                   baseline_oracle,
                   "baseline (no splice) -- oracle is EXP-0089's own recorded compiler-natural "
                   "output, re-verified byte-identical to a fresh compile of this experiment's "
                   "own copy of the kernel (baseline.py, PROGRESS.md)",
                   kernel=kernel, splice_pairs=[]))
    # Other 7 bits on c1 (earlier/producer). NOTE (found while building this
    # group): db.json's own match table for BOTH unpack_convert (bits
    # [16,1,0]+[18,6,21]) and cvt_i2f's analogous `mode` byte constrains
    # EVERY bit of this byte except bit1 as opcode-determining (i.e. by our
    # OWN model, bit1 is the only genuinely free bit -- the rest exist as a
    # `mod`-typed field label but are match-forced). XORing those bits
    # therefore produces bytes that do NOT re-decode as this family under
    # isadb (verify.py's selftest checks well-formed hex length only for
    # MODE B, not a full decode round-trip, for exactly this reason) --
    # isadb.assemble() still happily PRODUCES the requested byte pattern by
    # mnemonic name, and this experiment's own pilot confirmed the REAL
    # HARDWARE runs every one of these bytes successfully (STATUS OK,
    # matching the exact baseline output for the ones tried). This sweep is
    # therefore a genuine test of whether our DB's match-table-derived
    # "opcode-determining" classification holds on real silicon for this
    # byte, not merely a semantic-field sweep -- reported as such in
    # RESULTS.md, not silently reframed as an ordinary field test.
    for bit in range(8):
        if bit == 1:
            continue   # literal bit17, already HW-VALIDATED corrupting (EXP-0089) -- not re-tested
        splice_case("%s_c1_bit%d" % (group.lower(), bit), 1 << bit, "c1",
                    "EXPLORATORY: is this bit ALSO load-bearing like bit1, or genuinely inert "
                    "(NOTE: db.json's own match table treats this bit as opcode-determining, "
                    "not a free field -- see the comment above this loop)",
                    {"0": None, "1": None})
    # one consumer-site (c2) spot check, bit0, for polarity comparison
    splice_case("%s_c2_bit0" % group.lower(), 0x01, "c2",
                "consumer-site spot check (does flipping the LATER reader's bit0 matter, "
                "mirroring bit1's null-on-consumer polarity)",
                {"0": None, "1": None})
    # positive control: reuse EXP-0089's own raw-byte source-register redirect where it worked
    # (cvt_i2f: field 'src' +1) or, for unpack_convert (whose positive control EXP-0089 itself
    # could NOT get to detect -- disclosed limitation, not silently dropped), the SAME raw-byte
    # attempt repeated here for completeness, honestly labelled UNKNOWN going in.
    rec2 = isadb.decode_one(bytes.fromhex(c2_hex), 0)[0]
    if "src" in rec2["fields"]:
        flds = dict(rec2["fields"]); flds["src"] ^= 1
        newhex = isadb.assemble(rec2["mnemonic"], flds).hex()
        cs.append(case("%s_positive_control" % group.lower(), group, None, {"0": None, "1": None},
                       "positive control: redirect c2's src register field by 1",
                       kernel=kernel, splice_pairs=[(c2_off, newhex)]))
    else:
        b = bytearray(bytes.fromhex(c2_hex)); b[4] = (b[4] + 1) & 0xFF
        cs.append(case("%s_positive_control" % group.lower(), group, None, {"0": None, "1": None},
                       "positive control: raw byte+4 +1 (EXP-0089's own attempt for this kernel "
                       "FAILED to detect -- MATCH_EXPECTED baseline was the observed EXP-0089 "
                       "result; repeated here, honestly UNKNOWN going in, not assumed fixed)",
                       kernel=kernel, splice_pairs=[(c2_off, bytes(b).hex())]))
    return cs


# ---------------------------------------------------------------------------
# H3 -- does bit 17 generalize? ibitcount is a THIRD, structurally
# independent family (byte0=0x27, not the 0x09/0x17/0xa7 families already
# tested) whose `cache` field sits at the SAME literal bit position
# (byte+2 bit1 = instruction bit17) and is independently HW-VALIDATED for
# dst/src addressing (EXP-M4-14 direct splice; re-confirmed this
# experiment's own pilot). This group directly tests the discriminating
# question the dispatch asks for: own-result-only vs later-read vs both,
# and whether corruption (if any) reaches a THIRD, independent reader
# (the discrim3 persistence signature EXP-0089 could not build for any
# literal-bit-17 family).
# ---------------------------------------------------------------------------
def build_h3():
    cs = []
    for cache, label in ((1, "baseline"), (0, "flip")):
        instrs = [seed_r3(),
                  H.ibitcount_raw(2, R3, cache_bit17=cache),   # dst=r2 (own popcount result)
                  store(0, 2),
                  reader(1, K2),          # 1st later, independent reader
                  store(4, 1),
                  reader(4, K4),          # 2nd later, independent reader (discrim persistence)
                  store(12, 4)]
        cs.append(case("h3_ibitcount_cache_%s" % label, "H3_IBITCOUNT", instrs,
                       {0: H.bits_f32(6), 4: K2, 12: K4},   # word0 is popcount's raw u32 result (6)
                                                             # REINTERPRETED as float32 bits (a tiny
                                                             # denormal, ~8.4e-45) -- ibitcount is an
                                                             # integer op, its dst is read back through
                                                             # the SAME f32 decode as every other word
                       "ibitcount(dst=r2,src=r3,cache=%d); word0=own popcount(30.0's bits)=6 "
                       "(pilot-CONFIRMED both cache values give 6 on M4 -- CONTRADICTS "
                       "EXP-M4-14's A18 finding that cache=0/0x54 breaks the own-result to 0; "
                       "see PROGRESS.md/RESULTS.md for the direct A18-vs-M4 discrepancy, "
                       "reproduced byte-for-byte against their literal anchor); word4/word12 = "
                       "two INDEPENDENT later readers -- pilot-CONFIRMED BOTH corrupt to "
                       "read-as-zero REGARDLESS of cache, i.e. ibitcount unconditionally "
                       "releases its src operand (a discrim3-style persistence-to-a-third-"
                       "reader signature, unconditional on `cache`)" % cache))
    # positive control: ibitcount reads an unrelated, never-written register (r7) -- proves the
    # harness/own-result readback correctly reflects a DIFFERENT source (pilot: gave 0.0)
    instrs = [seed_r3(), H.ibitcount_raw(2, R7, cache_bit17=1), store(0, 2), reader(1, K2), store(4, 1)]
    cs.append(case("h3_ibitcount_positive_control", "H3_IBITCOUNT", instrs,
                   {0: 0.0, 4: V + K2},
                   "positive control: ibitcount src=r7 (never written) -- own result must be "
                   "popcount(0)=0, and r3's later read must be UNAFFECTED (r7 is a different "
                   "register) -- proves ibitcount reading an unrelated register has no effect "
                   "on r3, isolating the corruption to genuinely reading r3 itself"))
    return cs


# ---------------------------------------------------------------------------
# H4 -- mechanism discrimination
# ---------------------------------------------------------------------------
def build_h4():
    cs = []

    # H4_MEMOP_INTERVENING: does an intervening, UNRELATED, completed
    # device_store+device_load pair reset the "released" state?
    def memop_seq(corrupt, with_memop):
        instrs = [seed_r3(),
                  H.falu2i_raw(0, R3, K2, opflags4=1 if corrupt else 0),
                  store(0, 0)]
        if with_memop:
            instrs += [H.device_store(R_IDX, 3, 0, data_reg=0),   # unrelated store, word12
                       H.device_load(R9, R_IDX, 3)]                 # unrelated load back into r9 (unused)
        instrs += [reader(1, K2), store(4, 1)]
        return instrs

    for corrupt in (False, True):
        for with_memop in (False, True):
            later = (K2 if corrupt else V + K2)
            name = "h4_memop_%s_%s" % ("corrupt" if corrupt else "retain",
                                        "withmemop" if with_memop else "nomemop")
            cs.append(case(name, "H4_MEMOP_INTERVENING", memop_seq(corrupt, with_memop),
                           {0: V + K2, 4: later},
                           "producer opflags bit0=%d (corrupt=%s), %s intervening unrelated "
                           "device_store+device_load; PREDICTION: an intervening completed "
                           "memory transaction does NOT reset the release state (word4 stays "
                           "%.1f when corrupt=True, memop or not) -- pilot-CONFIRMED for the "
                           "with-memop+corrupt cell" % (1 if corrupt else 0, corrupt,
                                                          "WITH" if with_memop else "no",
                                                          K2 if corrupt else V + K2)))

    # H4_LATERWRITE_RESTORE: does a later WRITE to the same register (with
    # normal retain semantics) restore it after a corrupting read?
    def rewrite_seq(corrupt, rewrite):
        instrs = [seed_r3()]
        if corrupt:
            instrs.append(H.falu2i_raw(0, R3, K2, opflags4=1))
            instrs.append(store(0, 0))
        else:
            instrs.append(store(0, R_IDX))   # placeholder store to keep word0 defined (index-reg value, ignored)
        if rewrite:
            instrs.append(H.falu2i_raw(R3, R_UNW, K3, opflags4=0))
        instrs += [reader(1, K2), store(4, 1)]
        return instrs

    combos = [
        (False, False, V + K2, "baseline: no corrupt, no rewrite"),
        (False, True, K3 + K2, "sanity: plain rewrite (no prior corrupt) must simply take "
                                "effect -- pilot-CONFIRMED (28.0)"),
        (True, False, K2, "control: corrupt with NO rewrite -- confirms corruption present "
                           "in this exact instruction shape before adding the rewrite step"),
        (True, True, K3 + K2, "THE decisive case: corrupt THEN a fresh normal rewrite -- does "
                               "the later reader see the REWRITTEN value (restored) or stay "
                               "corrupted? PREDICTION (persistent producer-side writeback-"
                               "suppression model): RESTORED (28.0) -- pilot-CONFIRMED"),
    ]
    for corrupt, rewrite, later, note in combos:
        name = "h4_laterwrite_%s_%s" % ("corrupt" if corrupt else "retain",
                                         "rewrite" if rewrite else "norewrite")
        cs.append(case(name, "H4_LATERWRITE_RESTORE", rewrite_seq(corrupt, rewrite),
                       {4: later}, note))

    # H4_REGFILE_VS_FORWARD: after a corrupting read, does an INDEPENDENT
    # read path (device_store's data-register read, a DIFFERENT port than
    # falu2i's srcA read) also see the corruption, or does it see the real
    # value? Distinguishes "gone from the register file" (store also sees
    # corruption) from "merely not ALU-forwarded" (store sees the real
    # value; only the ALU path is affected).
    for corrupt, order in ((False, "store_then_alu"), (True, "store_then_alu"), (True, "alu_then_store")):
        instrs = [seed_r3(), H.falu2i_raw(0, R3, K2, opflags4=1 if corrupt else 0), store(0, 0)]
        if order == "store_then_alu":
            instrs += [H.device_store(R_IDX, 2, 0, data_reg=R3), reader(1, K2), store(4, 1)]
        else:
            instrs += [reader(1, K2), store(4, 1), H.device_store(R_IDX, 2, 0, data_reg=R3)]
        later = K2 if corrupt else V + K2
        cs.append(case("h4_regfile_%s_%s" % ("corrupt" if corrupt else "retain", order),
                       "H4_REGFILE_VS_FORWARD", instrs, {8: V, 4: later},
                       "corrupt=%s, order=%s; word8=device_store's OWN read of r3 (a "
                       "DIFFERENT read port than falu2i's srcA); word4=ALU later-read. "
                       "PREDICTION under 'not-forwarded, not register-file-gone': word8 stays "
                       "%.1f (correct) even when word4=%.1f (corrupted) -- refuted if word8 "
                       "also reads corrupted/zero" % (corrupt, order, V, later)))

    # H4_BARRIER: does the release survive a real threadgroup_barrier?
    def barrier():
        return isadb.assemble("threadgroup_barrier", {"sub": 4, "mem_scope": 133, "flags": 8, "b5": 0})
    for corrupt in (False, True):
        instrs = [seed_r3(),
                  H.falu2i_raw(0, R3, K2, opflags4=1 if corrupt else 0),
                  barrier(),
                  reader(1, K2),
                  store(0, 0), store(4, 1)]
        later = K2 if corrupt else V + K2
        cs.append(case("h4_barrier_%s" % ("corrupt" if corrupt else "retain"),
                       "H4_BARRIER", instrs, {0: V + K2, 4: later},
                       "producer opflags bit0=%d, REAL threadgroup_barrier(mem_device) between "
                       "producer and later reader (grid=1/tg=1, trivially satisfied); "
                       "PREDICTION: the release state SURVIVES the barrier (word4=%.1f when "
                       "corrupt=True) -- pilot-CONFIRMED" % (1 if corrupt else 0, later)))
    return cs


# ---------------------------------------------------------------------------
# whole-matrix assembly
# ---------------------------------------------------------------------------
def build_cases():
    cs = []
    cs += build_h1()
    cs += build_h2()   # includes the SRCMOD12B hang-probe -- NOT yet last; reordered below
    cs += build_h3()
    cs += build_h4()
    # positive control (whole-matrix, deliberate-mismatch detection proof, EXP-0099 precedent)
    instrs = [seed_r3(), reader(1, K2), store(4, 1)]
    cs.append(case("positive_control_deliberate_mismatch", "CONTROL", instrs,
                   {4: 999.0}, "deliberately wrong oracle (real value is %.1f) -- proves "
                   "match-detection is not a rubber stamp" % (V + K2)))
    # SAFETY: move the one hang-candidate case to the ABSOLUTE END of the matrix.
    hang_idx = next(i for i, c in enumerate(cs) if c["name"].endswith("_HANGPROBE"))
    hang_case = cs.pop(hang_idx)
    cs.append(hang_case)
    assert cs[-1]["name"].endswith("_HANGPROBE"), "hang probe is not last"
    for i, c in enumerate(cs):
        c["i"] = i
    names = [c["name"] for c in cs]
    assert len(names) == len(set(names)), "duplicate case name in casematrix"
    return cs
