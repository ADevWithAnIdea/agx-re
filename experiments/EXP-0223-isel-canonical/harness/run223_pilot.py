#!/usr/bin/env python3
"""EXP-0223 pre-freeze generated isel10 pilots."""

import random
import sys
from pathlib import Path

NEW_EXP = Path(__file__).resolve().parent.parent
REPO_EXP = NEW_EXP.parent
OLD_HARNESS = REPO_EXP / "EXP-0220-canonical-recipes" / "harness"
if not OLD_HARNESS.exists():
    OLD_HARNESS = REPO_EXP / "EXP-0220" / "harness"
sys.path.insert(0, str(OLD_HARNESS))

import cases220 as C  # noqa: E402
import prog220 as P  # noqa: E402
import run220 as R  # noqa: E402
import synth220 as S  # noqa: E402


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0223 PRE_REGISTRATION", note)


def packed(reg, packing):
    if packing == "h1":
        return reg
    if packing == "h2":
        return (reg << 1) | 1
    if packing == "h3":
        return reg << 2
    raise ValueError(packing)


def emit_isel(pg, dst, cmp_a, cmp_b, sel_true, sel_false, packing,
              model_cmp_a=None, model_cmp_b=None):
    pg.E.emit("isel10", {
        "dst": fv(dst, "destination GPR candidate"),
        "cmpA": fv(packed(cmp_a, packing), f"{packing} compare-A selector"),
        "opsel": fv(0, "lowest structural ten-byte member"),
        "cmpB": fv(packed(cmp_b, packing), f"{packing} compare-B selector"),
        "cmp_mode": fv(0x81, "signed less-than mode hypothesis"),
        "selTrue": fv(packed(sel_true, packing), f"{packing} true selector"),
        "cc": fv(0x07, "signed less-than condition hypothesis"),
        "flags": fv(0, "canonical lifecycle candidate"),
        "selFalse_file": fv(0, "GPR false-source candidate"),
        "selFalse": fv(packed(sel_false, packing), f"{packing} false selector"),
    })
    pg._pending = None
    ma = cmp_a if model_cmp_a is None else model_cmp_a
    mb = cmp_b if model_cmp_b is None else model_cmp_b
    av, bv = pg.rbits(ma), pg.rbits(mb)
    tv, fv_bits = pg.rbits(sel_true), pg.rbits(sel_false)
    out = None if None in (av, bv, tv, fv_bits) else (tv if av < bv else fv_bits)
    pg.set_reg(dst, out)


def signed32(value):
    return value - (1 << 32) if value & 0x80000000 else value


def model_predicate(kind, a, b):
    if kind == "slt":
        return signed32(a) < signed32(b)
    if kind == "sgt":
        return signed32(a) > signed32(b)
    if kind == "ult":
        return a < b
    if kind == "ugt":
        return a > b
    if kind == "eq":
        return a == b
    if kind == "flt":
        return S.bits_f32(a) < S.bits_f32(b)
    if kind == "fgt":
        return S.bits_f32(a) > S.bits_f32(b)
    if kind == "feq":
        return S.bits_f32(a) == S.bits_f32(b)
    raise ValueError(kind)


