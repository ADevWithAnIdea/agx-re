#!/usr/bin/env python3
"""EXP-0225 generated low-32 integer multiply-add harness."""

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
    return S.FV(value, S.RULE, "EXP-0225 PRE_REGISTRATION", note)


def emit_imad(pg, dst, src_x, src_y, imm, b9, b10,
              model_src_x=None, model_src_y=None, model_imm=None,
              release_x=False, release_y=False):
    if not (0 <= imm <= 255):
        raise ValueError("EXP-0225 literal is eight bits")
    pg.E.emit("imad", {
        "b0bit7": fv(1, "twelve-byte integer family"),
        "lenbit": fv(0, "twelve-byte IMAD form"),
        "b1hi": fv(0, "generated low-bank form"),
        "b2_bit0": fv(0, "canonical structural point"),
        "store_en": fv(1, "publish destination"),
        "b2_fmt": fv(0x15, "32-bit integer format point"),
        "dst": fv(dst << 1, "destination descriptor D<<1"),
        "opmode": fv(0x02, "low-32 register operation"),
        "srcC_lo": fv(src_x << 2, "multiplicand X descriptor X<<2"),
        "srcB": fv(src_y << 3, "multiplicand Y descriptor Y<<3"),
        "srcC_desc": fv((imm & 31) << 3, "literal low five bits"),
        "mulsel": fv(0xD0 | (imm >> 5), "low product plus literal high bits"),
        "b9": fv(b9, "literal-source and lifecycle hypothesis"),
        "b10": fv(b10, "low-product control hypothesis"),
        "b11": fv(0, "bounded tail point"),
    })
    pg._pending = None
    mx = src_x if model_src_x is None else model_src_x
    my = src_y if model_src_y is None else model_src_y
    mk = imm if model_imm is None else model_imm
    x, y = pg.rbits(mx), pg.rbits(my)
    result = None if x is None or y is None else (x * y + mk) & 0xFFFFFFFF
    # AMENDMENT-01: releases occur after both reads; destination publication
    # follows, so a destination/source alias contains the result.
    if release_x:
        pg.set_reg(src_x, 0)
    if release_y:
        pg.set_reg(src_y, 0)
    pg.set_reg(dst, result)


def build_cases(include_hazard=False):
    out = [case for case in ORIG_CASES(False) if case["arm"] == "S0"]
    candidates = {
        "H1": (0x20, 0x0A),
        "H2": (0x20, 0x0F),
        "H3": (0x20, 0x1F),
        "H4": (0x22, 0x0A),
    }
    variants = [
        ("base", dict(dst=0, src_x=1, src_y=2, imm=7)),
        ("perm", dict(dst=5, src_x=6, src_y=3, imm=201)),
        ("alias_x", dict(dst=1, src_x=1, src_y=2, imm=13)),
        ("alias_y", dict(dst=2, src_x=1, src_y=2, imm=29)),
        ("imul", dict(dst=7, src_x=4, src_y=6, imm=0)),
        ("imm255", dict(dst=8, src_x=9, src_y=10, imm=255)),
    ]
    for arm, (b9, b10) in candidates.items():
        for suffix, cfg in variants:
            op = dict(cfg, b9=b9, b10=b10)
            out.append({
                "i": len(out), "name": "%s_%s" % (arm.lower(), suffix),
                "arm": arm, "kind": "imad", "op": op,
                "expect_match": True, "predicted_bucket": "exact",
            })

    for name, b9, rx, ry in (("l1_release_y", 0x24, False, True),
                             ("l1_release_xy", 0x26, True, True)):
        for suffix, dst in (("plain", 0), ("alias_x", 1), ("alias_y", 2)):
            out.append({
                "i": len(out), "name": "%s_%s" % (name, suffix),
                "arm": "L1", "kind": "imad", "expect_match": True,
                "predicted_bucket": "exact",
                "op": dict(dst=dst, src_x=1, src_y=2, imm=37,
                           b9=b9, b10=0x0A, release_x=rx, release_y=ry),
            })

    out.append({
        "i": len(out), "name": "ctl_wrong_imm", "arm": "CTL",
        "kind": "imad", "expect_match": False, "predicted_bucket": "refute",
        "op": dict(dst=0, src_x=1, src_y=2, imm=7, b9=0x20, b10=0x0A,
                   model_imm=8),
    })
    out.append({
        "i": len(out), "name": "ctl_wrong_source", "arm": "CTL",
        "kind": "imad", "expect_match": False, "predicted_bucket": "refute",
        "op": dict(dst=0, src_x=1, src_y=2, imm=7, b9=0x20, b10=0x0A,
                   model_src_y=3),
    })
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = B.fresh(case, slots)
    emit_imad(pg, **case["op"])
    pg.dump()
    return pg, pg.finish(carrier_len)


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
