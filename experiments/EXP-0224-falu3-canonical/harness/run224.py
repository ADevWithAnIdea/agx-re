#!/usr/bin/env python3
"""EXP-0224 generated FP32 falu3 recipe harness."""

import struct
import sys
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
EXP_ROOT = EXP.parent
BASE_HARNESS = EXP_ROOT / "EXP-0223-isel-canonical" / "harness"
sys.path.insert(0, str(BASE_HARNESS))
import run223_pilot as B  # noqa: E402


C, P, R, S = B.C, B.P, B.R, B.S
ORIG_CASES = B.ORIG_CASES
ORIG_BUILD = B.ORIG_BUILD


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0224 PRE_REGISTRATION", note)


def fma_bits(a_bits, b_bits, c_bits):
    if None in (a_bits, b_bits, c_bits):
        return None
    a, b, c = S.bits_f32(a_bits), S.bits_f32(b_bits), S.bits_f32(c_bits)
    # Every H input is an exactly representable small binary32 value.  Its
    # product and sum are exact in binary64, followed by one binary32 rounding.
    return struct.unpack("<I", struct.pack("<f", S.f32(a * b + c)))[0]


def emit_fma(pg, dst, src_a, src_b, src_c, op, ctrl_len,
             ctrl=0x02, srcmods=0xc0,
             model_src_a=None, model_src_b=None, model_src_c=None,
             model_kind="fma"):
    pg.E.emit("falu3", {
        "dst": fv(dst, "destination GPR"),
        "srcA": fv((src_a << 1) | 1, "FP32 source A descriptor"),
        "op": fv(op, "generated FMA operation/lifecycle point"),
        "srcB": fv((src_b << 1) | 1, "FP32 source B descriptor"),
        "ctrl_len": fv(ctrl_len, "eight-byte control/length point"),
        "srcC": fv(src_c << 1, "FP32 source C descriptor"),
        "ctrl": fv(ctrl, "source/control point"),
        "srcmods": fv(srcmods, "source modifier/load-accept point"),
    })
    pg._pending = None
    ma = src_a if model_src_a is None else model_src_a
    mb = src_b if model_src_b is None else model_src_b
    mc = src_c if model_src_c is None else model_src_c
    result = fma_bits(pg.rbits(ma), pg.rbits(mb), pg.rbits(mc))
    if model_kind == "mul_add_a":
        result = fma_bits(pg.rbits(ma), pg.rbits(mb), pg.rbits(ma))
    # Destination publication is intentionally the only modelled mutation in
    # H1-H3. A release-like candidate therefore fails complete-state checking.
    pg.set_reg(dst, result)


def seed_h(pg, mapping):
    for reg, word in mapping:
        pg.load_f(reg, word, salt=f"{pg.salt}.seed_r{reg}")
    pg.movi(P.R_IDX, 0)       # independent post-load visibility gap


def build_cases(include_hazard=False):
    out = [case for case in ORIG_CASES(False) if case["arm"] == "S0"]
    candidates = {
        "h1": (0x1e, 0x81),
        "h2": (0x06, 0x81),
        "h3": (0x06, 0x01),
    }
    variants = [
        ("abc", 0, 1, 2, 3),
        ("perm", 0, 3, 2, 1),
        ("reloc", 5, 6, 7, 8),
        ("alias_a", 1, 1, 2, 3),
    ]
    for name, (op, ctrl_len) in candidates.items():
        for suffix, dst, a, b, c in variants:
            out.append({
                "i": len(out), "name": f"{name}_{suffix}", "arm": name.upper(),
                "kind": "falu3", "expect_match": True, "predicted_bucket": "exact",
                "cfg": dict(dst=dst, src_a=a, src_b=b, src_c=c,
                            op=op, ctrl_len=ctrl_len),
            })
    out.append({
        "i": len(out), "name": "h_ctl_wrong_c", "arm": "HCTL", "kind": "falu3",
        "expect_match": False, "predicted_bucket": "refute",
        "cfg": dict(dst=0, src_a=1, src_b=2, src_c=3, op=0x06, ctrl_len=0x81,
                    model_src_c=4),
    })
    out.append({
        "i": len(out), "name": "h_ctl_wrong_op", "arm": "HCTL", "kind": "falu3",
        "expect_match": False, "predicted_bucket": "refute",
        "cfg": dict(dst=0, src_a=1, src_b=2, src_c=3, op=0x06, ctrl_len=0x81,
                    model_kind="mul_add_a"),
    })
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = B.fresh(case, slots)
    seed_h(pg, [(1, 3), (2, 7), (3, 11), (4, 15),
                (6, 19), (7, 23), (8, 27)])
    emit_fma(pg, **case["cfg"])
    pg.dump()
    return pg, pg.finish(carrier_len)


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
