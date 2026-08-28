#!/usr/bin/env python3
"""EXP-0112 non-DAG case families: REGBOUNDARY, IADD_ANCHOR, ADVERSARIAL.

Each builder here is still a GENERATOR in the sense that it constructs
instruction bytes from isa_helpers RULES for a caller-supplied field value
-- these are simply smaller, more targeted constructions than MAIN_DAG's
general DAG, aimed at systematic min/max/first-invalid/hole coverage of
ONE field at a time (the coordinator's scope reinforcement), rather than
broad combinatorial coverage.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
import generator as G    # noqa: E402  (shared DAG_CARRIER_LEN/SLOT_* constants)

DAG_CARRIER_LEN = G.DAG_CARRIER_LEN
SLOT_OUT = G.SLOT_OUT
SLOT_MEM = G.SLOT_MEM
SLOT_IMEM = G.SLOT_IMEM


# ---------------------------------------------------------------------------
# REGBOUNDARY -- device_load->falu2i bridge's extmode-target register R,
# swept across its full 7-bit encodable range (0..127), specifically to
# find the failure boundary the coordinator asked for: does the EXP-0099
# "register field top-bit-inert / effectively 6-bit" finding (established
# for a DIFFERENT context -- a literal, hand-forced register-index field on
# an ALREADY-GPR-resident value) also bound THIS experiment's own
# extmode-target bridge (EXP-0101 H1), which was only spot-checked at
# R in {0,3,7,16,20} and never swept past 20?
# ---------------------------------------------------------------------------
def build_regboundary_program(mem_words, R, idx_off, poison_reg=None, poison_k=999.0):
    """R: the extmode-target/consumer register (0..127). idx_off: which
    known word of MEM_WORDS to load. poison_reg: if set, pre-writes that
    register (via an ordinary const node, NOT touching R's own bridging
    fields) to a KNOWN, distinct value BEFORE the load -- lets a failure
    be classified as "reads r(R mod 64)'s poisoned content" (aliasing) vs.
    "reads 0.0" (silent zero / unwritten) vs. "reads the correct loaded
    value" (no boundary effect in this context) from the observed output
    alone, no ambiguity."""
    instrs = [H.mov_imm(H.R_IDX, 0)]
    if poison_reg is not None:
        instrs.append(H.falu2i(poison_reg, "fadd", H.R_UNWRITTEN, poison_k, last_use_srcA=True))
    instrs.append(H.device_load(H.R_IDX, idx_off, elem_code=3, base_slot=SLOT_MEM, extmode=(R << 1) & 0xFF))
    instrs.append(H.falu2i(0, "fadd", R, 0.0, last_use_srcA=True, mods=0xC0))
    instrs.append(H.device_store(H.R_IDX, 0, SLOT_OUT, data_reg=0))
    instrs.append(H.stop())
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    byte_off = H.load_byte_offset(0, idx_off, 3)
    expected = mem_words[byte_off // 4]
    return prog.hex(), expected


# ---------------------------------------------------------------------------
# IADD_ANCHOR -- EXP-0090's own verbatim device_load->iadd2->device_store
# anchor (isa_helpers.iadd2_anchor), srcB_imm swept including the K=128
# encoding-wraps-to-0 boundary this project has never independently tested
# (EXP-0090 only tried K in {0,100,127}).
# ---------------------------------------------------------------------------
def build_iadd_program(imem_words, K, idx_off):
    instrs = [
        H.mov_imm(H.R_IDX, 0),
        H.device_load(H.R_IDX, idx_off, elem_code=3, base_slot=SLOT_IMEM, extmode=0, dst_lo=1, dst_ext9=1),
        H.iadd2_anchor((K << 1) & 0xFF, dst=0),
        H.device_store(H.R_IDX, 0, SLOT_OUT, data_reg=0),
        H.stop(),
    ]
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    byte_off = H.load_byte_offset(0, idx_off, 3)
    raw_int = imem_words[byte_off // 4]
    v = (K << 1) & 0xFF
    addend = v >> 1
    expected_int = (raw_int + addend) & 0xFFFFFFFF
    return prog.hex(), H.bits_f32(expected_int)


# ---------------------------------------------------------------------------
# ADVERSARIAL -- deliberate single-rule violations, expect_match=False.
# Each `oracle` value is the CORRECT (rule-following) result; the
# construction deliberately does NOT follow the rule, so a MISMATCH is the
# predicted, correct outcome -- proves the harness/oracle detect known
# failure modes, not merely reward whatever comes back.
# ---------------------------------------------------------------------------
def build_adv_missing_mods(mem_words, idx_off):
    """falu2i consuming a load-sourced operand WITHOUT mods=0xC0 (EXP-0101
    H1: predicted silent-zero of the load-sourced operand)."""
    instrs = [
        H.mov_imm(H.R_IDX, 0),
        H.device_load(H.R_IDX, idx_off, elem_code=3, base_slot=SLOT_MEM, extmode=(7 << 1) & 0xFF),
        H.falu2i(0, "fadd", 7, 5.0, last_use_srcA=True, mods=0),   # WRONG: should be 0xC0
        H.device_store(H.R_IDX, 0, SLOT_OUT, data_reg=0),
        H.stop(),
    ]
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    byte_off = H.load_byte_offset(0, idx_off, 3)
    correct = H.f32(mem_words[byte_off // 4] + H.imm_value(5.0))
    return prog.hex(), correct


def build_adv_wrong_dsttoken(mem_words, idx_off):
    """device_load feeding falu2i via extmode, but dst_lo/dst_ext9 forced to
    (0,0) instead of the verbatim-required (1,1) (EXP-0101 H1 adversarial
    finding: predicted silent-zero)."""
    instrs = [
        H.mov_imm(H.R_IDX, 0),
        H.device_load(H.R_IDX, idx_off, elem_code=3, base_slot=SLOT_MEM, extmode=(7 << 1) & 0xFF,
                       dst_lo=0, dst_ext9=0),                       # WRONG: should be (1,1)
        H.falu2i(0, "fadd", 7, 5.0, last_use_srcA=True, mods=0xC0),
        H.device_store(H.R_IDX, 0, SLOT_OUT, data_reg=0),
        H.stop(),
    ]
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    byte_off = H.load_byte_offset(0, idx_off, 3)
    correct = H.f32(mem_words[byte_off // 4] + H.imm_value(5.0))
    return prog.hex(), correct


def build_adv_opflags1_bothreal(mem_words, idx_off1, idx_off2):
    """falu2 register-register, BOTH operands real, opflags forced to 1
    (bit0 only) instead of 3 (EXP-0090 finding_1: predicted srcB silently
    reads 0)."""
    instrs = [
        H.mov_imm(H.R_IDX, 0),
        H.device_load(H.R_IDX, idx_off1, elem_code=3, base_slot=SLOT_MEM, extmode=(3 << 1) & 0xFF),
        H.falu2i(0, "fadd", 3, 0.0, last_use_srcA=True, mods=0xC0),        # r0 = mem[idx_off1]
        H.device_load(H.R_IDX, idx_off2, elem_code=3, base_slot=SLOT_MEM, extmode=(5 << 1) & 0xFF),
        H.falu2i(1, "fadd", 5, 0.0, last_use_srcA=True, mods=0xC0),        # r1 = mem[idx_off2]
        isadb_assemble_falu2_opflags1(2, 0, 1),                            # r2 = r0+r1, opflags=1 WRONG
        H.device_store(H.R_IDX, 0, SLOT_OUT, data_reg=2),
        H.stop(),
    ]
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    b1 = H.load_byte_offset(0, idx_off1, 3)
    b2 = H.load_byte_offset(0, idx_off2, 3)
    correct = H.f32(mem_words[b1 // 4] + mem_words[b2 // 4])
    return prog.hex(), correct


def isadb_assemble_falu2_opflags1(dst, srcA_reg, srcB_reg):
    import isadb  # noqa: E402  (already on sys.path via isa_helpers import)
    return isadb.assemble("falu2", {
        "dst": dst, "srcA_size": 1, "srcA_reg": srcA_reg & 0x7F, "opsel": 4,
        "opflags": 1, "srcB_size": 1, "srcB_reg": srcB_reg & 0x7F, "ctrl": 0,
        "srcB_imm": 0, "mod_lo": 0, "srcB_neg": 0, "mod_hi": 0xC,
    })


def build_adv_liveness_flip(mem_words, idx_off):
    """Read R (via falu2i) TWICE: first read wrongly marked 'last use'
    (bit0=1), second (real last) read left bit0=0. EXP-0086/EXP-0090:
    predicted the SECOND read silently sees 0, not the loaded value."""
    instrs = [
        H.mov_imm(H.R_IDX, 0),
        H.device_load(H.R_IDX, idx_off, elem_code=3, base_slot=SLOT_MEM, extmode=(9 << 1) & 0xFF),
        H.falu2i(0, "fadd", 9, 1.0, last_use_srcA=True, mods=0xC0),   # WRONG: not actually last
        H.falu2i(1, "fadd", 9, 2.0, last_use_srcA=False, mods=0xC0),  # this IS the real last read
        H.device_store(H.R_IDX, 0, SLOT_OUT, data_reg=1),
        H.stop(),
    ]
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    byte_off = H.load_byte_offset(0, idx_off, 3)
    correct = H.f32(mem_words[byte_off // 4] + H.imm_value(2.0))
    return prog.hex(), correct
