#!/usr/bin/env python3
"""EXP-0146 arm table — frozen with PRE_REGISTRATION.md.

One entry per (instruction, carrier). `fields` lists the db.json field names to sweep with the
per-field value list; `bytes` lists raw byte-offset probes (relative to the instruction) used for
match-bit / raw-subbyte coverage that db.json does not expose as a field.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import oracles as O
import sweeplib as S

R8 = list(range(256))
R7 = list(range(128))
R4 = list(range(16))
R1 = [0, 1]


def carriers():
    """name -> (msl, ins, outs, out_idx, decode, oracle, tol)"""
    return {
        "u64add":     ("k_u64add.metal",   {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64}, 2, S.words64, O.oracle_u64add(),   None),
        "u64sub":     ("k_u64sub.metal",   {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64}, 2, S.words64, O.oracle_u64sub(),   None),
        "logic_and":  ("k_logic_and.metal",{0: O.pack32(O.LOGIC_A), 1: O.pack32(O.LOGIC_B)}, {2: 32}, 2, S.words32, O.oracle_logic_and(), None),
        "zext16":     ("k_zext16.metal",   {0: O.pack32(O.U32_A)}, {1: 32}, 1, S.words32, O.oracle_zext16(),  None),
        "rot_imm":    ("k_rot_imm.metal",  {0: O.pack32(O.U32_A)}, {1: 32}, 1, S.words32, O.oracle_rot_imm(), None),
        "rot_var":    ("k_rot_var.metal",  {0: O.pack32(O.U32_A), 1: O.pack32(O.U32_B)}, {2: 32}, 2, S.words32, O.oracle_rot_var(), None),
        "u64eq":      ("k_u64eq.metal",    {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 32}, 2, S.words32, O.oracle_u64eq(),   None),
        "roundmodes": ("k_roundmodes.metal", {0: O.packf32(O.F32_ROUND)}, {1: 32}, 1, S.words32, O.oracle_roundmodes(), None),
        "sfu_sin":    ("k_sfu_sin.metal",  {0: O.packf32(O.F32_SIN)}, {1: 32}, 1, S.floats32, O.oracle_sin(), 1e-3),
    }


# arm = (arm_id, instr, carrier, offset, {field: values}, {byte_rel: values}, note)
ARMS = [
    ("A_carry_gen", "carry_gen", "u64add", 0x2a,
     {"dst": R4, "subop": R8, "srcA": R8, "cmpmode": R8, "b5": R8},
     {0: R8, 2: R8},
     "byte+2 (0x35) and byte0 low nibble are db.json MATCH bits, not fields: probed raw. "
     "byte+2 = 0x00 is pre-registered falsifier F1 (EXP-0038 A18 neutralisation)."),

    ("B_ilogic", "ilogic", "logic_and", 0x20,
     {"srcA": R8, "op_base": R1, "srcB": R8, "lut_a": R8, "lut_b": R8,
      "z6": R8, "outmod": R8, "z8": R8, "z9": R8},
     {0: R8},
     "byte0 = 0x0a is pre-registered falsifier F2."),

    ("C_iadd2_64", "iadd2", "u64sub", 0x20,
     {"dst": R8, "srcA": R8, "opmode": R8, "srcB_imm": R8, "srcB_ext": R7,
      "srcB_imm_hi": R1, "opc_tail": R8, "opc_tail2": R8, "lenbit": R1,
      "srcB_reg_hi": R7, "b2_bit0": R1, "store_en": R1, "b2_fmt": list(range(64)),
      "addsub": R1},
     {0: R8},
     "the 64-bit form. byte0 0x1f -> 0x9f is pre-registered falsifier F3 (I64-01 test)."),

    ("D_irotate", "irotate", "rot_imm", 0x12,
     {"b1": R8, "b2": R8},
     {3: R8, 4: R8, 5: R8, 6: R8, 7: R8, 8: R8, 9: R8, 10: R8, 11: R8},
     "db.json models bytes +3..+7 as one 40-bit `operands` raw field and +8..+11 as a 32-bit "
     "`tail`; both are swept BYTE-WISE (FIELD-SWEEP-PROTOCOL §5)."),

    ("E_mov_zext16", "mov_zext16", "zext16", 0x12,
     {"src_reg": R7, "src_flag": R1, "subform": R8, "extend": R8},
     {0: R8},
     "byte0 = 0x12 is pre-registered falsifier F4."),

    ("F_shift_amt_move", "shift_amt_move", "rot_var", 0x4c,
     {"dst": R4, "src_reg": R7, "src_flag": R1, "kind": R8, "op_desc": R8},
     {}, ""),

    ("G_n3_mov", "n3_mov", "u64eq", 0x3c,
     {"dst": R4, "srcA_reg": R7, "srcA_uni": R1, "subform": R8, "companion": R8},
     {}, ""),

    ("H_n2_op6", "n2_op6", "u64eq", 0x32,
     {"dst": R4, "src_desc": R8, "opsel": R8, "opA": R8, "opB": R8, "imm_sel": R8},
     {}, ""),

    ("I_n2_op8", "n2_op8", "sfu_sin", 0x18,
     {"dst": R4, "srcA_desc": R8, "opsel": R8},
     {3: R8, 4: R8, 5: R8, 6: R8, 7: R8},
     "db.json models bytes +3..+7 as one 40-bit `body` raw field; swept BYTE-WISE."),

    ("J_n2_op10", "n2_op10", "roundmodes", 0x1c,
     {"dst": R4, "src": R8, "opsel": R8, "opdesc": R8},
     {4: R8, 5: R8, 6: R8, 7: R8, 8: R8, 9: R8},
     "db.json models bytes +4..+9 as one 48-bit `immword` raw field; swept BYTE-WISE."),

    ("K_sfu_marker", "sfu_marker", "sfu_sin", 0x4a,
     {},
     {0: R8, 1: R8},
     "sfu_marker declares NO fields in db.json (a byte-invariant 2-byte token); both bytes are "
     "probed raw to establish whether either carries emittable information."),

    ("L_n2_op6_sfu", "n2_op6", "sfu_sin", 0x44,
     {"dst": R4, "src_desc": R8, "opsel": R8, "opA": R8, "opB": R8, "imm_sel": R8},
     {}, "second, independent carrier for the n2_op6 catch-all (cross-carrier check)."),
]

# 2-D / paired sweeps (arm_id, instr, carrier, offset, [(fieldA, valsA), (fieldB, valsB)], note)
PAIRED = [
    ("B2_ilogic_lut2d", "ilogic", "logic_and", 0x20,
     [("lut_a", list(range(16))), ("lut_b", list(range(16))), ("op_base", R1)],
     "joint LUT-selector map: lut_a x lut_b x op_base."),
]

# functional-only carriers (baseline execution, no mutation) for the I64 answers
I64_FUNCTIONAL = [
    ("u64add", "k_u64add.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64}, 2, "words64", "oracle_u64add"),
    ("u64sub", "k_u64sub.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64}, 2, "words64", "oracle_u64sub"),
    ("s64add", "k_s64add.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64}, 2, "words64", "oracle_u64add"),
    ("s64sub", "k_s64sub.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64}, 2, "words64", "oracle_u64sub"),
    ("u64addimm", "k_u64addimm.metal", {0: O.pack64(O.U64_A)}, {1: 64}, 1, "words64", "oracle_u64addimm"),
    ("u64mul", "k_u64mul.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64}, 2, "words64", "oracle_u64mul"),
    ("u32x32to64", "k_u32x32to64.metal", {0: O.pack32(O.U32_A), 1: O.pack32(O.U32_B)}, {2: 64}, 2, "words64", "oracle_u32x32to64"),
    ("s32x32to64", "k_s32x32to64.metal", {0: O.pack32(O.U32_A), 1: O.pack32(O.U32_B)}, {2: 64}, 2, "words64", "oracle_s32x32to64"),
    ("u64and", "k_u64and.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64}, 2, "words64", "oracle_u64and"),
    ("u64cmp", "k_u64cmp.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 32}, 2, "words32", "oracle_u64lt"),
    ("s64cmp", "k_s64cmp.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 32}, 2, "words32", "oracle_s64lt"),
    ("u64eq", "k_u64eq.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 32}, 2, "words32", "oracle_u64eq"),
    ("u64min", "k_u64min.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64}, 2, "words64", "oracle_u64min"),
    ("u64shl", "k_u64shl.metal", {0: O.pack64(O.U64_A), 1: O.pack32(O.U32_B)}, {2: 64}, 2, "words64", "oracle_u64shl"),
    ("u64shr", "k_u64shr.metal", {0: O.pack64(O.U64_A), 1: O.pack32(O.U32_B)}, {2: 64}, 2, "words64", "oracle_u64shr"),
    ("u64clz", "k_u64clz.metal", {0: O.pack64(O.U64_A)}, {1: 32}, 1, "words32", "oracle_u64clz"),
    ("u64ctz", "k_u64ctz.metal", {0: O.pack64(O.U64_A)}, {1: 32}, 1, "words32", "oracle_u64ctz"),
    ("u64popcnt", "k_u64popcnt.metal", {0: O.pack64(O.U64_A)}, {1: 32}, 1, "words32", "oracle_u64popcnt"),
    ("u64sel", "k_u64sel.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B), 2: O.pack32(O.U32_B)}, {3: 64}, 3, "words64", "oracle_u64sel"),
]
