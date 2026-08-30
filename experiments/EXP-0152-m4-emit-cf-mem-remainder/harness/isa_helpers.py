#!/usr/bin/env python3
"""EXP-0140 shared instruction-construction helpers.

Every instruction is built through `tools/agx-isa`'s READ-ONLY
`isadb.assemble(mnemonic, fields)` -- never a hand-spliced byte string.

REUSE / CITATION. The following helpers are reused VERBATIM (same field
values, same rules) from EXP-0112-m4-program-generator/isa_helpers.py and
EXP-0128-m4-generator-envelope/isa_helpers.py, which HW-VALIDATED them on
this same local M4:
  `mov_imm`, `get_sr_tid`, `device_store`, `stop`, `build_program`,
  `assert_round_trip`, `f32`, `i32`.
The CF skeleton in `cf_skeleton()` is a byte-for-byte reuse of
EXP-0112/cf.py::build_cf_program, which is itself a field-by-field
reconstruction of EXP-0090's own HW-VALIDATED P3 program (0 byte diffs
against a genuine own-compile). This experiment does NOT re-derive it and
does NOT change its instruction lengths or branch displacements: every CF
case here perturbs exactly ONE named field of ONE instruction inside that
fixed skeleton, so no displacement arithmetic is ever recomputed (the
specific hazard that safety-stopped EXP-0128's item (d)).

`mov_imm` immediates are hard-restricted to 0..127 (EXP-0128: 128..255
silently zero, and in one construction produced a real GPU hang).
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only use)


# ---------------------------------------------------------------- scalars
def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def i32(u):
    return struct.unpack("<i", struct.pack("<I", u & 0xFFFFFFFF))[0]


def u32(i):
    return struct.unpack("<I", struct.pack("<i", int(i)))[0]


# ------------------------------------------------- single-instruction ops
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8.  EXP-0112/EXP-0128 verbatim. dst is a 4-bit field
    (r0..r15); imm8 restricted to 0..127 per EXP-0128's boundary finding."""
    if not (0 <= imm8 <= 127):
        raise ValueError("mov_imm: imm8 must be 0..127 (EXP-0128 boundary hazard)")
    if not (0 <= dst <= 15):
        raise ValueError("mov_imm: dst must be 0..15 (4-bit field)")
    return isadb.assemble("mov_imm", {"dst": dst, "imm7": imm8 & 0x7F,
                                        "imm_top": (imm8 >> 7) & 1})


def mov_imm_raw(dst, imm8):
    """Same, but WITHOUT the 0..127 guard -- used only by the pre-registered
    `mov_imm.imm7/imm_top` re-confirmation controls, never by an operand seed."""
    return isadb.assemble("mov_imm", {"dst": dst & 0xF, "imm7": imm8 & 0x7F,
                                        "imm_top": (imm8 >> 7) & 1})


def get_sr_tid(dst=0, form=1, sr_sel=0xA0, dp_width=0x10, dp_marker=6, dst_hi=0):
    """4B get_sr.  Default field values are the compiler-natural ones seen in
    EVERY own-compile of a `thread_position_in_grid` read (EXP-0112 verbatim);
    this experiment sweeps `form`, `dp_width` and `dp_marker` around them."""
    return isadb.assemble("get_sr", {"form": form, "dst": dst, "sr_sel": sr_sel,
                                       "dp_width": dp_width, "dp_marker": dp_marker,
                                       "dst_hi": dst_hi})


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None,
                  space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                  st_format_ext=0, st_desc_hi=0x24, elem_size=0x11,
                  reserved7=0, reserved13=0):
    """14B device_store, ALU-forwarded form. `extmode = 2*data_reg` is
    EXP-0090's HW-VALIDATED formula (finding_5); EXP-0112/EXP-0128 verbatim.
    Byte address = content(index_reg)*4 + idx_off*16."""
    if extmode is None:
        extmode = (data_reg << 1) & 0xFF
    return isadb.assemble("device_store", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "st_format": st_format, "st_format_ext": st_format_ext,
        "idx_off": idx_off & 0x7FF, "st_desc_hi": st_desc_hi,
        "elem_size": elem_size & 0xFF, "reserved13": reserved13})


def regmove(dst, src_byte, form_byte, opdesc_byte):
    """4B  byte0 low nibble 0xB  instruction -- the family db.json splits into
    reg_move_c0 / c1 / c2var / c9 / cb / uniform_mov.  Built HERE as ONE
    instruction with four independent bytes:
        byte0 = (dst<<4) | 0x0B      byte+1 = src_byte
        byte+2 = form_byte           byte+3 = opdesc_byte
    (EXP-0087 already showed the five db.json descriptors are one
    instruction; this experiment sweeps byte+1..byte+3 to test that.)
    Assembled through isadb via whichever descriptor matches, so the
    round-trip assertion still applies."""
    b = bytes([((dst & 0xF) << 4) | 0x0B, src_byte & 0xFF,
               form_byte & 0xFF, opdesc_byte & 0xFF])
    return b


