#!/usr/bin/env python3
"""EXP-0158 CF (control-flow) family -- RETAINED AS THE HONEST NEGATIVE.

This is EXP-0090's P3 loop+if/else->select skeleton, reused byte-for-byte the
way EXP-0112 reused it.  It is NOT synthesised and this experiment does not
pretend otherwise: every control instruction's operand fields are tagged
COPIED, so every CF case lands in the "still needs a donor" bucket of the
headline count.  Keeping the family is the point -- it is how the experiment
reports an honest denominator instead of quietly dropping what it cannot
generate.

What IS computed here, and tagged RULE:
  * the two falu2i immediates (1.5, 2.0, 3.0) go through isadb's minifloat
    codec instead of being written as literal imm_mant/imm_exp nibbles;
  * the final device_store is emitted by synth.device_store from the EXP-0090
    finding_5 / EXP-0141 H10 rule (extmode = 2*data_reg).

base_slot methodology note carried over from EXP-0112: carrier_cf.metal's own
compile assigns base_slot=2 to the FIRST load (a[tid]) and 1 to the SECOND
(n[tid]).  baseline.py re-derives and ORDER-checks this from the actual
carrier, never from a simplified stand-in probe (a real hardware failure in
EXP-0112 came from exactly that mistake).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402
sys.path.insert(0, str(HERE))
import synth as S  # noqa: E402

CARRIER_LEN = 152
SLOT_OUT = 0
SLOT_A = 2
SLOT_N = 1


def _copied(led, mnemonic, fields, cite="EXP-0090 P3 skeleton (verbatim)"):
    return S.emit(led, mnemonic, {k: S.FV(v, S.COPIED, cite) for k, v in fields.items()})


def _falu2i_computed_imm(led, dst, opsel, srcA_reg, k, opflags, mods=0, ctrl_lo=0,
                         srcA_size=1, srcA_reg_top=0):
    """The skeleton's own falu2i instances, with the IMMEDIATE derived from
    isadb's minifloat codec (RULE) instead of copied nibbles.  The operand and
    modifier fields stay COPIED -- the skeleton's register choices are not
    derived from any rule."""
    b1, sign = isadb.imm_encode(k)
    return S.emit(led, "falu2i", {
        "dst": S.FV(dst, S.COPIED, "EXP-0090 P3 skeleton"),
        "imm_flag": S.FV(b1 & 1, S.RULE, "EXP-0006 minifloat codec"),
        "imm_mant": S.FV((b1 >> 1) & 0x7, S.RULE, "EXP-0006 minifloat codec"),
        "imm_exp": S.FV((b1 >> 4) & 0xF, S.RULE, "EXP-0006 minifloat codec"),
        "opsel": S.FV(opsel, S.RULE, "EXP-0005/0006 opsel enum"),
        "imm_sign": S.FV(sign & 1, S.RULE, "EXP-0006 minifloat codec"),
        "opflags": S.FV(opflags, S.COPIED, "EXP-0090 P3 skeleton"),
        "srcA_size": S.FV(srcA_size, S.RULE, "b32 operand"),
        "srcA_reg": S.FV(srcA_reg & 0x3F, S.COPIED, "EXP-0090 P3 skeleton"),
        "ctrl_lo": S.FV(ctrl_lo, S.RULE, "EXP-0119 length selector"),
        "mods": S.FV(mods, S.COPIED, "EXP-0090 P3 skeleton"),
        "srcA_reg_top": S.FV(srcA_reg_top & 1, S.COPIED, "EXP-0090 P3 skeleton"),
    })


def build_cf_program(a_val, n_val, cond_override=None, liveness_violate=False):
    led = S.Ledger()
    instrs = []
    instrs.append(_copied(led, "get_sr", {"form": 1, "dst": 0, "sr_sel": 0xA0,
                                          "dp_width": 0x10, "dp_marker": 6, "dst_hi": 0}))
    instrs.append(_copied(led, "device_load", {
        "space": 0x10, "addr_mode": 0x54, "extmode": 4, "base_slot": SLOT_A,
        "index_reg": 0, "access_desc": 0x20, "reserved7": 0, "ld_format": 0x11,
        "dst_lo": 1, "dst_ext9": 1, "idx_off": 0, "ldform_hi11": 0x10,
        "elem_size": 0x46, "reserved13": 0}))                       # r5 = a[tid]
    instrs.append(_copied(led, "device_load", {
        "space": 0, "addr_mode": 0x44, "extmode": 2, "base_slot": SLOT_N,
        "index_reg": 0, "access_desc": 0x20, "reserved7": 0, "ld_format": 0x11,
        "dst_lo": 0, "dst_ext9": 0, "idx_off": 0, "ldform_hi11": 0x10,
        "elem_size": 0x46, "reserved13": 0}))                       # r0 = n[tid]
    cond = 6 if cond_override is None else cond_override
    instrs.append(_copied(led, "icmp_pred", {"dst_pred": 0, "srcA": 0x5, "neg": 1, "cmpmode": 2,
                                             "opdesc_hi": 2, "srcB": 0x80, "cond": cond,
                                             "opclass": 0xC2}))
    instrs.append(_copied(led, "if_push_pred", {"pred": 1, "scope": 0x54, "level": 1}))
    instrs.append(_copied(led, "jump_cond", {"cf_scope": 0x54, "offset": 0x40, "reserved": 0}))
    instrs.append(_copied(led, "reg_move_c0", {"dst": 3, "src_reg": 0, "src_flag": 0,
                                               "src_class": 2, "op_desc": 0}))
    instrs.append(_copied(led, "if_push", {"scope": 0x54, "scope_kind": 0x1A}))
    instrs.append(_copied(led, "iadd2", {"addsub": 1, "lenbit": 1, "srcB_reg_hi": 0, "b2_bit0": 0,
                                         "store_en": 0, "b2_fmt": 1, "dst": 6, "opmode": 3,
                                         "srcB_imm": 2, "srcB_imm_hi": 0, "srcB_ext": 0xC,
                                         "srcA": 0x88, "opc_tail": 0x15, "opc_tail2": 4}))
    instrs.append(_copied(led, "icmp_pred", {"dst_pred": 0, "srcA": 0x7, "neg": 1, "cmpmode": 3,
                                             "opdesc_hi": 2, "srcB": 5, "cond": 6, "opclass": 0}))
    instrs.append(_copied(led, "scoreboard_fence", {"kind": 0, "scope": 0, "mask": 0}))
    instrs.append(_falu2i_computed_imm(led, dst=1, opsel=4, srcA_reg=1, k=1.5, opflags=3))
    instrs.append(_copied(led, "ret", {"linkmode": 4, "scoreboard": 0x22}))
    instrs.append(_copied(led, "jump", {"branch_ctrl": 0x54, "offset": (-30) & ((1 << 48) - 1),
                                        "link": 0}))
    instrs.append(_copied(led, "pop_reconverge", {"scope": 4, "scope_kind": 2, "reserved": 0}))
    instrs.append(_copied(led, "pop_reconverge", {"scope": 4, "scope_kind": 1, "reserved": 0}))
    arm_true_opflags = (1 if liveness_violate else 0) | (1 << 1)
    instrs.append(_falu2i_computed_imm(led, dst=2, opsel=5, srcA_reg=1, k=2.0,
                                       opflags=arm_true_opflags, srcA_reg_top=1))
    instrs.append(_falu2i_computed_imm(led, dst=3, opsel=4, srcA_reg=1, k=-3.0,
                                       opflags=2, srcA_reg_top=1))
    instrs.append(_copied(led, "isel10", {"dst": 1, "cmpA": 3, "opsel": 1, "cmpB": 0xC,
                                          "cmp_mode": 0x82, "selTrue": 4, "cc": 2, "flags": 2,
                                          "selFalse_file": 0x80, "selFalse": 6}))
    instrs.append(S.device_store(led, index_reg=0, idx_off=0, base_slot=SLOT_OUT, data_reg=1,
                                 salt="cf", offnatural=False, addr_mode_override=0x54))
    instrs.append(S.stop(led, offnatural=False))
    prog = S.build_program(led, instrs, CARRIER_LEN)
    S.assert_round_trip(prog)

    acc = a_val
    guard_taken = (cond == 6)
    if guard_taken:
        for _ in range(max(0, n_val)):
            acc = S.f32(acc + 1.5)
    acc_seen = 0.0 if liveness_violate else acc
    arm_true = S.f32(acc_seen * 2.0)
    arm_false = S.f32(acc_seen - 3.0)
    natural = acc_seen > 100.0
    out0 = arm_true if natural else arm_false
    meta = {"acc": acc, "natural_select_true": natural, "guard_taken": guard_taken,
            "prov_counts": led.counts(), "copied_fields": led.copied_fields(),
            "carrier_fields": led.carrier_fields(), "pilot_fields": led.pilot_fields(),
            "n_offnatural": len(led.offnatural())}
    return prog.hex(), out0, meta
