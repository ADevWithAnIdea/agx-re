#!/usr/bin/env python3
"""EXP-0223 pre-freeze generated isel10 pilots."""

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


def emit_isel_r1(pg, dst, cmp_a, cmp_b, sel_true, sel_false, cond, flags=0xC0,
                 cc_value=None, cmp_mode=0x02,
                 model_cmp_a=None, model_cmp_b=None, model_sel_true=None,
                 model_sel_false=None):
    pg.E.emit("isel10", {
        "dst": fv(dst, "R1 destination GPR"),
        "cmpA": fv((cmp_a << 1) | 1, "R1 compare-A descriptor"),
        "opsel": fv(0, "R1 ten-byte member"),
        "cmpB": fv((cmp_b << 1) | 1, "R1 compare-B descriptor"),
        "cmp_mode": fv(cmp_mode, "R1 compare mode; AMENDMENT-07 C2 sweep"),
        "selTrue": fv(sel_true << 1, "R1 true-value descriptor"),
        "cc": fv((0x07 if cond == "lt" else 0x06) if cc_value is None else cc_value,
                 "R1 condition; AMENDMENT-07 C1 sweep"),
        "flags": fv(flags, "R1 flags byte; AMENDMENT-03 L1 sweep"),
        "selFalse_file": fv(0, "R1 GPR false-source file"),
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
        pred = signed32(av) < signed32(bv) if cond == "lt" else signed32(av) > signed32(bv)
        out = tv if pred else fv_bits
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
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = fresh(case, slots)
    if case["arm"] in ("C1", "C2", "C2B"):
        ca, cb = prepare_relation(pg, case["relation"])
        emit_isel_r1(pg, dst=0, cmp_a=ca, cmp_b=cb, sel_true=3, sel_false=4,
                     cond="lt", flags=0xC0, cc_value=case.get("cc_value"),
                     cmp_mode=case.get("cmp_mode", 0x02))
    elif case["arm"] in ("P1", "D1"):
        for reg, word in case["loads"]:
            pg.load_i(reg, word, salt=f"{case['name']}.load_r{reg}")
        for n in range(case.get("delay", 0)):
            pg.movi(14, 75 + (n & 3))
        emit_isel_r1(pg, **case["op_r1"])
    elif case["arm"] in ("H4", "L1"):
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
