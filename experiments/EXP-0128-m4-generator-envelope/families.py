#!/usr/bin/env python3
"""EXP-0128 case families: IADD_REG (item c) and LOADSTORE_DIRECT (item a).

Both are GENERATORS in the sense that each case is built from a documented,
cited FIELD RULE (isa_helpers.py) applied to a swept parameter -- never a
copied byte string for a specific case. See RESULTS.md for the closure
verdicts these families establish, and PROGRESS.md Milestones 1-2 for the
pilot-phase decoding work that DERIVED the rules these builders encode.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402

DAG_CARRIER_LEN = 1536     # carrier_dag.metal's own compiled length is 1590B (EXP-0112, re-derived by baseline.py)
SLOT_OUT = 0
SLOT_MEM = 1
SLOT_IMEM = 2

# Deterministic, distinct float words for LOADSTORE_DIRECT (word i -> a
# value that round-trips exactly through float32 and is easy to eyeball).
MEM_WORDS = [H.f32((i + 1) * 10 + 0.5) for i in range(16)]


# ---------------------------------------------------------------------------
# IADD_REG -- iadd2 register-mode, item (c)
# ---------------------------------------------------------------------------
def _pick_idxreg(*used):
    """Return a register in {14,15} not in `used` (both are inside the
    mov_imm 4-bit-seedable range but NOT used as an operand by the caller)."""
    for cand in (15, 14):
        if cand not in used:
            return cand
    raise ValueError("no free index register")


def build_iadd_reg_positive(N, dst_reg, r0val, rNval, addsub=1):
    """dst_reg = r0 (+/-) r_N, via isa_helpers.iadd2_reg_r0_plus_rN. N in
    0..15 (mov_imm-seedable). r0val/rNval are immediates in mov_imm's own
    HW-VALIDATED safe range 0..127 (isa_helpers.mov_imm hard-rejects
    128..255 -- see its own docstring and RESULTS.md)."""
    idxreg = _pick_idxreg(0, N)
    instrs = [H.mov_imm(idxreg, 0), H.mov_imm(0, r0val)]
    if N != 0:
        instrs.append(H.mov_imm(N, rNval))
    instrs.append(H.iadd2_reg_r0_plus_rN(dst_reg, N, addsub=addsub))
    instrs.append(H.device_store(idxreg, 0, SLOT_OUT, data_reg=dst_reg))
    instrs.append(H.stop())
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    a = r0val if N != 0 else r0val  # r0 IS r_N when N==0 (self-read)
    b = rNval if N != 0 else r0val
    # addsub=1 (add): d = r0 + rN (a+b), symmetric, order-independent.
    # addsub=0 (subtract): HW-VALIDATED THIS EXPERIMENT (2 independent N
    # points, PROGRESS.md/RESULTS.md item c) -- the register-mode form
    # computes d = rN - r0 (b-a), NOT the naive "srcA-srcB"=r0-rN (a-b)
    # reading db.json's own semantics note would suggest for this field's
    # role in the IMMEDIATE-mode/anchor shape. A driver emitting subtract
    # via THIS specific tail shape (opc_tail=0x17/0x05, srcA=0xa8) must
    # swap operand order (or negate) to compensate.
    expected = H.i32(a + b) if addsub else H.i32(b - a)
    return prog.hex(), expected


def build_iadd_reg_adversarial_reghi(N, dst_reg, r0val, rNval, reg_hi_bad):
    """Deliberate rule violation: srcB_reg_hi forced nonzero (every
    HW-VALIDATED positive case uses reg_hi=0) -- predicts a WRONG (not
    r0+rN) result, expect_match=False."""
    idxreg = _pick_idxreg(0, N)
    instrs = [H.mov_imm(idxreg, 0), H.mov_imm(0, r0val)]
    if N != 0:
        instrs.append(H.mov_imm(N, rNval))
    instrs.append(H.iadd2_reg_adversarial_wrong_reghi(dst_reg, N, reg_hi_bad))
    instrs.append(H.device_store(idxreg, 0, SLOT_OUT, data_reg=dst_reg))
    instrs.append(H.stop())
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    a = r0val
    b = rNval if N != 0 else r0val
    correct = H.i32(a + b)
    return prog.hex(), correct


def build_iadd_reg_positive_control_mismatch(N, dst_reg, r0val, rNval):
    """A genuinely CORRECT construction, compared against a deliberately
    unreachable oracle -- proves match-detection is not a rubber stamp."""
    prog_hex, correct = build_iadd_reg_positive(N, dst_reg, r0val, rNval)
    bogus_oracle = H.i32(correct + 123456)
    return prog_hex, bogus_oracle


# ---------------------------------------------------------------------------
# LOADSTORE_DIRECT -- device_load -> device_store addr_mode=0x56 direct
# forward, item (a)
# ---------------------------------------------------------------------------
def build_loadstore_pair(load_idx, store_idx, load_idx_off=0, store_idx_off=0):
    """ONE load-direct-store pair. `load_idx`/`store_idx` are the DYNAMIC
    values seeded into (possibly different) index registers via mov_imm --
    the address-carrying mechanism this experiment's own pilot phase
    established (PROGRESS.md Milestone 2), NOT the idx_off immediate."""
    load_reg, store_reg = 14, 15
    instrs = [
        H.mov_imm(load_reg, load_idx & 0xF),
        H.mov_imm(store_reg, store_idx & 0xF),
        H.device_load(load_reg, load_idx_off, elem_code=3, base_slot=SLOT_MEM, extmode=0,
                       dst_lo=1, dst_ext9=1),
        H.device_store_direct(store_reg, SLOT_OUT, idx_off=store_idx_off),
        H.stop(),
    ]
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    expected_word = store_idx if store_idx_off == 0 else None  # only meaningful when idx_off=0
    correct = MEM_WORDS[load_idx]
    return prog.hex(), store_idx, correct


def build_loadstore_chained(pairs):
    """Multiple INDEPENDENT load-direct-store pairs in ONE program --
    HW-VALIDATED (this experiment's own pilot phase) NOT to hit the
    chaining hazard iadd2 register-mode does. `pairs`: list of
    (load_idx, store_idx)."""
    load_reg, store_reg = 14, 15
    instrs = []
    for load_idx, store_idx in pairs:
        instrs.append(H.mov_imm(load_reg, load_idx & 0xF))
        instrs.append(H.device_load(load_reg, 0, elem_code=3, base_slot=SLOT_MEM, extmode=0,
                                      dst_lo=1, dst_ext9=1))
        instrs.append(H.mov_imm(store_reg, store_idx & 0xF))
        instrs.append(H.device_store_direct(store_reg, SLOT_OUT, idx_off=0))
    instrs.append(H.stop())
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    oracle = {store_idx: MEM_WORDS[load_idx] for load_idx, store_idx in pairs}
    return prog.hex(), oracle


def build_loadstore_adversarial_idxoff(load_idx, store_idx, bad_side):
    """Deliberate rule violation: idx_off forced to 1 (instead of the
    required 0) on the `bad_side` ('load' or 'store') -- predicts a WRONG
    (not the forwarded value) result, per this experiment's own pilot-phase
    finding (PROGRESS.md Milestone 2)."""
    load_reg, store_reg = 14, 15
    load_off = 1 if bad_side == "load" else 0
    store_off = 1 if bad_side == "store" else 0
    instrs = [
        H.mov_imm(load_reg, load_idx & 0xF),
        H.mov_imm(store_reg, store_idx & 0xF),
        H.device_load(load_reg, load_off, elem_code=3, base_slot=SLOT_MEM, extmode=0,
                       dst_lo=1, dst_ext9=1),
        H.device_store_direct(store_reg, SLOT_OUT, idx_off=store_off),
        H.stop(),
    ]
    prog = H.build_program(instrs, DAG_CARRIER_LEN)
    H.assert_round_trip(prog)
    correct = MEM_WORDS[load_idx]
    return prog.hex(), store_idx, correct


def build_loadstore_positive_control_mismatch(load_idx, store_idx):
    prog_hex, word_idx, correct = build_loadstore_pair(load_idx, store_idx)
    bogus = H.f32(correct + 999.0)
    return prog_hex, word_idx, bogus
