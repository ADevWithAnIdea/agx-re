#!/usr/bin/env python3
"""EXP-0151 seeded-register SYNTH carrier.

EXP-0139's named highest-value follow-up, built: 44 of its 64 remaining
integer-ALU fields are operand/condition selectors that a single-carrier
splice sweep proves LIVE but cannot map to registers, because every wrong
value points at a register the carrier never seeded.  This module builds the
fix -- a program in which **all sixteen mov_imm-reachable GPRs hold distinct,
host-known values** -- so a selector field's value can be DECODED to a
register number from the observed output.

Program shape (fully synthesized; nothing copied from a compiler template
except the single instruction under test, which is our own compiled MSL):

    mov_imm r0..r15 = SEED[r]          16 x 2B   (imm7 in 0..127, never 12)
    <INSTRUCTION UNDER TEST>                     (anchor bytes, one field mutated)
    device_store slot0[ r15 ] <- r6              result readback   -> out[0]
    device_store slot0[ r14 ] <- r13             INTEGRITY SENTINEL -> out[1]
    stop
    <mov_imm r12,0 padding, after stop, never executed>

`out[1]` is the FIELD-SWEEP-PROTOCOL §7 integrity sentinel on an INDEPENDENT
path: a different index register, a different data register and a different
store instruction from the one that carries the result.  If the mutated
instruction did not execute at all, or the command buffer was a victim of a
sibling experiment's fault, out[1] is not 111 and the case is quarantined
instead of being scored.

CLEAN-ROOM: every byte here is assembled by `tools/agx-isa`'s own field rules
from values HW-VALIDATED by our own prior experiments, or is the compiled form
of our own MSL.  No Apple binary is introspected.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H      # noqa: E402
import isadb                 # noqa: E402  (pulled in by isa_helpers)

M32 = 0xFFFFFFFF

CARRIER_LEN = 1536           # _agc.main length of kernels/carrier_seed.metal
SLOT_OUT = 0

R_DST = 6                    # instruction-under-test destination AND out[0] data reg
R_IDX = 15                   # out[0] store index register (content 0 -> word 0)
R_IDX2 = 14                  # out[1] store index register (content 1 -> word 1)
R_SENT = 13                  # integrity-sentinel data register
SENTINEL_DST = 97            # r6's pre-seed: unchanged => the instruction wrote elsewhere
SENTINEL_INTEGRITY = 111     # r13's value: out[1] must equal this or the case is void

# Distinct, host-known, all inside mov_imm's HW-VALIDATED 0..127 range and
# avoiding imm7 == 12 (EXP-0140: does not tokenize).  Chosen pairwise distinct
# so that an operand selector that reads rN can be identified from the output.
SEED = {0: 3, 1: 17, 2: 23, 3: 29, 4: 37, 5: 41, 6: SENTINEL_DST, 7: 53,
        8: 59, 9: 61, 10: 67, 11: 71, 12: 73, 13: SENTINEL_INTEGRITY,
        14: 1, 15: 0}
assert len(set(SEED.values())) == 16
assert all(0 <= v <= 127 and v != 12 for v in SEED.values())

# value -> [register numbers whose seed equals it]  (the decode table)
SEED_INV = {}
for _r, _v in SEED.items():
    SEED_INV.setdefault(_v, []).append(_r)


N_OUT_WORDS = 64             # r_k lands in word 4*k; word 1 is the sentinel


def seed_program(instr_bytes, dump=True):
    """Assemble the whole 1536-byte program around one instruction.

    With `dump` (the default) the program ends with a SIXTEEN-WAY REGISTER
    DUMP: `device_store` slot0[r15 + idx_off=k] <- r_k for k = 0..15, so one
    dispatch returns the ENTIRE post-instruction state of the mov_imm-reachable
    register file (r_k in output word 4*k).  That is what turns a selector
    sweep into a decode: a destination field is read off as "which register
    changed", and a source field as "which seed value appeared".

    `device_store`'s byte address is `index_reg_content*4 + idx_off*16`
    (EXP-0082/EXP-0090, our own prior HW-VALIDATED rule), so index register
    r15 (seeded 0) with idx_off = k addresses word 4*k, and index register
    r14 (seeded 1) with idx_off = 0 addresses word 1."""
    body = [H.mov_imm(r, SEED[r]) for r in range(16)]
    body.append(instr_bytes)
    if dump:
        for k in range(16):
            body.append(H.device_store(R_IDX, k, SLOT_OUT, data_reg=k))
    body.append(H.device_store(R_IDX2, 0, SLOT_OUT, data_reg=R_SENT))
    body.append(H.stop())
    return H.build_program(body, CARRIER_LEN, pad_dst=12)


def regs_from_words(words):
    """[r0..r15] out of the 64-word dump."""
    return [words[4 * k] if 4 * k < len(words) else None for k in range(16)]


def decode_register(observed):
    """Which seeded register(s) could have produced `observed` verbatim?"""
    return SEED_INV.get(observed & M32, [])