def stop():
    return isadb.assemble("stop", {"reserved": 0})


# ------------------------------------------------------- whole programs
def build_program(instrs, carrier_len, pad_dst=13):
    """EXP-0112 verbatim: concatenate, then pad to the carrier's exact
    _agc.main length with `mov_imm(pad_dst,0)` (2B) so the spliced region is
    length-exact.  Padding is placed AFTER the terminating `stop()` and is
    never executed."""
    body = b"".join(instrs)
    if len(body) > carrier_len:
        raise ValueError("program body %d bytes exceeds carrier length %d"
                          % (len(body), carrier_len))
    remainder = carrier_len - len(body)
    if remainder % 2:
        raise ValueError("odd padding remainder %d" % remainder)
    out = body + mov_imm(pad_dst, 0) * (remainder // 2)
    assert len(out) == carrier_len
    return out


def assert_round_trip(hexbytes):
    """EXP-0112 verbatim."""
    recs, leftover = isadb.disassemble(hexbytes)
    if leftover:
        raise AssertionError("round-trip: %d leftover bytes: %s"
                              % (len(leftover), leftover.hex()))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])
        want = hexbytes[off:off + r["length"]]
        if got != want:
            raise AssertionError("round-trip mismatch at +0x%x (%s): %s != %s"
                                  % (off, r["mnemonic"], got.hex(), want.hex()))
        off += r["length"]
    return recs


# ---------------------------------------------------------------------------
# CF skeleton -- byte-for-byte reuse of EXP-0112/cf.py::build_cf_program,
# itself a field-by-field reconstruction of EXP-0090's HW-VALIDATED P3
# program (0 byte diffs vs a genuine own-compile).  The instruction SEQUENCE,
# every LENGTH and both branch DISPLACEMENTS are frozen; `overrides` may
# perturb exactly one named field of one instruction, addressed by its index
# in the sequence.  Nothing recomputes a displacement (the EXP-0128 hazard).
# ---------------------------------------------------------------------------
CF_CARRIER_LEN = 152       # carrier_cf.metal (EXP-0112); re-derived by baseline.py
CF_SLOT_OUT = 0
CF_SLOT_A = 2      # buffer(1)=a   -- re-derived from the carrier's OWN compile, never assumed
CF_SLOT_N = 1      # buffer(2)=n

# Integrity sentinel (EXP-0141): every generated program writes a known value
# to a dedicated output word through a path that runs BEFORE, and is
# independent of, the instruction under test.  A dispatch that reports
# STATUS OK but never executed leaves the pre-poisoned buffer untouched, which
# on this ISA is indistinguishable from a wrong field value -- the sentinel is
# what separates them.  r14/r15 are used because the reused CF skeleton writes
# only r0,r1,r2,r3,r6 and reads r5.
SENT_VAL = 91              # must fit mov_imm's 0..127 safe range (EXP-0128)
SENT_REG_VAL = 15
SENT_REG_IDX = 14


def sentinel_prologue(slot_out, sent_idx):
    if not (0 <= sent_idx <= 127):
        raise ValueError("sentinel index must be mov_imm-seedable")
    return [mov_imm(SENT_REG_VAL, SENT_VAL),
            mov_imm(SENT_REG_IDX, sent_idx),
            device_store(SENT_REG_IDX, 0, slot_out, data_reg=SENT_REG_VAL)]