def emit_isel_r1(pg, dst, cmp_a, cmp_b, sel_true, sel_false, cond, flags=0xC0,
                 opsel=0,
                 cc_value=None, cmp_mode=0x02, sel_false_file=0,
                 model_cmp_a=None, model_cmp_b=None, model_sel_true=None,
                 model_sel_false=None, model_kind=None):
    pg.E.emit("isel10", {
        "dst": fv(dst, "R1 destination GPR"),
        "cmpA": fv((cmp_a << 1) | 1, "R1 compare-A descriptor"),
        "opsel": fv(opsel, "R1 member; AMENDMENT-09 F1 sweep"),
        "cmpB": fv((cmp_b << 1) | 1, "R1 compare-B descriptor"),
        "cmp_mode": fv(cmp_mode, "R1 compare mode; AMENDMENT-07 C2 sweep"),
        "selTrue": fv(sel_true << 1, "R1 true-value descriptor"),
        "cc": fv((0x07 if cond == "lt" else 0x06) if cc_value is None else cc_value,
                 "R1 condition; AMENDMENT-07 C1 sweep"),
        "flags": fv(flags, "R1 flags byte; AMENDMENT-03 L1 sweep"),
        "selFalse_file": fv(sel_false_file,
                            "R1 false-source control; AMENDMENT-10 S1 sweep"),
        "selFalse": fv(sel_false << 1, "R1 false-value descriptor"),
    })
    pg._pending = None
    ma = cmp_a if model_cmp_a is None else model_cmp_a
    mb = cmp_b if model_cmp_b is None else model_cmp_b
    mt = sel_true if model_sel_true is None else model_sel_true
    mf = sel_false if model_sel_false is None else model_sel_false
    av, bv, tv, fv_bits = pg.rbits(ma), pg.rbits(mb), pg.rbits(mt), pg.rbits(mf)
    if None in (av, bv, tv, fv_bits):
        out = None
    else:
        pred = (model_predicate(model_kind, av, bv) if model_kind is not None else
                (signed32(av) < signed32(bv) if cond == "lt" else
                 signed32(av) > signed32(bv)))
        out = tv if pred else fv_bits
    # F1/S1: source releases occur after all reads and regardless of predicate.
    # Destination publication follows, so an aliased destination wins.
    if opsel & 1:
        pg.set_reg(cmp_a, 0)
    if opsel & 2:
        pg.set_reg(cmp_b, 0)
    if (cmp_mode & 0xE0) == 0x80:
        pg.set_reg(sel_true, 0)
    if (sel_false_file & 0xE0) == 0x80:
        pg.set_reg(sel_false, 0)
    pg.set_reg(dst, out)


def emit_iadd_proven(pg, dst, src_a, src_b, add):
    """EXP-0222's proven 32-bit register recipe, retained-source form."""
    phys_a, phys_b = (src_a, src_b) if add else (src_b, src_a)
    pg.E.emit("iadd2", {
        "addsub": fv(1 if add else 0, "EXP-0222 add/sub operation"),
        "lenbit": fv(1, "EXP-0222 ten-byte form"),
        "srcB_reg_hi": fv(0, "EXP-0222 register form"),
        "b2_bit0": fv(0, "EXP-0222 canonical point"),
        "store_en": fv(1, "EXP-0222 publish destination"),
        "b2_fmt": fv(0x15, "EXP-0222 format point"),
        "dst": fv((dst << 1) | 1, "EXP-0222 32-bit destination"),
        "opmode": fv(2, "EXP-0222 register mode"),
        "srcB_imm": fv(phys_b << 2, "EXP-0222 second physical source"),
        "srcB_imm_hi": fv(0, "EXP-0222 register form"),
        "srcB_ext": fv(phys_a << 2, "EXP-0222 first physical source"),
        "srcA": fv(0xA8, "EXP-0222 operand control"),
        "opc_tail": fv(0x11, "EXP-0222 retain both sources"),
        "opc_tail2": fv(0x05, "EXP-0222 tail"),
    })
    pg._pending = None
    a, b = pg.rbits(src_a), pg.rbits(src_b)
    pg.set_reg(dst, None if a is None or b is None else
               ((a + b) if add else (a - b)) & 0xFFFFFFFF)


