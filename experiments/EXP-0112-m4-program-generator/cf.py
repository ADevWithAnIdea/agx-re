#!/usr/bin/env python3
"""EXP-0112 CF (control-flow) family.

This is NOT a general control-flow synthesizer -- no experiment in this
repository (including this one) has established that arbitrary reducible
CF shapes can be freely composed from the decoded `icmp_pred`/`if_push`/
`jump_cond`/`pop_reconverge`/`isel10` primitives the way MAIN_DAG's
dataflow nodes compose from `falu2`/`falu2i`/`device_load`/`device_store`.
What EXP-0090's own P3 program established is narrower and is exactly what
this module reuses: ONE real compiled loop-with-carried-accumulator +
if/else->select CONTROL-FLOW SKELETON, reconstructed field-by-field from a
genuine own-compile (0 byte diffs against that compile), with the loop trip
count, the branch-selecting input, and ONE structural field (`icmp_pred`
`cond`) independently variable. `build_cf_program` below is a byte-for-byte
copy of that skeleton (EXP-0090 programs.py::build_p3).

base_slot methodology note (a real mistake made and caught during this
experiment's own dry-run validation, kept here as a documented trap):
`kernels/carrier_cf.metal`'s own natural compile assigns base_slot=2 to the
FIRST load (`a[tid]`) and base_slot=1 to the SECOND (`n[tid]`) --
IDENTICAL to EXP-0090's own carrier_p3.metal, so `build_cf_program` below
uses P3's base_slot values COMPLETELY UNCHANGED. A first attempt at this
module instead SWAPPED them (1/2) based on a SEPARATE, structurally
simpler probe kernel's own compile (`out[tid]=a[tid]; out[tid+1]=
float(n[tid]);`) -- that probe is WRONG evidence for this purpose: base_slot
assignment is decided by the compiler from the WHOLE kernel body (a
trivial passthrough kernel and a real loop+branch kernel with the SAME
buffer declarations were empirically observed to get DIFFERENT internal
base_slot assignments here), not merely from buffer-argument declaration
order. The swapped version ran with real, reproducible failure signatures
on hardware (5 repeats: 4x a stable wrong value 67108864.0 = 2^26,
consistent with `n` being read from garbage causing a very large loop trip
count that saturates float32 accumulation; 1x CMDBUF_ERROR) before this was
caught and fixed. **The only reliable way to learn a carrier's own
base_slot mapping is to disassemble the CARRIER KERNEL ITSELF, in its own
exact shape** -- baseline.py does this (never a simplified stand-in probe).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402

CARRIER_LEN = 152
SLOT_OUT = 0
SLOT_A = 2     # buffer(1)=a -- own baseline.py re-derivation of carrier_cf.metal's OWN compile;
               # matches EXP-0090's carrier_p3.metal exactly (see module docstring's methodology note)
SLOT_N = 1     # buffer(2)=n


def build_cf_program(a_val, n_val, cond_override=None, liveness_violate=False):
    """a_val: float input (buffer 1). n_val: int32 loop trip count (buffer 2).
    cond_override: icmp_pred's loop-exit `cond` field (default reproduces
    the natural s_gt=6 compile; 7=s_lt inverts the guard, skipping the loop
    entirely regardless of n_val -- EXP-0090's own finding, re-labelled
    here, not re-derived).
    liveness_violate: flips the `acc*2.0` arm's opflags bit0 (ADVERSARIAL
    use only -- predicts silent corruption per EXP-0086/EXP-0090)."""
    instrs = []
    instrs.append(H.get_sr_tid(dst=0))
    instrs.append(isadb.assemble("device_load", {
        "space": 0x10, "addr_mode": 0x54, "extmode": 4, "base_slot": SLOT_A,
        "index_reg": 0, "access_desc": 0x20, "reserved7": 0, "ld_format": 0x11,
        "dst_lo": 1, "dst_ext9": 1, "idx_off": 0, "ldform_hi11": 0x10,
        "elem_size": 0x46, "reserved13": 0}))                              # r5 = a[tid] (acc)
    instrs.append(isadb.assemble("device_load", {
        "space": 0, "addr_mode": 0x44, "extmode": 2, "base_slot": SLOT_N,
        "index_reg": 0, "access_desc": 0x20, "reserved7": 0, "ld_format": 0x11,
        "dst_lo": 0, "dst_ext9": 0, "idx_off": 0, "ldform_hi11": 0x10,
        "elem_size": 0x46, "reserved13": 0}))                              # r0 = n[tid] (count)
    cond = 6 if cond_override is None else cond_override
    instrs.append(isadb.assemble("icmp_pred", {"dst_pred": 0, "srcA": 0x5, "neg": 1, "cmpmode": 2,
                                                  "opdesc_hi": 2, "srcB": 0x80, "cond": cond, "opclass": 0xC2}))
    instrs.append(isadb.assemble("if_push_pred", {"pred": 1, "scope": 0x54, "level": 1}))
    instrs.append(isadb.assemble("jump_cond", {"cf_scope": 0x54, "offset": 0x40, "reserved": 0}))
    instrs.append(isadb.assemble("reg_move_c0", {"dst": 3, "src_reg": 0, "src_flag": 0, "src_class": 2, "op_desc": 0}))
    instrs.append(isadb.assemble("if_push", {"scope": 0x54, "scope_kind": 0x1A}))
    instrs.append(isadb.assemble("iadd2", {"addsub": 1, "lenbit": 1, "srcB_reg_hi": 0, "b2_bit0": 0,
                                             "store_en": 0, "b2_fmt": 1, "dst": 6, "opmode": 3, "srcB_imm": 2,
                                             "srcB_imm_hi": 0, "srcB_ext": 0xC, "srcA": 0x88, "opc_tail": 0x15,
                                             "opc_tail2": 4}))                                      # i++
    instrs.append(isadb.assemble("icmp_pred", {"dst_pred": 0, "srcA": 0x7, "neg": 1, "cmpmode": 3,
                                                  "opdesc_hi": 2, "srcB": 5, "cond": 6, "opclass": 0}))
    instrs.append(isadb.assemble("scoreboard_fence", {"kind": 0, "scope": 0, "mask": 0}))
    instrs.append(isadb.assemble("falu2i", {"dst": 1, "imm_flag": 1, "imm_mant": 4, "imm_exp": 0xB, "opsel": 4,
                                              "imm_sign": 0, "opflags": 3, "srcA_size": 1, "srcA_reg": 1,
                                              "ctrl_lo": 0, "mods": 0}))                             # acc += 1.5
    instrs.append(isadb.assemble("ret", {"linkmode": 4, "scoreboard": 0x22}))
    instrs.append(isadb.assemble("jump", {"branch_ctrl": 0x54, "offset": (-30) & ((1 << 48) - 1), "link": 0}))
    instrs.append(isadb.assemble("pop_reconverge", {"scope": 4, "scope_kind": 2, "reserved": 0}))
    instrs.append(isadb.assemble("pop_reconverge", {"scope": 4, "scope_kind": 1, "reserved": 0}))
    arm_true_opflags = (1 if liveness_violate else 0) | (1 << 1)
    instrs.append(isadb.assemble("falu2i", {"dst": 2, "imm_flag": 1, "imm_mant": 0, "imm_exp": 0xC, "opsel": 5,
                                              "imm_sign": 0, "opflags": arm_true_opflags, "srcA_size": 1,
                                              "srcA_reg": 0x41, "ctrl_lo": 0, "mods": 0}))            # r2 = acc*2.0
    instrs.append(isadb.assemble("falu2i", {"dst": 3, "imm_flag": 1, "imm_mant": 4, "imm_exp": 0xC, "opsel": 4,
                                              "imm_sign": 1, "opflags": 2, "srcA_size": 1, "srcA_reg": 0x41,
                                              "ctrl_lo": 0, "mods": 0}))                              # r3 = acc-3.0
    instrs.append(isadb.assemble("isel10", {"dst": 1, "cmpA": 3, "opsel": 1, "cmpB": 0xC, "cmp_mode": 0x82,
                                              "selTrue": 4, "cc": 2, "flags": 2, "selFalse_file": 0x80,
                                              "selFalse": 6}))
    instrs.append(H.device_store(index_reg=0, idx_off=0, base_slot=SLOT_OUT, data_reg=1, addr_mode=0x54))
    instrs.append(H.stop())
    prog = H.build_program(instrs, CARRIER_LEN)
    H.assert_round_trip(prog)

    acc = a_val
    guard_taken = (cond == 6)
    if guard_taken:
        for _ in range(max(0, n_val)):
            acc = H.f32(acc + 1.5)
    acc_seen = 0.0 if liveness_violate else acc
    arm_true = H.f32(acc_seen * 2.0)
    arm_false = H.f32(acc_seen - 3.0)
    natural = acc_seen > 100.0
    out0 = arm_true if natural else arm_false
    return prog.hex(), out0, {"acc": acc, "natural_select_true": natural, "guard_taken": guard_taken}