def cf_sequence(cond=6, slot_a=None, slot_n=None):
    """Returns the frozen list of (mnemonic, fields-dict) making up the
    skeleton, in program order.  EXP-0112/cf.py values, unchanged."""
    sa = CF_SLOT_A if slot_a is None else slot_a
    sn = CF_SLOT_N if slot_n is None else slot_n
    return [
        ("get_sr", {"form": 1, "dst": 0, "sr_sel": 0xA0, "dp_width": 0x10,
                     "dp_marker": 6, "dst_hi": 0}),
        ("device_load", {"space": 0x10, "addr_mode": 0x54, "extmode": 4,
                          "base_slot": sa, "index_reg": 0, "access_desc": 0x20,
                          "reserved7": 0, "ld_format": 0x11, "dst_lo": 1, "dst_ext9": 1,
                          "idx_off": 0, "ldform_hi11": 0x10, "elem_size": 0x46,
                          "reserved13": 0}),
        ("device_load", {"space": 0, "addr_mode": 0x44, "extmode": 2,
                          "base_slot": sn, "index_reg": 0, "access_desc": 0x20,
                          "reserved7": 0, "ld_format": 0x11, "dst_lo": 0, "dst_ext9": 0,
                          "idx_off": 0, "ldform_hi11": 0x10, "elem_size": 0x46,
                          "reserved13": 0}),
        ("icmp_pred", {"dst_pred": 0, "srcA": 0x5, "neg": 1, "cmpmode": 2,
                        "opdesc_hi": 2, "srcB": 0x80, "cond": cond, "opclass": 0xC2}),
        ("if_push_pred", {"pred": 1, "scope": 0x54, "level": 1}),
        ("jump_cond", {"cf_scope": 0x54, "offset": 0x40, "reserved": 0}),
        ("reg_move_c0", {"dst": 3, "src_reg": 0, "src_flag": 0, "src_class": 2,
                          "op_desc": 0}),
        ("if_push", {"scope": 0x54, "scope_kind": 0x1A}),
        ("iadd2", {"addsub": 1, "lenbit": 1, "srcB_reg_hi": 0, "b2_bit0": 0,
                    "store_en": 0, "b2_fmt": 1, "dst": 6, "opmode": 3, "srcB_imm": 2,
                    "srcB_imm_hi": 0, "srcB_ext": 0xC, "srcA": 0x88, "opc_tail": 0x15,
                    "opc_tail2": 4}),
        ("icmp_pred", {"dst_pred": 0, "srcA": 0x7, "neg": 1, "cmpmode": 3,
                        "opdesc_hi": 2, "srcB": 5, "cond": 6, "opclass": 0}),
        ("scoreboard_fence", {"kind": 0, "scope": 0, "mask": 0}),
        ("falu2i", {"dst": 1, "imm_flag": 1, "imm_mant": 4, "imm_exp": 0xB, "opsel": 4,
                     "imm_sign": 0, "opflags": 3, "srcA_size": 1, "srcA_reg": 1,
                     "ctrl_lo": 0, "mods": 0}),
        ("ret", {"linkmode": 4, "scoreboard": 0x22}),
        ("jump", {"branch_ctrl": 0x54, "offset": (-30) & ((1 << 48) - 1), "link": 0}),
        ("pop_reconverge", {"scope": 4, "scope_kind": 2, "reserved": 0}),
        ("pop_reconverge", {"scope": 4, "scope_kind": 1, "reserved": 0}),
        ("falu2i", {"dst": 2, "imm_flag": 1, "imm_mant": 0, "imm_exp": 0xC, "opsel": 5,
                     "imm_sign": 0, "opflags": 2, "srcA_size": 1, "srcA_reg": 0x01,
                     "srcA_reg_top": 1, "ctrl_lo": 0, "mods": 0}),
        ("falu2i", {"dst": 3, "imm_flag": 1, "imm_mant": 4, "imm_exp": 0xC, "opsel": 4,
                     "imm_sign": 1, "opflags": 2, "srcA_size": 1, "srcA_reg": 0x01,
                     "srcA_reg_top": 1, "ctrl_lo": 0, "mods": 0}),
        ("isel10", {"dst": 1, "cmpA": 3, "opsel": 1, "cmpB": 0xC, "cmp_mode": 0x82,
                     "selTrue": 4, "cc": 2, "flags": 2, "selFalse_file": 0x80,
                     "selFalse": 6}),
    ]


# index of each sweepable CF instruction inside cf_sequence()
CF_IDX = {"if_push_pred": 4, "jump_cond": 5, "reg_move_c0": 6, "if_push": 7,
          "ret": 12, "jump": 13, "pop_reconverge_a": 14, "pop_reconverge_b": 15}

CF_SENT_IDX = 11           # output word the CF sentinel writes (lanes use 0..7)
# NOTE (this experiment's own finding, recorded as a db_defect): a `mov_imm`
# whose 7-bit immediate is exactly 12 does NOT tokenize -- byte+1 = 0x0C makes
# the 2-byte pair look like the 4-byte `0x?c` preamble/get_sr group under the
# current length rule, and `instr_length` returns None.  It is the ONLY
# immediate in 0..127 with this property (checked exhaustively over all 16
# dst values).  Every immediate this experiment emits avoids 12.


