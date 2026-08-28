#!/usr/bin/env python3
"""EXP-0105 case matrix -- the ENC-* cluster's TOP-PRIORITY register-
addressing probe (Part II, APPLE9_RE_IMPLEMENTATION_GAPS.md, ENC-02/ENC-14,
touching ENC-01/ENC-04), plus a candidate-field sweep for the `falu2`
register-liveness family EXP-0099 left open.

Every case = ONE hand-built AGX program (concat of isa_helpers.py builders,
each a tools/agx-isa isadb.assemble() call), padded to CARRIER_LEN, spliced
over kernels/carrier.metal's compiled `_agc.main` (offset 0), executed on
real M4 hardware via tools/agxtest, and compared to an independently
computed oracle -- never derived from an observed output.

CARRIER_LEN=170 re-derived fresh by baseline.py before every capture
(byte-identical to EXP-0099's own carrier, same kernel text).

## Why this matrix is falu2/falu2i-only (a disclosed scope narrowing)

This experiment's PILOT PHASE (see PROGRESS.md) attempted a SECOND,
independent register-addressing method using `iminmax` (chosen because its
`srcA`/`srcB` fields are documented as PLAIN 8-bit register bytes,
structurally different from falu2's packed 7-bit+flags field EXP-0099
already refuted) and, separately, a `get_sr`-seeded positive-value
confirmation. Both were ABANDONED after producing evidence the pilot phase
could not interpret safely:

  - Splicing `iminmax`'s `srcA` byte, on a REAL, independently-verified-
    correct compiled `max(int,int)` kernel (own-MSL, OWN-SHADER), to EITHER
    a genuinely different IN-RANGE low register (1, holding a known-zero
    SR value) OR the r64-95 candidate (67) produced **NO CHANGE IN OUTPUT
    WHATSOEVER** -- the store kept reading the ORIGINAL "a" operand's value
    in every splice tried, with one splice value (67) additionally showing
    anomalous GPU time (~30x normal) while still reporting `STATUS OK`.
  - A hand-built (not anchor-spliced) `iminmax` program, using field values
    (`fmt`/`selhi`) empirically extracted from that SAME working compiled
    instance, could not even correctly read back a `mov_imm`-seeded LOW
    register (r3) through `iminmax` -- a construction with NO r64-95
    involvement at all, i.e. the failure is not specific to high-register
    addressing.

Neither failure mode matches any PREVIOUSLY documented hardware behavior in
this repository (not the "silent zero" pattern, not a fault, not the
known load-to-ALU blocker -- the STORE mechanism itself was independently
confirmed working via a parallel `mov_imm`-sourced control in the same
pilot session). Per CODEX step 2 ("known confounders") and the standing
"do not guess, do not assume" discipline, this is reported as an HONEST,
UNRESOLVED NEGATIVE FINDING (see PROGRESS.md / RESULTS.md "iminmax pilot
finding") rather than shipped as a gated case whose construction is not
understood well enough to interpret a MISMATCH (mismatch could mean
"register not addressed," "iminmax itself doesn't work this way," or "the
splice/harness has an iminmax-specific defect" -- these are NOT
distinguishable from the pilot's own evidence). A `get_sr`-based seeding
step (untested by this experiment on its own hardware, only cited from
EXP-0092) was also dropped from the gated matrix for the same reason: this
experiment did not have time to independently re-verify it before the
capture deadline, and stacking one not-independently-verified mechanism on
top of another not-independently-understood one (iminmax) would not have
produced an interpretable result even if built.

**What this means for TOP-PRIORITY coverage:** the register-addressing
question is answered here via a SAFE, extensively pre-validated
construction only -- falu2/falu2i, using EXACTLY EXP-0090/EXP-0099's own
proven field-value conventions -- extended to a genuinely NEW data point
EXP-0099 explicitly flagged as untested: `falu2i`'s `srcA_reg` field (the
"same annotation by structural analogy... NOT independently tested"
caveat in EXP-0099's own proposed corrections), plus a candidate-bank-bit
sweep crossed against BOTH the low (r3) and high (r67-field) register
selector. This is narrower than the dispatch's stated ambition (a second,
STRUCTURALLY DIFFERENT family) but is real, decisive, HW-tested evidence
rather than a result built on a mechanism this experiment could not get to
behave predictably in the time available. The iminmax/get_sr avenue is
reported as a concrete, well-specified lead for a successor experiment.

Design (REG64_FALU2I_ALIAS + CAND_BANK_FALU2 groups) -- EXP-0099's exact
aliasing-detection method: seed r3 via falu2i(srcA=UNWRITTEN, K), and test
srcA_reg field value 67 (low 6 bits == 3, the SAME low register r3 lives
in; register 67 itself is NEVER written by any case in this matrix, so a
"reads 0.0" result is exactly as decisive as it was in EXP-0099 -- it
means the field addressed an unwritten register, not that r3 leaked
through). CAND_BANK_FALU2 additionally sweeps candidate "separate bank
bit" fields (opflags bits22/23, mod_hi bit44, a ctrl bit walk) -- inspired
by the STRUCTURALLY ANALOGOUS `get_sr` mechanism (`dst_hi`, a register-
extension field living in a SEPARATE byte from the primary dst nibble,
HW-VALIDATED 0-95 round trip, EXP-0092) -- crossed against BOTH reg=3 (low)
and reg=67 (high) to test whether any candidate specifically UNLOCKS high
addressing (not merely "is inert at the low register").
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / "tools" / "agx-isa"))
import isadb  # noqa: E402

CARRIER_LEN = 170
SLOT_OUT = 0
OUT_WORDS = 8

R_IDX = H.R_IDX                  # 15
R_UNWRITTEN = H.R_UNWRITTEN      # 14
R_LOW = H.R_LOW                  # 3
R_HIGH_FIELD = H.R_HIGH_FIELD    # 67

V_LOW_FLOAT = H.imm_value(42.5)  # -> 30.0, ALU-seeded (EXP-0090/EXP-0099's exact fixed point)
K_ZERO = H.imm_value(0.0)        # -> 0.0, exact minifloat representable point

DEFAULT_DISPATCH = {"grid": 1, "tg": 1}


def _idx0():
    return [H.mov_imm(R_IDX, 0)]


def _store_word(idx_off, data_reg):
    return [H.device_store(R_IDX, idx_off, SLOT_OUT, data_reg, extmode=(data_reg << 1) & 0xFF)]


def _prog(instrs):
    body = b"".join(instrs) + H.stop()
    return H.build_program([body], CARRIER_LEN)


def _f32(v):
    return {"kind": "f32", "value": v}


def _case(i, name, group, instrs, oracle_words, notes, expect_match=None, dispatch=None):
    hexbytes = _prog(instrs)
    H.assert_round_trip(hexbytes)   # CODEX step 10, fail fast at build time
    return {
        "i": i, "name": name, "group": group,
        "hex": hexbytes.hex(),
        "oracle": {str(k): v for k, v in oracle_words.items()},
        "expect_match": expect_match,
        "notes": notes,
        "dispatch": dict(DEFAULT_DISPATCH if dispatch is None else dispatch),
    }


def build_cases():
    cs = []
    i = 0

    def add(name, group, instrs, oracle_words, notes, expect_match=None, dispatch=None):
        nonlocal i
        cs.append(_case(i, name, group, instrs, oracle_words, notes, expect_match, dispatch))
        i += 1

    def seed_r3():
        return _idx0() + [H.falu2i_raw(R_LOW, R_UNWRITTEN, V_LOW_FLOAT, opflags4=1)]

    # ------------------------------------------------------------------
    # SEED_CHECK -- sanity (case 0 is also the --seqtest/run.py smoke case)
    # ------------------------------------------------------------------
    add("control_r3_falu2i", "SEED_CHECK",
        seed_r3() + [H.falu2i_raw(5, R_LOW, 0.0, opflags4=1)] + _store_word(0, 5),
        {0: _f32(V_LOW_FLOAT)},
        "Seed r3=30.0 via falu2i(srcA=UNWRITTEN,K=30.0) (EXP-0090/EXP-0099's "
        "exact HW-VALIDATED ALU-only seeding technique). Read it back via "
        "falu2i(srcA_reg=3, K=0.0) -- the SAME field this experiment's "
        "decisive case varies. Expect 30.0 (r3+0.0).",
        expect_match=True)

    add("control_unwritten_falu2i", "SEED_CHECK",
        _idx0() + [H.falu2i_raw(5, R_UNWRITTEN, 0.0, opflags4=1)] + _store_word(0, 5),
        {0: _f32(0.0)},
        "srcA_reg=14 (R_UNWRITTEN, never written by ANY case in this "
        "matrix). Re-confirms EXP-0087 MOVE-04's 'unwritten GPR reads "
        "exactly 0.0' for THIS harness/carrier, independently.",
        expect_match=True)

    add("positive_control_deliberate_mismatch", "SEED_CHECK",
        seed_r3() + [H.falu2i_raw(5, R_LOW, 0.0, opflags4=1)] + _store_word(0, 5),
        {0: _f32(999.0)},
        "Same construction as control_r3_falu2i but an oracle chosen to be "
        "UNREACHABLE (30.0 != 999.0) -- proves match-detection actually "
        "detects mismatch, not a rubber stamp.",
        expect_match=False)

    # ------------------------------------------------------------------
    # REG64_FALU2I_ALIAS -- TOP PRIORITY. Closes EXP-0099's own disclosed
    # gap: "falu2i's srcA_reg (bits 25-31) should get the same annotation
    # [as falu2's] by structural analogy (not independently tested by this
    # experiment -- only the falu2 register-register form's bit15/31 were
    # tested; the analogous position in falu2i was not)." This experiment
    # tests it directly, on falu2i instead of falu2 (same family, sibling
    # instruction, IDENTICAL srcA_reg bit position per db.json: bits25-31).
    # ------------------------------------------------------------------
    add("falu2i_srca_high67_alias_DECISIVE", "REG64_FALU2I_ALIAS",
        seed_r3() + [H.falu2i_raw(5, R_HIGH_FIELD, 0.0, opflags4=1)] + _store_word(0, 5),
        {0: _f32(0.0)},
        "srcA_reg field value 67 (low 6 bits == 3, the SAME low register "
        "r3 lives in; r67 itself is NEVER written by this case, or any "
        "other case in this matrix). Oracle 0.0 is the prediction IF a "
        "genuine, wide, 7-bit register field addresses r67 (unwritten -> "
        "reads 0.0, exactly EXP-0099's own decisive signature). If instead "
        "this reads 30.0, the field ALIASES to its low 6 bits (r3), "
        "extending EXP-0099's falu2 finding to falu2i by INDEPENDENT "
        "construction (not mere structural analogy).",
        expect_match=None)

    # ------------------------------------------------------------------
    # CAND_BANK_FALU2 -- does ANY field OTHER than falu2's own reg-field
    # top bit (HW-REFUTED, EXP-0099 H1/H2) act as a get_sr-dst_hi-style
    # SEPARATE bank-select bit? Crossed against BOTH reg=3 (low, baseline)
    # and reg=67 (high field value) -- EXP-0099 only crossed the reg-field
    # top bit itself against opflags bit19/20; this experiment crosses
    # DIFFERENT candidate fields (opflags22/23, mod_hi bit44, a ctrl bit
    # walk) against the SAME high-field-value construction, asking "does
    # this candidate UNLOCK r64-95 addressing" as well as "is it inert at
    # the low register."
    # ------------------------------------------------------------------
    def bank_case(name, reg_field, opflags5, mod_hi4, ctrl, note):
        instrs = seed_r3() + [H.falu2_raw(
            5, reg_field, R_UNWRITTEN, opflags5=opflags5, mod_hi4=mod_hi4, ctrl=ctrl)]
        oracle = 0.0 if reg_field == R_HIGH_FIELD else V_LOW_FLOAT
        add(name, "CAND_BANK_FALU2",
            instrs + _store_word(0, 5),
            {0: _f32(oracle)},
            note, expect_match=None)

    bank_case("bank_low_baseline", R_LOW, 0, 0, 0,
              "Baseline @ reg=3 (top bit 0, low6=3, ALREADY HW-VALIDATED "
              "inert by EXP-0099): opflags=0, mod_hi=0, ctrl=0. Expect "
              "30.0 -- calibrates the 'no candidate active' reading all "
              "other reg=3 rows are compared against.")
    bank_case("bank_low_opflags_bit22", R_LOW, (1 << 3), 0, 0,
              "@ reg=3: candidate opflags bit22 (instr bit22, UNTESTED "
              "before this experiment; bit19/20 are the known retention "
              "bits, bit21 was HW-REFUTED as 'destination publication' by "
              "EXP-0099 H5).")
    bank_case("bank_low_opflags_bit23", R_LOW, (1 << 4), 0, 0,
              "@ reg=3: candidate opflags bit23 (the 5th/last opflags "
              "bit, UNTESTED before this experiment).")
    bank_case("bank_low_modhi_bit44", R_LOW, 0, 1, 0,
              "@ reg=3: candidate mod_hi bit44 (instr bit44, the ONE bit "
              "of the 4-bit mod_hi field EXP-0099's H4 route sweep did "
              "NOT touch -- that sweep varied bits45-47/route only).")
    for bit in (0, 1, 2, 3):
        bank_case("bank_low_ctrl_bit%d" % bit, R_LOW, 0, 0, (1 << bit),
                  "@ reg=3: candidate ctrl bit%d (instr bit%d) -- the "
                  "7-bit byte+4 'ctrl' field is WHOLLY UNTESTED before "
                  "this experiment (a 4-of-7-bit walk; bits4-6 explicitly "
                  "deferred, see RESULTS.md limitations)." % (bit, 32 + bit))

    bank_case("bank_high_baseline", R_HIGH_FIELD, 0, 0, 0,
              "@ reg=67 (field value; r67 unwritten): opflags=0, mod_hi=0, "
              "ctrl=0. Same construction as "
              "falu2i_srca_high67_alias_DECISIVE but on falu2 (register-"
              "register form) instead of falu2i -- a THIRD independent "
              "confirmation point for the same aliasing question, on the "
              "instruction EXP-0099's own H1/H2 originally used.")
    bank_case("bank_high_opflags_bit22", R_HIGH_FIELD, (1 << 3), 0, 0,
              "@ reg=67: does opflags bit22 UNLOCK high addressing (as "
              "opposed to merely being inert at reg=3, tested above)? "
              "Expect 0.0 if still inert; anything else is a genuine new "
              "finding.")
    bank_case("bank_high_opflags_bit23", R_HIGH_FIELD, (1 << 4), 0, 0,
              "@ reg=67: same question for opflags bit23.")
    bank_case("bank_high_modhi_bit44", R_HIGH_FIELD, 0, 1, 0,
              "@ reg=67: same question for mod_hi bit44.")

    return cs


if __name__ == "__main__":
    cs = build_cases()
    print("n_cases:", len(cs))
    for c in cs:
        print(c["i"], c["name"], c["group"], len(c["hex"]) // 2, "bytes",
              c["dispatch"], c["oracle"])