def prepare_relation(pg, relation):
    if relation == "lt":
        return 1, 2
    if relation == "gt":
        return 2, 1
    if relation == "eq":
        pg.movi(2, 41)
        return 1, 2
    if relation == "sneg_lt":
        pg.movi(1, 0)
        pg.movi(2, 1)
        emit_iadd_proven(pg, 1, 1, 2, False)
        return 1, 2
    if relation == "sneg_gt":
        pg.movi(1, 1)
        pg.movi(2, 0)
        emit_iadd_proven(pg, 2, 2, 1, False)
        return 1, 2
    if relation == "flt":
        pg.load_f(1, 3)
        pg.load_f(2, 7)
        return 1, 2
    if relation == "fgt":
        pg.load_f(1, 7)
        pg.load_f(2, 3)
        return 1, 2
    if relation == "feq":
        pg.load_f(1, 3)
        pg.load_f(2, 3)
        return 1, 2
    if relation == "fnan":
        pg.load_f(1, 522)
        pg.load_f(2, 514)
        return 1, 2
    if relation == "fpos_lt":
        pg.load_f(1, 514)
        pg.load_f(2, 516)
        return 1, 2
    if relation == "fneg_lt":
        pg.load_f(1, 517)
        pg.load_f(2, 515)
        return 1, 2
    if relation == "fneg_gt":
        pg.load_f(1, 515)
        pg.load_f(2, 517)
        return 1, 2
    if relation == "fzero":
        pg.load_f(1, 513)
        pg.load_f(2, 512)
        return 1, 2
    if relation == "fneq":
        pg.load_f(1, 514)
        pg.load_f(2, 516)
        return 1, 2
    raise ValueError(relation)


def fresh(case, slots):
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.prologue(seed_high=True)
    return pg


ORIG_CASES = C.build_cases
ORIG_BUILD = C.build_program_for