def cf_program(cond=6, override=None, carrier_len=None, slot_a=None, slot_n=None,
                slot_out=None, sentinel=False):
    """override = (sequence_index, field_name, value) or None.

    The skeleton's instruction SEQUENCE, every LENGTH and both branch
    DISPLACEMENTS are frozen: an override perturbs exactly one named field of
    one instruction, so no displacement is ever recomputed (the hazard that
    safety-stopped EXP-0128's item (d))."""
    L = CF_CARRIER_LEN if carrier_len is None else carrier_len
    so = CF_SLOT_OUT if slot_out is None else slot_out
    seq = cf_sequence(cond, slot_a, slot_n)
    if override is not None:
        i, name, val = override
        seq[i] = (seq[i][0], dict(seq[i][1], **{name: val}))
    instrs = list(sentinel_prologue(so, CF_SENT_IDX)) if sentinel else []
    instrs += [isadb.assemble(m, f) for (m, f) in seq]
    instrs.append(device_store(index_reg=0, idx_off=0, base_slot=so,
                               data_reg=1, addr_mode=0x54))
    instrs.append(stop())
    return build_program(instrs, L)


def cf_oracle(a_val, n_val, cond=6):
    """Host-computed expected out[0], independent of the GPU.  EXP-0112 verbatim."""
    acc = a_val
    if cond == 6:
        for _ in range(max(0, n_val)):
            acc = f32(acc + 1.5)
    arm_true = f32(acc * 2.0)
    arm_false = f32(acc - 3.0)
    return arm_true if acc > 100.0 else arm_false


# ---------------------------------------------------------------------------
# EXP-0152 additions.  Everything above this line is EXP-0140's file, reused
# verbatim (which in turn reuses EXP-0112/EXP-0090).  The additions below add
# (a) multi-override + raw-byte-patch program construction, so a same-length
# variant instruction (`ret_luse` over `ret`, `mask_op` over `if_push`) can be
# spliced at a real control-flow site with NO length and NO displacement change,
# and (b) the frozen instruction-start table of the skeleton.
# ---------------------------------------------------------------------------

def cf_starts(carrier_len=None):
    """Byte offset of every instruction in the unmutated skeleton, re-derived by
    tokenizing the program we just built (never a hardcoded table)."""
    prog = cf_program(carrier_len=carrier_len)
    starts, off = [], 0
    while off < len(prog):
        rec, L = isadb.decode_one(prog, off)
        starts.append((off, rec["mnemonic"], L))
        off += L
    return starts


# Frozen expectation, asserted before every capture (baseline.py).
CF_STARTS_EXPECT = [
    (0, "get_sr", 4), (4, "device_load", 14), (18, "device_load", 14),
    (32, "icmp_pred", 6), (38, "if_push_pred", 4), (42, "jump_cond", 10),
    (52, "reg_move_c0", 4), (56, "if_push", 4), (60, "iadd2", 10),
    (70, "icmp_pred", 6), (76, "scoreboard_fence", 4), (80, "falu2i", 6),
    (86, "ret", 4), (90, "jump", 10), (100, "pop_reconverge", 6),
    (106, "pop_reconverge", 6), (112, "falu2i", 6), (118, "falu2i", 6),
    (124, "isel10", 10), (134, "device_store", 14), (148, "stop", 4),
]
CF_ADDR = {"if_push_pred": 38, "jump_cond": 42, "if_push": 56,
           "ret": 86, "jump": 90, "pop_a": 100, "pop_b": 106}


def cf_program_x(overrides=(), patches=(), carrier_len=None,
                  slot_a=None, slot_n=None, slot_out=None, cond=6):
    """Frozen skeleton with ZERO or MORE named-field overrides and ZERO or more
    raw same-length byte patches applied afterwards.

    `overrides` : iterable of (sequence_index, field_name, value)
    `patches`   : iterable of (absolute_offset_in_program, bytes)

    A patch must not change the program length -- it overwrites in place -- so
    no branch displacement is ever recomputed (the hazard that safety-stopped
    EXP-0128's item (d) and that EXP-0140 froze the skeleton to avoid)."""
    L = CF_CARRIER_LEN if carrier_len is None else carrier_len
    so = CF_SLOT_OUT if slot_out is None else slot_out
    seq = cf_sequence(cond, slot_a, slot_n)
    for (i, name, val) in overrides:
        seq[i] = (seq[i][0], dict(seq[i][1], **{name: val}))
    instrs = [isadb.assemble(m, f) for (m, f) in seq]
    instrs.append(device_store(index_reg=0, idx_off=0, base_slot=so,
                               data_reg=1, addr_mode=0x54))
    instrs.append(stop())
    prog = bytearray(build_program(instrs, L))
    for (off, blob) in patches:
        if off + len(blob) > len(prog):
            raise ValueError("patch runs past the program")
        prog[off:off + len(blob)] = blob
    if len(prog) != L:
        raise AssertionError("patch changed program length")
    return bytes(prog)
