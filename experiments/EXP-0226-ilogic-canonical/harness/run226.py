#!/usr/bin/env python3
"""EXP-0226 generated 32-bit LUT2 harness."""

import sys
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
EXP_ROOT = EXP.parent
BASE_HARNESS = EXP_ROOT / "EXP-0225-imad-canonical" / "harness"
sys.path.insert(0, str(BASE_HARNESS))
import run225 as B  # noqa: E402


C, P, R, S = B.C, B.P, B.R, B.S
ORIG_CASES = B.ORIG_CASES
ORIG_BUILD = B.ORIG_BUILD


# Desired semantic function -> EXP-0146 selector row. The table's operand a
# lives in db srcB and table b lives in db srcA (EXP-0154 DEF-0154-5).
TABLE = {
    "zero": (0, 0x00, 0x00),
    "and": (1, 0x00, 0x00),
    "a_and_not_b": (0, 0x00, 0x08),
    "a": (0, 0x00, 0x09),
    "not_a_and_b": (0, 0x02, 0x00),
    "b": (0, 0x02, 0x02),
    "xor": (0, 0x02, 0x08),
    "or": (1, 0x02, 0x08),
    "nor": (0, 0x01, 0x00),
    "xnor": (1, 0x01, 0x00),
    "not_b": (0, 0x01, 0x02),
    "a_or_not_b": (1, 0x01, 0x08),
    "not_a": (0, 0x01, 0x01),
    "not_a_or_b": (1, 0x03, 0x00),
    "nand": (0, 0x03, 0x08),
    "ones": (0, 0x01, 0x05),
}


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0226 PRE_REGISTRATION", note)


def logic_value(kind, a, b):
    mask = 0xFFFFFFFF
    return {
        "zero": 0,
        "and": a & b,
        "a_and_not_b": a & ~b,
        "a": a,
        "not_a_and_b": ~a & b,
        "b": b,
        "xor": a ^ b,
        "or": a | b,
        "nor": ~(a | b),
        "xnor": ~(a ^ b),
        "not_b": ~b,
        "a_or_not_b": a | ~b,
        "not_a": ~a,
        "not_a_or_b": ~a | b,
        "nand": ~(a & b),
        "ones": mask,
    }[kind] & mask


def emit_logic(pg, dst, src_a, src_b, func, model_func=None,
               model_src_a=None, model_src_b=None):
    base, la, lb = TABLE[func]
    pg.E.emit("ilogic", {
        "dst": fv(dst, "destination low-bank GPR"),
        "srcA": fv((src_b << 1) | 1, "table operand b / descriptor srcA"),
        "op_base": fv(base, "LUT base selector"),
        "srcB": fv((src_a << 1) | 1, "table operand a / descriptor srcB"),
        "lut_a_sel": fv(la & 3, "LUT selector A low bits"),
        "lut_a_free": fv(0, "bounded selector alias point"),
        "lut_a_z": fv(0, "required-zero selector tail"),
        "lut_b": fv(lb, "LUT selector B"),
        "z6": fv(0, "bounded tail point"),
        "outmod": fv(0x80, "source-read enable"),
        "z8": fv(0, "bounded tail point"),
        "z9": fv(0, "bounded tail point"),
    })
    pg._pending = None
    ma = src_a if model_src_a is None else model_src_a
    mb = src_b if model_src_b is None else model_src_b
    a, b = pg.rbits(ma), pg.rbits(mb)
    result = None if a is None or b is None else logic_value(model_func or func, a, b)
    # Pre-registered destructive-source model; destination publication wins.
    pg.set_reg(src_a, 0)
    pg.set_reg(src_b, 0)
    pg.set_reg(dst, result)


def build_cases(include_hazard=False):
    out = [case for case in ORIG_CASES(False) if case["arm"] == "S0"]
    for func in TABLE:
        out.append({
            "i": len(out), "name": "h1_" + func, "arm": "H1",
            "kind": "logic", "expect_match": True,
            "predicted_bucket": "exact",
            "op": dict(dst=0, src_a=1, src_b=2, func=func),
        })
    for n, func in enumerate(("a_and_not_b", "not_a_and_b", "a_or_not_b",
                              "not_a_or_b"), 5):
        out.append({
            "i": len(out), "name": "h1_reloc_" + func, "arm": "H1",
            "kind": "logic", "expect_match": True,
            "predicted_bucket": "exact",
            "op": dict(dst=n, src_a=6, src_b=7, func=func),
        })
    for suffix, dst, a, b in (("dst_a", 1, 1, 2), ("dst_b", 2, 1, 2),
                              ("same", 0, 1, 1)):
        out.append({
            "i": len(out), "name": "h1_alias_" + suffix, "arm": "H1",
            "kind": "logic", "expect_match": True,
            "predicted_bucket": "exact",
            "op": dict(dst=dst, src_a=a, src_b=b, func="xor"),
        })
    out.append({
        "i": len(out), "name": "ctl_wrong_order", "arm": "CTL",
        "kind": "logic", "expect_match": False, "predicted_bucket": "refute",
        "op": dict(dst=0, src_a=1, src_b=2, func="a_and_not_b",
                   model_src_a=2, model_src_b=1),
    })
    out.append({
        "i": len(out), "name": "ctl_wrong_function", "arm": "CTL",
        "kind": "logic", "expect_match": False, "predicted_bucket": "refute",
        "op": dict(dst=0, src_a=1, src_b=2, func="xor", model_func="or"),
    })
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = B.B.fresh(case, slots)
    emit_logic(pg, **case["op"])
    pg.dump()
    return pg, pg.finish(carrier_len)


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())