def build_cases(include_hazard=False):
    out = [c for c in ORIG_CASES(False) if c["arm"] == "S0"]
    for packing in ("h1", "h2", "h3"):
        for direction, ca, cb in (("true", 1, 2), ("false", 2, 1)):
            out.append({
                "i": len(out), "name": f"{packing}_{direction}", "arm": packing.upper(),
                "kind": "isel10", "expect_match": True, "predicted_bucket": "exact",
                "op": dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3, sel_false=4,
                           packing=packing),
            })
    out.append({
        "i": len(out), "name": "ctl_wrong_predicate", "arm": "CTL", "kind": "isel10",
        "expect_match": False, "predicted_bucket": "refute",
        "op": dict(dst=0, cmp_a=1, cmp_b=2, sel_true=3, sel_false=4,
                   packing="h1", model_cmp_a=2, model_cmp_b=1),
    })
    h4_specs = [
        ("h4_lt_true", dict(dst=0, cmp_a=1, cmp_b=2, sel_true=3, sel_false=4, cond="lt")),
        ("h4_lt_false", dict(dst=0, cmp_a=2, cmp_b=1, sel_true=3, sel_false=4, cond="lt")),
        ("h4_gt_true", dict(dst=0, cmp_a=2, cmp_b=1, sel_true=3, sel_false=4, cond="gt")),
        ("h4_gt_false", dict(dst=0, cmp_a=1, cmp_b=2, sel_true=3, sel_false=4, cond="gt")),
        ("h4_relocate", dict(dst=5, cmp_a=6, cmp_b=7, sel_true=8, sel_false=9, cond="lt")),
        ("h4_alias_a", dict(dst=1, cmp_a=1, cmp_b=2, sel_true=3, sel_false=4, cond="lt")),
        ("h4_alias_b", dict(dst=2, cmp_a=1, cmp_b=2, sel_true=3, sel_false=4, cond="lt")),
        ("h4_alias_t", dict(dst=3, cmp_a=1, cmp_b=2, sel_true=3, sel_false=4, cond="lt")),
        ("h4_alias_f", dict(dst=4, cmp_a=2, cmp_b=1, sel_true=3, sel_false=4, cond="lt")),
        ("h4_ctl_wrong_cmp", dict(dst=0, cmp_a=2, cmp_b=2, sel_true=3, sel_false=4,
                                         cond="lt", model_cmp_a=1, model_cmp_b=2)),
        ("h4_ctl_wrong_true", dict(dst=0, cmp_a=1, cmp_b=2, sel_true=5, sel_false=4,
                                          cond="lt", model_sel_true=3)),
    ]
    for name, op in h4_specs:
        out.append({
            "i": len(out), "name": name, "arm": "H4", "kind": "isel10",
            "expect_match": not name.startswith("h4_ctl"),
            "predicted_bucket": "refute" if name.startswith("h4_ctl") else "exact",
            "op_r1": op,
        })
    for flags in range(256):
        for direction, ca, cb in (("true", 1, 2), ("false", 2, 1)):
            out.append({
                "i": len(out),
                "name": f"l1_flags{flags:02x}_{direction}",
                "arm": "L1",
                "kind": "isel10_flags",
                "expect_match": True,
                "predicted_bucket": "measure",
                "op_r1": dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3,
                              sel_false=4, cond="lt", flags=flags),
            })
    high_flags = [sum(((mask >> bit) & 1) << outbit
                      for bit, outbit in enumerate((3, 5, 6, 7)))
                  for mask in range(16)]
    loaded_values = {
        "true": {1: 21, 2: 62, 3: 73, 4: 74},
        "false": {1: 21, 2: 61, 3: 73, 4: 74},
    }
    for flags in high_flags:
        for direction, ca, cb in (("true", 1, 2), ("false", 2, 1)):
            values = loaded_values[direction]
            for direct in (1, 2, 3, 4):
                # One loaded operand, immediately before the select.
                out.append({
                    "i": len(out),
                    "name": f"p1_one_f{flags:02x}_{direction}_r{direct}",
                    "arm": "P1", "kind": "isel10_provenance",
                    "expect_match": True, "predicted_bucket": "measure",
                    "loads": [(direct, values[direct])],
                    "op_r1": dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3,
                                  sel_false=4, cond="lt", flags=flags),
                })
                # All four loaded, with `direct` deliberately last.
                order = [r for r in (1, 2, 3, 4) if r != direct] + [direct]
                out.append({
                    "i": len(out),
                    "name": f"p1_all_f{flags:02x}_{direction}_last_r{direct}",
                    "arm": "P1", "kind": "isel10_provenance",
                    "expect_match": True, "predicted_bucket": "measure",
                    "loads": [(r, values[r]) for r in order],
                    "op_r1": dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3,
                                  sel_false=4, cond="lt", flags=flags),
                })
            for gap in (0, 1, 2, 4, 8, 16):
                out.append({
                    "i": len(out),
                    "name": f"d1_f{flags:02x}_{direction}_gap{gap:02d}",
                    "arm": "D1", "kind": "isel10_load_distance",
                    "expect_match": True, "predicted_bucket": "measure",
                    "loads": [(r, values[r]) for r in (1, 2, 3, 4)],
                    "delay": gap,
                    "op_r1": dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3,
                                  sel_false=4, cond="lt", flags=flags),
                })
    for cc in range(256):
        for relation in ("lt", "gt", "eq", "sneg_lt", "sneg_gt"):
            out.append({
                "i": len(out), "name": f"c1_cc{cc:02x}_{relation}",
                "arm": "C1", "kind": "isel10_cc", "relation": relation,
                "expect_match": True, "predicted_bucket": "measure",
                "cc_value": cc,
            })
    for mode in range(256):
        for relation in ("lt", "gt", "eq", "sneg_lt", "sneg_gt",
                         "flt", "fgt", "feq", "fnan"):
            out.append({
                "i": len(out), "name": f"c2_mode{mode:02x}_{relation}",
                "arm": "C2", "kind": "isel10_cmp_mode", "relation": relation,
                "expect_match": True, "predicted_bucket": "measure",
                "cmp_mode": mode,
            })
    for opsel in range(32):
        for cc in (2, 3):
            for relation in ("fpos_lt", "fneg_lt", "fneg_gt", "fzero", "fnan"):
                out.append({
                    "i": len(out),
                    "name": f"f1_op{opsel:02x}_cc{cc}_{relation}",
                    "arm": "F1", "kind": "isel10_float_opsel",
                    "relation": relation, "opsel": opsel, "cmp_mode": 0x02,
                    "cc_value": cc, "expect_match": True,
                    "predicted_bucket": "measure",
                })
        for relation in ("feq", "fneq", "fzero", "fnan"):
            out.append({
                "i": len(out),
                "name": f"f1_op{opsel:02x}_eq_{relation}",
                "arm": "F1", "kind": "isel10_float_eq_opsel",
                "relation": relation, "opsel": opsel, "cmp_mode": 0x06,
                "cc_value": 0, "expect_match": True,
                "predicted_bucket": "measure",
            })
    for false_file in range(256):
        for direction, ca, cb in (("true", 1, 2), ("false", 2, 1)):
            out.append({
                "i": len(out),
                "name": f"s1_ff{false_file:02x}_{direction}",
                "arm": "S1", "kind": "isel10_false_file",
                "expect_match": True, "predicted_bucket": "measure",
                "op_r1": dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3,
                              sel_false=4, cond="lt", flags=0xC0, opsel=0,
                              cmp_mode=0x02, sel_false_file=false_file),
            })
    for mode in range(256):
        if (mode & 3) != 2:
            continue
        for relation in ("lt", "gt", "eq", "sneg_lt", "sneg_gt",
                         "flt", "fgt", "feq", "fnan"):
            out.append({
                "i": len(out), "name": f"c2b_mode{mode:02x}_{relation}",
                "arm": "C2B", "kind": "isel10_cmp_mode_valid",
                "relation": relation, "expect_match": True,
                "predicted_bucket": "measure", "cmp_mode": mode,
            })

    def v2_single(name, op, relation=None, expect_match=True):
        out.append({
            "i": len(out), "name": name, "arm": "V2", "kind": "v2_single",
            "relation": relation, "op_r1": op, "expect_match": expect_match,
            "predicted_bucket": "exact" if expect_match else "refute",
        })

    # Integer condition table, both predicate outcomes.
    int_specs = [
        ("slt_t", "sneg_lt", 7, "slt", 3, 4),
        ("slt_f", "sneg_gt", 7, "slt", 3, 4),
        ("sgt_t", "sneg_gt", 6, "sgt", 3, 4),
        ("sgt_f", "sneg_lt", 6, "sgt", 3, 4),
        ("ult_t", "sneg_gt", 5, "ult", 3, 4),
        ("ult_f", "sneg_lt", 5, "ult", 3, 4),
        ("ugt_t", "sneg_lt", 4, "ugt", 3, 4),
        ("ugt_f", "sneg_gt", 4, "ugt", 3, 4),
        ("eq_t", "eq", 7, "eq", 3, 4),
        ("eq_f", "lt", 7, "eq", 3, 4),
        ("ne_t", "lt", 7, "eq", 4, 3),
        ("ne_f", "eq", 7, "eq", 4, 3),
    ]
    for name, relation, cc, kind, st, sf in int_specs:
        v2_single("v2_int_" + name,
                  dict(dst=0, cmp_a=1, cmp_b=2, sel_true=st, sel_false=sf,
                       cond="lt", flags=0xC0, opsel=0,
                       cmp_mode=0x06 if name.startswith(("eq", "ne")) else 0x02,
                       cc_value=cc, sel_false_file=0, model_kind=kind), relation)

    float_specs = [
        ("fgt_t", "fneg_gt", 2, 0x02, "fgt", 3, 4),
        ("fgt_f", "fneg_lt", 2, 0x02, "fgt", 3, 4),
        ("flt_t", "fneg_lt", 3, 0x02, "flt", 3, 4),
        ("flt_f", "fneg_gt", 3, 0x02, "flt", 3, 4),
        ("feq_t", "fzero", 0, 0x06, "feq", 3, 4),
        ("feq_f", "fneq", 0, 0x06, "feq", 3, 4),
        ("fneu_nan", "fnan", 0, 0x06, "feq", 4, 3),
        ("fneu_eq", "feq", 0, 0x06, "feq", 4, 3),
    ]
    for name, relation, cc, mode, kind, st, sf in float_specs:
        v2_single("v2_float_" + name,
                  dict(dst=0, cmp_a=1, cmp_b=2, sel_true=st, sel_false=sf,
                       cond="lt", flags=0xC0, opsel=0, cmp_mode=mode,
                       cc_value=cc, sel_false_file=0, model_kind=kind), relation)

    # Lifecycle truth tables over both predicate outcomes.
    for opsel in (0, 1, 2, 3, 6, 7):
        for direction, ca, cb in (("t", 1, 2), ("f", 2, 1)):
            v2_single(f"v2_life_cmp_op{opsel}_{direction}",
                      dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3, sel_false=4,
                           cond="lt", flags=0xC0, opsel=opsel, cmp_mode=0x02,
                           cc_value=7, sel_false_file=0, model_kind="slt"))
    for mode in (0x02, 0x82):
        for direction, ca, cb in (("t", 1, 2), ("f", 2, 1)):
            v2_single(f"v2_life_true_m{mode:02x}_{direction}",
                      dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3, sel_false=4,
                           cond="lt", flags=0xC0, opsel=0, cmp_mode=mode,
                           cc_value=7, sel_false_file=0, model_kind="slt"))
    for ff in (0x00, 0x80):
        for direction, ca, cb in (("t", 1, 2), ("f", 2, 1)):
            v2_single(f"v2_life_false_f{ff:02x}_{direction}",
                      dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3, sel_false=4,
                           cond="lt", flags=0xC0, opsel=0, cmp_mode=0x02,
                           cc_value=7, sel_false_file=ff, model_kind="slt"))
    for direction, ca, cb in (("t", 1, 2), ("f", 2, 1)):
        v2_single(f"v2_life_all_{direction}",
                  dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3, sel_false=4,
                       cond="lt", flags=0xC0, opsel=3, cmp_mode=0x82,
                       cc_value=7, sel_false_file=0x80, model_kind="slt"))

    for name, op in h4_specs[5:9]:
        op = dict(op)
        op["model_kind"] = "slt"
        v2_single("v2_" + name, op)

    # Canonical load provenance, one loaded source or all with each final slot.
    for direction, ca, cb in (("true", 1, 2), ("false", 2, 1)):
        values = loaded_values[direction]
        for direct in (1, 2, 3, 4):
            base = dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3, sel_false=4,
                        cond="lt", flags=0xC0, opsel=0, cmp_mode=0x02,
                        cc_value=7, sel_false_file=0, model_kind="slt")
            out.append({
                "i": len(out), "name": f"v2_load_one_{direction}_r{direct}",
                "arm": "V2", "kind": "v2_load", "expect_match": True,
                "predicted_bucket": "exact", "loads": [(direct, values[direct])],
                "op_r1": base,
            })
            order = [r for r in (1, 2, 3, 4) if r != direct] + [direct]
            out.append({
                "i": len(out), "name": f"v2_load_all_{direction}_last_r{direct}",
                "arm": "V2", "kind": "v2_load", "expect_match": True,
                "predicted_bucket": "exact",
                "loads": [(r, values[r]) for r in order], "op_r1": dict(base),
            })

    # Operand and destination reach over the complete dumped register envelope.
    for role in ("a", "b", "t", "f"):
        for reg in (0, 5, 10, 14, 16, 19, 22, 23):
            op = dict(dst=11, cmp_a=1, cmp_b=2, sel_true=3, sel_false=4,
                      cond="lt", flags=0xC0, opsel=0, cmp_mode=0x02,
                      cc_value=7, sel_false_file=0, model_kind="slt")
            op[{"a": "cmp_a", "b": "cmp_b", "t": "sel_true", "f": "sel_false"}[role]] = reg
            v2_single(f"v2_cross_{role}_r{reg:02d}", op)
    for dst in range(15):
        v2_single(f"v2_dst_r{dst:02d}",
                  dict(dst=dst, cmp_a=16, cmp_b=17, sel_true=18, sel_false=19,
                       cond="lt", flags=0xC0, opsel=0, cmp_mode=0x02,
                       cc_value=7, sel_false_file=0, model_kind="slt"))

    # Deterministic generated programs, 2..64 operations, no release hints.
    src_pool = list(range(12)) + [13, 14] + list(range(16, 24))
    dst_pool = list(range(12)) + [13, 14]
    for case_i in range(100):
        rng = random.Random(223000 + case_i)
        ops = []
        for _ in range(2 + ((case_i * 37) % 63)):
            if rng.randrange(5) < 2:
                ops.append(("iadd", dict(dst=rng.choice(dst_pool),
                                          src_a=rng.choice(src_pool),
                                          src_b=rng.choice(src_pool),
                                          add=bool(rng.randrange(2)))))
            else:
                ops.append(("isel", dict(dst=rng.choice(dst_pool),
                                          cmp_a=rng.choice(src_pool),
                                          cmp_b=rng.choice(src_pool),
                                          sel_true=rng.choice(src_pool),
                                          sel_false=rng.choice(src_pool),
                                          cond="lt", flags=0xC0, opsel=0,
                                          cmp_mode=0x02, cc_value=7,
                                          sel_false_file=0, model_kind="slt")))
        out.append({
            "i": len(out), "name": f"v2_dag_{case_i:03d}", "arm": "V2",
            "kind": "v2_dag", "ops": ops, "expect_match": True,
            "predicted_bucket": "exact",
        })

    v2_single("v2_ctl_wrong_cmp",
              dict(dst=0, cmp_a=1, cmp_b=2, sel_true=3, sel_false=4,
                   cond="lt", flags=0xC0, opsel=0, cmp_mode=0x02, cc_value=7,
                   sel_false_file=0, model_kind="slt", model_cmp_a=2,
                   model_cmp_b=1), expect_match=False)
    v2_single("v2_ctl_wrong_true",
              dict(dst=0, cmp_a=1, cmp_b=2, sel_true=5, sel_false=4,
                   cond="lt", flags=0xC0, opsel=0, cmp_mode=0x02, cc_value=7,
                   sel_false_file=0, model_kind="slt", model_sel_true=3),
              expect_match=False)
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = fresh(case, slots)
    if case["arm"] == "V2":
        if case.get("relation") is not None:
            ca, cb = prepare_relation(pg, case["relation"])
            op = dict(case["op_r1"])
            op["cmp_a"], op["cmp_b"] = ca, cb
            emit_isel_r1(pg, **op)
        elif case["kind"] == "v2_load":
            for reg, word in case["loads"]:
                pg.load_i(reg, word, salt=f"{case['name']}.load_r{reg}")
            emit_isel_r1(pg, **case["op_r1"])
        elif case["kind"] == "v2_dag":
            for kind, op in case["ops"]:
                if kind == "iadd":
                    emit_iadd_proven(pg, **op)
                else:
                    emit_isel_r1(pg, **op)
        else:
            emit_isel_r1(pg, **case["op_r1"])
    elif case["arm"] in ("C1", "C2", "C2B", "F1"):
        ca, cb = prepare_relation(pg, case["relation"])
        emit_isel_r1(pg, dst=0, cmp_a=ca, cmp_b=cb, sel_true=3, sel_false=4,
                     cond="lt", flags=0xC0, cc_value=case.get("cc_value"),
                     cmp_mode=case.get("cmp_mode", 0x02),
                     opsel=case.get("opsel", 0))
    elif case["arm"] in ("P1", "D1"):
        for reg, word in case["loads"]:
            pg.load_i(reg, word, salt=f"{case['name']}.load_r{reg}")
        for n in range(case.get("delay", 0)):
            pg.movi(14, 75 + (n & 3))
        emit_isel_r1(pg, **case["op_r1"])
    elif case["arm"] in ("H4", "L1", "S1"):
        emit_isel_r1(pg, **case["op_r1"])
    else:
        emit_isel(pg, **case["op"])
    pg.dump()
    return pg, pg.finish(carrier_len)


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
