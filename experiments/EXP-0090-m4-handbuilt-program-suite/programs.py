#!/usr/bin/env python3
"""EXP-0090 program definitions: P1 (arithmetic dataflow chain), P2 (memory
round trip), P3 (control flow), P4 (register-pressure/move). Each build_pN()
returns (program_bytes, oracle_dict, meta_dict). Every program is a
concatenation of isa_helpers.py instruction builders (each one isadb's own
assemble()), padded to an exact carrier length, then round-trip-checked.

Carrier lengths and base_slot assignments below are derived facts from our
own compiled carrier kernels (kernels/carrier_p*.metal), recorded verbatim
in PRE_REGISTRATION.md/CAPTURE_CONTRACT.json -- not re-derived here so a
toolchain drift is caught by the frozen-anchor check in run.py, not silently
swept.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / "tools" / "agx-isa"))
import isadb  # noqa: E402

# Carrier _agc.main lengths + base_slot assignments, derived from
# kernels/carrier_p1.metal / carrier_p2.metal / carrier_p4.metal (frozen in
# PRE_REGISTRATION.md; re-derived fresh by baseline.py before every capture).
CARRIER_LEN = {"p1": 520, "p2": 170, "p4": 476, "p3": 152}
SLOT_IADD = 2   # buffer(2) = iA (int32 pair), confirmed base_slot=2 by disassembling carrier_p1.metal
# every carrier below: buffer(0) = out (store base_slot=0), buffer(1) = the
# read buffer (load base_slot=1) -- confirmed by disassembling each carrier.
SLOT_OUT = 0
SLOT_IN = 1


# ---------------------------------------------------------------------------
# P1 -- arithmetic dataflow chain
# ---------------------------------------------------------------------------
def build_p1(p, k1, k2, k3, ia0, int_k, liveness_violate=False):
    """FINAL P1 design (revised after hardware falsification of the
    original register-form-heavy chain -- see RESULTS.md "srcB
    readability" finding). Every step uses ONLY the two mechanisms
    independently HW-validated by this experiment's own diagnostic probes:
      (1) falu2i: srcA reads a real prior register, srcB is a compile-time
          immediate -- reliable for ANY last_use_srcA value.
      (2) falu2 (register form) combining TWO real prior values: reliable
          ONLY with opflags=3 (both bit0 AND bit1 set) -- i.e. srcA must
          ALSO be its own last use. A `both_real=True` falu2 call with
          srcA not-last (bit0=0) FAILS (pilot31): srcB silently reads 0.
    p = [p0,p1,p2] float32 inputs, delivered as immediates fed through an
    UNWRITTEN-register-plus-immediate seed (HW-VALIDATED: an unwritten GPR
    reads exactly 0.0, EXP-0087 MOVE-04) rather than device_load -- see
    RESULTS.md's device_load-to-ALU finding (could not be independently,
    reliably bridged in the time available). k1/k2/k3 = float immediates
    (rounded through isadb.imm_encode/imm_decode, same as the oracle).
    ia0/int_k: the INDEPENDENT integer op (verbatim iadd2 anchor,
    kernels/pilot_immadd.metal, srcB_imm varied -- HW-VALIDATED, pilot22),
    writing its own out[1] slot.
    liveness_violate: flips the FIRST read of the double-read register (R1,
    read at step 5 non-last and step 9 last) from opflags bit0=0 to 1 --
    the EXP-0086 HW-VALIDATED corrupting perturbation -- predicting the
    SECOND read silently returns 0.
    """
    UNW = 50   # unwritten "seed" register (never written; HW-VALIDATED reads 0.0)
    R0, R1, R2 = 0, 1, 2
    R3, R4, R5, R6, R7, R8, R9 = 3, 4, 5, 6, 7, 8, 9
    ik_K = int_k & 0x7F   # actual added value K (0..127, fits the 8-bit srcB_imm=(K<<1) field without srcB_imm_hi)
    ik = (ik_K << 1) & 0xFF
    instrs = [
        H.mov_imm(15, 0),                                                 # r15 = 0, dedicated index register
        # -- integer op FIRST (verbatim anchor, kernels/pilot_immadd.metal),
        # ONLY srcB_imm varied -- HW-VALIDATED pilot22/pilot32 in isolation;
        # placed before the float chain so no preceding instruction can
        # perturb it -- writes an INDEPENDENT out[1] slot. --
        isadb.assemble("device_load", {"space": 0x10, "addr_mode": 0x44, "extmode": 0,
                                         "base_slot": SLOT_IADD, "index_reg": 15, "access_desc": 0x20,
                                         "reserved7": 0, "ld_format": 0x11, "dst_lo": 1, "dst_ext9": 1,
                                         "idx_off": 0, "ldform_hi11": 0x10, "elem_size": 0x46, "reserved13": 0}),
        isadb.assemble("iadd2", {"addsub": 1, "lenbit": 1, "srcB_reg_hi": 0, "b2_bit0": 0,
                                   "store_en": 1, "b2_fmt": 0x15, "dst": 0, "opmode": 2,
                                   "srcB_imm": ik, "srcB_imm_hi": 0, "srcB_ext": 0,
                                   "srcA": 0x88, "opc_tail": 0x15, "opc_tail2": 4}),
        H.device_store(index_reg=15, idx_off=1, base_slot=SLOT_OUT, data_reg=0, addr_mode=0x54),
        H.falu2i(R0, "fadd", srcA_reg=UNW, k=p[0], last_use_srcA=True),   # r0 = p0
        H.falu2i(R1, "fadd", srcA_reg=UNW, k=p[1], last_use_srcA=True),   # r1 = p1  (read twice: steps 5,9)
        H.falu2i(R2, "fadd", srcA_reg=UNW, k=p[2], last_use_srcA=True),   # r2 = p2
        H.falu2i(R3, "fadd", srcA_reg=R0, k=k1, last_use_srcA=True),      # r3 = p0+k1
        H.falu2i(R4, "fadd", srcA_reg=R1, k=0.0,
                  last_use_srcA=(False if not liveness_violate else True)),  # r4 = p1  (R1 1st/non-last read)
        H.falu2(R5, "fadd", srcA_reg=R3, srcB_reg=R4, last_use_srcA=True, both_real=True),   # r5 = r3+r4
        H.falu2i(R6, "fmul", srcA_reg=R2, k=k2, last_use_srcA=True),      # r6 = p2*k2
        H.falu2(R7, "fadd", srcA_reg=R5, srcB_reg=R6, last_use_srcA=True, both_real=True),   # r7 = r5+r6
        H.falu2i(R8, "fmul", srcA_reg=R1, k=k3, last_use_srcA=True),      # r8 = p1*k3  (R1 2nd/last read)
        H.falu2(R9, "fadd", srcA_reg=R7, srcB_reg=R8, last_use_srcA=True, both_real=True),   # r9 = r7+r8  FINAL
        H.device_store(index_reg=15, idx_off=0, base_slot=SLOT_OUT, data_reg=R9, addr_mode=0x54),
        H.stop(),
    ]
    prog = H.build_program(instrs, CARRIER_LEN["p1"])
    k1v, k2v, k3v = H.imm_value(k1), H.imm_value(k2), H.imm_value(k3)
    r3 = H.f32(p[0] + k1v)
    r4 = H.f32(p[1] + 0.0)   # R1's FIRST read (non-last) -- ALWAYS correct; flipping its OWN bit
                              # does not corrupt ITS OWN read, only a LATER read of R1 (r8 below).
    r5 = H.f32(r3 + r4)
    r6 = H.f32(p[2] * k2v)
    r7 = H.f32(r5 + r6)
    r8 = H.f32((0.0 if liveness_violate else p[1]) * k3v)   # R1's SECOND/last read -- corrupted to 0 when violated
    r9 = H.f32(r7 + r8)
    int_result = (ia0 + ik_K) & 0xFFFFFFFF
    oracle = {"out0": r9, "out1_int_bits": int_result}
    meta = {"k1v": k1v, "k2v": k2v, "k3v": k3v, "r3": r3, "r4": r4, "r5": r5, "r6": r6, "r7": r7, "r8": r8}
    return prog, oracle, meta


# ---------------------------------------------------------------------------
# P2 -- memory round trip
# ---------------------------------------------------------------------------
def build_p2(mem_words, idx_ld, off_ld, code_ld, slot_ld, idx_st, off_st,
              tk, liveness_violate=False):
    """mem_words: list of float32 values pre-filling the read buffer
    (buffer 1), enough words to cover the largest exercised byte offset.
    idx_ld/off_ld/code_ld/slot_ld: the load's index register value / idx_off
    / elem_size code / base_slot -- the exact EXP-0082/0083 fields under
    test. idx_st/off_st: the store's index/idx_off (DIFFERENT computed
    offset than the load, per the P2 spec). tk: transform immediate.
    liveness_violate: flip the transform's first read of R0 (srcA, not the
    echo's last read) to bit0=1, predicting the echo store reads 0.
    """
    # REVISED after hardware falsification of device_load -> falu2i (see
    # RESULTS.md): the load's result is bridged into the transform via the
    # SAME device_load->iadd2 anchor validated for P1's integer op
    # (kernels/pilot_immadd.metal, srcA=0x88/opc_tail=0x15/opc_tail2=4/
    # dst=0 held fixed; ONLY srcB_imm and the load's EXP-0082/0083-validated
    # fields -- index_reg, idx_off, elem_size code, base_slot -- vary). The
    # transform is therefore INTEGER add-by-immediate on the loaded value's
    # raw bits (K = tk, 0..127) rather than a float op; this still exercises
    # every targeted memory-addressing field. `liveness_violate` is not
    # applicable to this anchor (iadd2 exposes no independently-established
    # liveness bit in this experiment -- see RESULTS.md) and is accepted
    # only for API symmetry with the other three programs (no-op here).
    IDXREG_LD, IDXREG_ST = 14, 15
    tkK = tk & 0x7F
    instrs = [
        H.mov_imm(IDXREG_LD, idx_ld & 0xFF),
        H.device_load(5, index_reg=IDXREG_LD, idx_off=off_ld, elem_code=code_ld,
                       base_slot=slot_ld, addr_mode=0x44, extmode=0),
        isadb.assemble("iadd2", {"addsub": 1, "lenbit": 1, "srcB_reg_hi": 0, "b2_bit0": 0,
                                   "store_en": 1, "b2_fmt": 0x15, "dst": 0, "opmode": 2,
                                   "srcB_imm": (tkK << 1) & 0xFF, "srcB_imm_hi": 0, "srcB_ext": 0,
                                   "srcA": 0x88, "opc_tail": 0x15, "opc_tail2": 4}),
        H.mov_imm(IDXREG_ST, idx_st & 0xFF),
        H.device_store(index_reg=IDXREG_ST, idx_off=off_st, base_slot=SLOT_OUT, data_reg=0, addr_mode=0x54),
        H.stop(),
    ]
    # NOTE: an earlier two-store ("echo") version of this program was
    # DROPPED after hardware falsification -- see RESULTS.md "P2 echo
    # anomaly". A second load+iadd2+store sequence appended after the first
    # landed its store at an UNEXPECTED byte offset (consistent with
    # IDXREG_ST's value silently changing between the two mov_imm/store
    # pairs, though the exact mechanism was not isolated in the time
    # available) -- a genuine, reported negative finding, not swept under.
    # The single load-transform-store sequence below is the one independently
    # HW-validated (byte-exact, 3 reproductions) shape.
    prog = H.build_program(instrs, CARRIER_LEN["p2"])
    byte_off = H.load_byte_offset(idx_ld, off_ld, code_ld)
    word_idx = byte_off // 4
    r0_bits = struct.unpack("<I", struct.pack("<f", mem_words[word_idx]))[0] if 0 <= word_idx < len(mem_words) else 0
    r_main = (r0_bits + tkK) & 0xFFFFFFFF
    st_off_main = H.store_byte_offset(idx_st, off_st)
    oracle = {"store_byte_off_main": st_off_main, "store_val_main_bits": r_main}
    meta = {"load_byte_off": byte_off, "r0_bits": r0_bits}
    return prog, oracle, meta


# ---------------------------------------------------------------------------
# P3 -- control flow (loop w/ carried value + if/else->select join)
#
# Anchor: kernels/carrier_p3.metal, OUR OWN authored MSL, compiled+tokenized
# cleanly with tools/agx-isa (0 leftover bytes; see PRE_REGISTRATION.md for
# the full disassembly). Every field below is reproduced via isadb.assemble()
# from that disassembly (proving field-by-field reconstruction, not a byte
# copy), with ONLY the fields the field matrix targets varied:
#   - loop trip count: DATA-driven (the `n` input register), zero structural
#     risk (jump/if_push/pop_reconverge bytes untouched).
#   - if/else selection: DATA-driven (the `a` input crossing the compiled
#     100.0 threshold), same rationale.
#   - icmp_pred `cond` (the well-documented HW-VALIDATED cond enum,
#     EXP-M4-13 R6 / EXP-0013): ONE case flips the loop-exit comparison
#     direction.
#   - a deliberate liveness-bit flip (opflags bit0) on one of the two arm-
#     producing falu2i instructions, predicting the isel10 join reads a
#     corrupted (zero) value for that arm.
# ---------------------------------------------------------------------------
def build_p3(a_val, n_val, cond_override=None, liveness_violate=False):
    """a_val: float input (buffer 1). n_val: int32 loop trip count (buffer 2).
    cond_override: if set, overrides icmp_pred's loop-exit `cond` field
    (well-documented enum; default reproduces the natural s_lt=7 compile).
    liveness_violate: flips the `acc*2.0` arm's opflags bit0 (natural=0,
    corrupting value=1), predicting the isel10 join reads 0 for that arm
    when it IS the selected one (a_val chosen > 100.0 in that case)."""
    # -- exact field reproduction of kernels/carrier_p3.metal's own compile,
    # via isadb.assemble() (see PRE_REGISTRATION.md for the full anchor
    # disassembly this mirrors byte-for-byte before any override) --
    instrs = []
    instrs.append(isadb.assemble("get_sr", {"form": 1, "dst": 0, "sr_sel": 0xA0, "dp_width": 0x10,
                                              "dp_marker": 6, "dst_hi": 0}))                       # r0 = tid
    instrs.append(H.device_load(5, index_reg=0, idx_off=0, elem_code=3, base_slot=2, extmode=4,
                                  addr_mode=0x54, access_desc=0x20, space=0x10))                    # r5(dst_lo=1,dst_ext9=1) = a[tid] (acc); base_slot=2 (buffer(1) maps here, confirmed by carrier disasm)
    instrs.append(isadb.assemble("device_load", {"space": 0, "addr_mode": 0x44, "extmode": 2,
                                                    "base_slot": 1, "index_reg": 0, "access_desc": 0x20,
                                                    "reserved7": 0, "ld_format": 0x11, "dst_lo": 0, "dst_ext9": 0,
                                                    "idx_off": 0, "ldform_hi11": 0x10, "elem_size": 0x46,
                                                    "reserved13": 0}))                              # r0 = n[tid]  (count)
    cond = 6 if cond_override is None else cond_override   # 6 = s_gt (native compile)
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
    arm_true_opflags = (1 if liveness_violate else 0) | (1 << 1)   # natural=0b010 (matches the real compile exactly); violated sets bit0 -> 0b011
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
    prog = H.build_program(instrs, CARRIER_LEN["p3"])

    acc = a_val
    # cond_override changes the LOOP-ENTRY GUARD icmp_pred (byte-verbatim
    # position 0x20 in the anchor) -- OBSERVED on hardware (pilotP3/case 22),
    # NOT the arm-selection predicate as this program's docstring originally
    # (wrongly) assumed; see RESULTS.md "P3 cond field" finding. cond=6
    # (s_gt, the natural compile) takes the loop; cond=7 (s_lt) inverts the
    # guard's sense, skipping the loop body entirely (0 iterations run
    # regardless of n_val).
    guard_taken = (cond == 6)
    if guard_taken:
        for _ in range(max(0, n_val)):
            acc = H.f32(acc + 1.5)
    # liveness_violate corrupts the SHARED producer register (acc, read via
    # srcA_reg=0x41): per EXP-0086, "the earlier instruction's bit alone
    # decides" for ALL later readers -- OBSERVED on hardware (case 23) that
    # this includes NOT ONLY both arm computations but the arm-SELECTION
    # decision itself (isel10 also ends up selecting as if acc==0), not
    # merely the two arm bodies as this program's docstring originally
    # (wrongly) assumed; see RESULTS.md "P3 liveness violation" finding.
    acc_seen = 0.0 if liveness_violate else acc
    arm_true = H.f32(acc_seen * 2.0)
    arm_false = H.f32(acc_seen - 3.0)
    natural = acc_seen > 100.0
    out0 = arm_true if natural else arm_false
    oracle = {"out0": out0}
    meta = {"acc": acc, "acc_seen": acc_seen, "arm_true": arm_true, "arm_false": arm_false,
            "natural_select_true": natural, "guard_taken": guard_taken}
    return prog, oracle, meta


# ---------------------------------------------------------------------------
# P4 -- register-pressure / move program
#
# Register budget note: falu2/falu2i/reg_move_* dst is a 4-bit nibble
# (r0..r15 ONLY -- the compact-form structural cap documented in
# docs/isa/register-move-and-liveness.md section 1.1/1.4). A correct
# hand-authored rotation-by-snapshot needs 2*N_P4 live registers (N data +
# N snapshot, avoiding any read-after-write hazard) plus 2 for the
# liveness-pair probe and 1 for the zero-index register: 2*N_P4+3 <= 16
# bounds N_P4 <= 6. N_P4=6 is chosen to stress the register file (6
# simultaneously live values, matching/exceeding P1's "3+" bar) while
# staying inside the proven 16-register compact-form envelope.
# ---------------------------------------------------------------------------
N_P4 = 6
_P4_IDXREG = 15
_P4_DATA = [0, 1, 2, 3, 4, 5]
_P4_SNAP = [6, 7, 8, 9, 10, 11]
_P4_PROBE = [12, 13]


def build_p4(vals, rot=1, silent_zero_slot=None, liveness_violate=False):
    """vals: N_P4 float32 inputs (buffer 1). Loads them into r0..r5, rotates
    by `rot` positions using ONLY the EXP-0087 HW-VALIDATED move encoding
    (byte+2=0x01, op_desc=0x08, src_flag=0) via a full snapshot (r6..r11) to
    avoid any read-after-write hazard, stores the rotated values back out,
    and appends a liveness-pair probe (r12,r13 both reading r0 -- first
    non-last, second last) mirroring P1/P2.
    silent_zero_slot: if set (0..N_P4-1), that ONE move (snapshot -> final)
    is replaced by the KNOWN-silent-zeroing byte+2 family (EXP-0087
    MOVE-01) instead of the proven encoding -- an explicit negative-space
    field-matrix case; the oracle predicts that one output slot reads 0.0
    instead of its rotated value."""
    regs = _P4_DATA
    snap = _P4_SNAP
    instrs = [H.mov_imm(_P4_IDXREG, 0)]
    for i in range(N_P4):
        instrs.append(H.device_load(regs[i], index_reg=_P4_IDXREG, idx_off=i, elem_code=3,
                                      base_slot=SLOT_IN, extmode=(i * 4) & 0xFF))
    moves = []
    for i in range(N_P4):
        moves.append(H.reg_move(snap[i], regs[i]))                 # snap[i] = old regs[i]
    for i in range(N_P4):
        src_i = (i + rot) % N_P4
        if silent_zero_slot is not None and i == silent_zero_slot:
            moves.append(H.reg_move_silent_zero(regs[i], snap[src_i]))
        else:
            moves.append(H.reg_move(regs[i], snap[src_i]))
    instrs += moves
    # liveness-pair probe on the FINAL rotated regs[0] (r0): read once
    # (non-last) feeding a throwaway ALU result, then again (last) feeding
    # the real echo output -- mirrors P1/P2's proven pair.
    probe_lo, probe_hi = _P4_PROBE
    instrs.append(H.falu2i(probe_lo, "fadd", srcA_reg=regs[0], k=0.0,
                             last_use_srcA=(False if not liveness_violate else True)))
    instrs.append(H.falu2i(probe_hi, "fadd", srcA_reg=regs[0], k=0.0, last_use_srcA=True))
    for i in range(N_P4):
        instrs.append(H.device_store(index_reg=_P4_IDXREG, idx_off=i, base_slot=SLOT_OUT, data_reg=regs[i]))
    instrs.append(H.device_store(index_reg=_P4_IDXREG, idx_off=N_P4, base_slot=SLOT_OUT, data_reg=probe_hi))  # echo slot
    instrs.append(H.stop())
    prog = H.build_program(instrs, CARRIER_LEN["p4"])

    out = [vals[(i + rot) % N_P4] for i in range(N_P4)]
    if silent_zero_slot is not None:
        out[silent_zero_slot] = 0.0
    # echo reads back whatever ended up in regs[0] after the shuffle (0.0 if
    # slot 0 was the silent-zero case, else the correctly rotated value),
    # then applies the liveness-pair rule (first read non-last, second read
    # last; a violated first read zeros what the second read sees).
    r0_final = out[0]
    echo = 0.0 if liveness_violate else H.f32(r0_final + 0.0)
    oracle = {"out": out, "echo": echo}
    meta = {}
    return prog, oracle, meta
