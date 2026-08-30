#!/usr/bin/env python3
"""EXP-0158 targeted families (G17P).

REGBOUNDARY  -- the device_load -> falu2i bridge with the destination register
                R swept, INCLUDING the dispatch's named boundary R = 63 and
                R = 64, plus poison controls and the extmode bit-0
                don't-care check.  Every field is synthesised.  EXP-0112 could
                not reach an arbitrary R at all except by reusing the captured
                `dst_lo`/`dst_ext9` token; EXP-0141's exact mask rules
                (`dst_lo & 3 == 1`, `dst_ext9 & 1 == 1`) replace it.
INLINEIMM    -- `falu2`'s INLINE 8-BIT FLOAT IMMEDIATE (EXP-0138 SS3), swept
                DENSE over all 64 codes.  This operand did not exist for
                EXP-0112, which had to spend a whole instruction on every
                constant.
IADD_SYNTH   -- integer add/subtract built ENTIRELY from EXP-0128/EXP-0139's
                register-mode rules: mov_imm seeds, iadd2 register mode,
                device_store.  This is the family that replaces EXP-0112's
                verbatim `iadd2_anchor`.
IADD_ANCHOR_COPIED -- EXP-0112's immediate-mode anchor, retained and tagged
                COPIED so the "still needs a donor" count is honest.
ADVERSARIAL  -- deliberate violations of the NEWLY COMPUTED rules, each
                pre-registered to fail.  If these passed, the whole synthesis
                claim would be untestable.

Every program in every family also carries the integrity SENTINEL
(synth.sentinel_instrs) and is read back out of a POISONED buffer, per
FIELD-SWEEP-PROTOCOL.md section 7.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import synth as S      # noqa: E402
import generator as G  # noqa: E402

DAG_CARRIER_LEN = G.DAG_CARRIER_LEN
SLOT_OUT = G.SLOT_OUT
SLOT_MEM = G.SLOT_MEM
SLOT_IMEM = G.SLOT_IMEM


def _finish(led, instrs, meta_extra=None):
    prog = S.build_program(led, instrs, DAG_CARRIER_LEN)
    S.assert_round_trip(prog)
    meta = {"prov_counts": led.counts(), "copied_fields": led.copied_fields(),
            "carrier_fields": led.carrier_fields(), "pilot_fields": led.pilot_fields(),
            "n_offnatural": len(led.offnatural())}
    if meta_extra:
        meta.update(meta_extra)
    return prog.hex(), meta


def _preamble(led, salt):
    """index register + integrity sentinel, in that order."""
    ins = [S.mov_imm(led, S.R_IDX, 0, salt=salt)]
    ins += S.sentinel_instrs(led, SLOT_OUT, salt)
    return ins


# ---------------------------------------------------------------------------
# REGBOUNDARY
# ---------------------------------------------------------------------------
def build_regboundary_program(mem_words, R, idx_off, salt, poison_reg=None, poison_k=30.0,
                              extmode_override=None, dst_lo_override=None,
                              dst_ext9_override=None, offnatural=True):
    """device_load into register R, then a falu2i that consumes R and stores.

    `extmode = 2*R` with bit0 a documented DON'T CARE (EXP-0141); the chooser
    deliberately sets bit0 on about half the cases, which no compiler does.
    R is reachable 0..63 only; R >= 64 is expected to silently zero/alias."""
    led = S.Ledger()
    instrs = _preamble(led, salt)
    if poison_reg is not None:
        instrs.append(S.falu2i(led, poison_reg, "fadd", S.R_UNWRITTEN, poison_k,
                               last_use_srcA=True, load_sourced=False, salt=salt + "p"))
    instrs.append(S.device_load(led, S.R_IDX, idx_off, 3, SLOT_MEM, R=R, salt=salt,
                                offnatural=offnatural, extmode_override=extmode_override,
                                dst_lo_override=dst_lo_override,
                                dst_ext9_override=dst_ext9_override))
    instrs.append(S.falu2i(led, 0, "fadd", R, 0.0, last_use_srcA=True,
                           load_sourced=True, salt=salt + "c"))
    instrs.append(S.device_store(led, S.R_IDX, 0, SLOT_OUT, data_reg=0, salt=salt,
                                 offnatural=offnatural))
    instrs.append(S.stop(led))
    byte_off = S.load_byte_offset(0, idx_off, 3)
    expected = mem_words[byte_off // 4]
    h, meta = _finish(led, instrs, {"R": R, "idx_off": idx_off})
    return h, expected, meta


# ---------------------------------------------------------------------------
# INLINEIMM -- falu2's inline 8-bit float immediate (EXP-0138 SS3)
# ---------------------------------------------------------------------------
def build_inline_imm_program(k, salt, seed=3.0, op="fadd", srcB_neg=0,
                             srcB_class_override=None, srcB_top_override=None,
                             offnatural=True):
    """r0 = seed (one falu2i);  r2 = r0 op INLINE_IMM(k);  store r2.

    The inline immediate costs NO extra instruction and NO extra register: the
    constant rides in the consuming ALU op's own srcB operand field.  That is
    the whole reason this family exists."""
    led = S.Ledger()
    instrs = _preamble(led, salt)
    instrs.append(S.falu2i(led, 0, "fadd", S.R_UNWRITTEN, seed, True, False, salt=salt + "s"))
    instrs.append(S.falu2_imm(led, 2, op, 0, None, last_use_srcA=True, salt=salt,
                              offnatural=offnatural, srcB_neg=srcB_neg,
                              srcB_class_override=srcB_class_override,
                              imm_code_override=k & 0x3F,
                              srcB_reg_top_override=srcB_top_override))
    instrs.append(S.device_store(led, S.R_IDX, 0, SLOT_OUT, data_reg=2, salt=salt,
                                 offnatural=offnatural))
    instrs.append(S.stop(led))
    b = S.inline_srcB_value(k, srcB_neg)
    a = S.imm_value(seed)
    expected = S.f32(a + b) if op == "fadd" else S.f32(a * b)
    h, meta = _finish(led, instrs, {"k": k, "srcB_neg": srcB_neg, "op": op,
                                    "imm_value": b})
    return h, expected, meta


# ---------------------------------------------------------------------------
# IADD_SYNTH -- fully synthesised integer arithmetic
# ---------------------------------------------------------------------------
def build_iadd_synth_program(A, B, N, dst_reg, addsub, salt, offnatural=True):
    """r0 = A; r_N = B; r_dst = (r0 + r_N) if addsub else (r_N - r0); store.

    N = 0 means the second operand IS r0, so the result is A+A / 0.
    All seeds go through mov_imm (7-bit immediates, EXP-0140) -- no
    device_load, so this family is independent of the load path entirely.
    NOTHING here is copied: EXP-0128 SS1.2/SS1.4 gives the operand model
    (srcA is a format byte that always reads r0; srcB_imm = 4*N selects r_N;
    addsub=0 is r_N - r0), and EXP-0139 SS1.3 gives every remaining field's
    accepted mask."""
    led = S.Ledger()
    instrs = _preamble(led, salt)
    instrs.append(S.mov_imm(led, 0, A, salt=salt + "a"))
    if N != 0:
        instrs.append(S.mov_imm(led, N, B, salt=salt + "b"))
        second = B
    else:
        second = A
    instrs.append(S.iadd2_regmode(led, dst_reg, N, addsub, salt=salt, offnatural=offnatural))
    instrs.append(S.device_store(led, S.R_IDX, 0, SLOT_OUT, data_reg=dst_reg, salt=salt,
                                 offnatural=offnatural))
    instrs.append(S.stop(led))
    # NOTE: the oracle for the integer families is a RAW 32-BIT WORD, not a
    # float.  A negative result has a bit pattern that IEEE-754 reads as NaN,
    # and NaN != NaN, so comparing it as a float would report a false failure.
    # The pilot's P9 arm hit exactly that (A=10,B=7,addsub=0 -> 0xFFFFFFFD).
    expected_int = ((A + second) if addsub else (second - A)) & 0xFFFFFFFF
    h, meta = _finish(led, instrs, {"A": A, "B": B, "N": N, "dst_reg": dst_reg,
                                    "addsub": addsub})
    return h, expected_int, meta


# ---------------------------------------------------------------------------
# IADD_ANCHOR_COPIED -- deliberately still a donor copy
# ---------------------------------------------------------------------------
def build_iadd_anchor_program(imem_words, K, idx_off, salt):
    led = S.Ledger()
    instrs = _preamble(led, salt)
    instrs.append(S.device_load(led, S.R_IDX, idx_off, 3, SLOT_IMEM, R=0, salt=salt,
                                offnatural=False, extmode_override=0))
    instrs.append(S.iadd2_immediate_anchor_COPIED(led, (K << 1) & 0xFF, dst=0))
    instrs.append(S.device_store(led, S.R_IDX, 0, SLOT_OUT, data_reg=0, salt=salt,
                                 offnatural=False))
    instrs.append(S.stop(led, offnatural=False))
    byte_off = S.load_byte_offset(0, idx_off, 3)
    raw_int = imem_words[byte_off // 4]
    addend = ((K << 1) & 0xFF) >> 1
    h, meta = _finish(led, instrs, {"K": K})
    return h, (raw_int + addend) & 0xFFFFFFFF, meta


# ---------------------------------------------------------------------------
# ADVERSARIAL -- violations of the NEWLY COMPUTED rules
# ---------------------------------------------------------------------------
def build_adv_dst_lo(mem_words, idx_off, bad_dst_lo, salt):
    """EXP-0141: dst_lo must be EXACTLY 1; 0/2/3 must silently zero the load."""
    return build_regboundary_program(mem_words, 7, idx_off, salt,
                                     dst_lo_override=bad_dst_lo)


def build_adv_dst_ext9_even(mem_words, idx_off, salt):
    """EXP-0141: dst_ext9 bit0 must be 1; all 64 even values silently zero."""
    return build_regboundary_program(mem_words, 7, idx_off, salt, dst_ext9_override=2)


def build_adv_extmode_bit7(mem_words, idx_off, salt):
    """EXP-0141: extmode bit7 must be 0; 128..255 (r64+) silently zero."""
    return build_regboundary_program(mem_words, 7, idx_off, salt,
                                     extmode_override=(7 << 1) | 0x80)


def build_adv_missing_mods(mem_words, idx_off, salt):
    """EXP-0101 H1: a falu2i consuming a load-sourced operand needs mods=0xC0.
    With mods=0 the load operand must read 0."""
    led = S.Ledger()
    instrs = _preamble(led, salt)
    instrs.append(S.device_load(led, S.R_IDX, idx_off, 3, SLOT_MEM, R=7, salt=salt))
    instrs.append(S.falu2i(led, 0, "fadd", 7, 5.0, last_use_srcA=True,
                           load_sourced=False, salt=salt + "c"))   # WRONG on purpose
    instrs.append(S.device_store(led, S.R_IDX, 0, SLOT_OUT, data_reg=0, salt=salt))
    instrs.append(S.stop(led))
    byte_off = S.load_byte_offset(0, idx_off, 3)
    correct = S.f32(mem_words[byte_off // 4] + S.imm_value(5.0))
    h, meta = _finish(led, instrs)
    return h, correct, meta


def build_adv_liveness_flip(mem_words, idx_off, salt):
    """EXP-0086/0090: the first (non-last) read wrongly marked last-use makes
    the real last read see 0."""
    led = S.Ledger()
    instrs = _preamble(led, salt)
    instrs.append(S.device_load(led, S.R_IDX, idx_off, 3, SLOT_MEM, R=9, salt=salt))
    instrs.append(S.falu2i(led, 0, "fadd", 9, 1.0, last_use_srcA=True,
                           load_sourced=True, salt=salt + "1"))
    instrs.append(S.falu2i(led, 1, "fadd", 9, 2.0, last_use_srcA=False,
                           load_sourced=True, salt=salt + "2"))
    instrs.append(S.device_store(led, S.R_IDX, 0, SLOT_OUT, data_reg=1, salt=salt))
    instrs.append(S.stop(led))
    byte_off = S.load_byte_offset(0, idx_off, 3)
    correct = S.f32(mem_words[byte_off // 4] + S.imm_value(2.0))
    h, meta = _finish(led, instrs)
    return h, correct, meta


def build_adv_iadd_dst96(A, B, N, salt):
    """EXP-0139: iadd2 `dst` register >= 96 faults reproducibly.  Built by
    hand because synth.iadd2_regmode refuses to emit it."""
    led = S.Ledger()
    instrs = _preamble(led, salt)
    instrs.append(S.mov_imm(led, 0, A, salt=salt + "a"))
    instrs.append(S.mov_imm(led, N, B, salt=salt + "b"))
    instrs.append(S.emit(led, "iadd2", {
        "addsub": S.FV(1, S.RULE, "EXP-0128"),
        "lenbit": S.FV(1, S.RULE, "EXP-0139: only 1 works"),
        "srcB_reg_hi": S.FV(0, S.FREE, "EXP-0139 INERT"),
        "b2_bit0": S.FV(0, S.FREE, "EXP-0139 INERT"),
        "store_en": S.FV(1, S.FREE, "EXP-0139 INERT"),
        "b2_fmt": S.FV(0x15, S.FREE, "EXP-0139 INERT"),
        "dst": S.FV(((96 << 1) | 1) & 0xFF, S.RULE,
                    "DELIBERATE VIOLATION of EXP-0139: dst register 96 must fault"),
        "opmode": S.FV(2, S.FREE, "EXP-0139 bit1"),
        "srcB_imm": S.FV((4 * N) & 0xFF, S.RULE, "EXP-0128 4*N"),
        "srcB_imm_hi": S.FV(0, S.RULE, "EXP-0139"),
        "srcB_ext": S.FV(0, S.FREE, "EXP-0139 0..3"),
        "srcA": S.FV(0xA8, S.FREE, "EXP-0139 bits 0,1"),
        "opc_tail": S.FV(0x17, S.FREE, "EXP-0139 bits 0,4"),
        "opc_tail2": S.FV(0x05, S.FREE, "EXP-0139 bits 0,2"),
    }))
    instrs.append(S.device_store(led, S.R_IDX, 0, SLOT_OUT, data_reg=0, salt=salt,
                                 offnatural=False))
    instrs.append(S.stop(led, offnatural=False))
    h, meta = _finish(led, instrs)
    return h, (A + B) & 0xFFFFFFFF, meta
