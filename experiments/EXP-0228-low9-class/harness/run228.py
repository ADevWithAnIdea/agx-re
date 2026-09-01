#!/usr/bin/env python3
"""EXP-0228: broaden G17P low-nibble-9 compact-length coverage."""

import importlib.util
import sys
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
EXP_ROOT = EXP.parent
HERE = Path(__file__).resolve().parent
BASE = EXP_ROOT / "EXP-0227-low9-length" / "harness"
sys.path.insert(0, str(BASE))
import run227 as B  # noqa: E402


C, P, R, S = B.C, B.P, B.R, B.S
ORIG_CASES, ORIG_BUILD = B.ORIG_CASES, B.ORIG_BUILD

PINNED = EXP / "work" / "frozen" / "isadb.py"
_spec = importlib.util.spec_from_file_location("exp0228_isadb", PINNED)
EXP228_ISADB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(EXP228_ISADB)
assert Path(EXP228_ISADB._DB_JSON).resolve() == (PINNED.parent / "db.json").resolve()
S.isadb = EXP228_ISADB

R.EXP = EXP
R.HERE = HERE
R.CARRIER = "carrier228.metal"
R.FUNC = "k"

NATURAL = (0x18, 0x19, 0x20, 0x21, 0x30, 0x31, 0x38, 0x39)
OFF_NATURAL = (0x00, 0x01, 0x08, 0x09, 0x10, 0x11, 0x28, 0x29,
               0x40, 0x41, 0x78, 0x79, 0xF8, 0xF9)


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0228 PRE_REGISTRATION", note)


def emit_prefix(pg, byte2):
    if byte2 in (0x18, 0x19, 0x38, 0x39):
        # The specific accumulate descriptor has precedence over the generic
        # compact-class descriptor at these four compiler-observed points.
        pg.E.emit("falu_acc", {
            "dst": fv(0, "fixed candidate destination"),
            "srcA": fv(0x01, "fixed candidate source descriptor"),
            "op": fv(byte2 & 1, "accumulate add/multiply selector"),
            "cache": fv((byte2 >> 5) & 1, "accumulate cache/lifecycle bit"),
            "srcB": fv(0x05, "fixed candidate operand descriptor"),
        })
    else:
        pg.E.emit("falu_compact4", {
            "dst": fv(0, "fixed candidate destination"),
            "src": fv(0x01, "fixed candidate source descriptor"),
            "opsel": fv(byte2 & 0x07, "compact-class selector"),
            "opmode": fv(byte2 >> 3, "dense mode sample"),
            "operand": fv(0x05, "fixed candidate operand descriptor"),
        })
    pg._pending = None
    for reg in B.CANDIDATE_UNKNOWN_REGS:
        pg.set_reg(reg, None)


def add_case(out, byte2, arm):
    out.append({
        "i": len(out), "name": "%s_b%02x" % (arm.lower(), byte2),
        "arm": arm, "kind": "low9_length", "expect_match": True,
        "predicted_bucket": "measure", "byte2": byte2,
        "first_reg": 6, "first_value": 87, "model_first_value": None,
        "expected_length": 4,
    })


def build_cases(include_hazard=False):
    out = [case for case in ORIG_CASES(False) if case["arm"] == "S0"]
    for byte2 in NATURAL:
        add_case(out, byte2, "OBS")
    for byte2 in OFF_NATURAL:
        add_case(out, byte2, "OFF")
    out.append({
        "i": len(out), "name": "ctl_b20_wrong_r6", "arm": "CTL",
        "kind": "low9_length", "expect_match": False,
        "predicted_bucket": "refute", "byte2": 0x20,
        "first_reg": 6, "first_value": 87, "model_first_value": 88,
        "expected_length": 4,
    })
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = B.B.fresh(case, slots)
    emit_prefix(pg, case["byte2"])
    case["marker_values"] = B.emit_staircase(
        pg, case["first_reg"], case["first_value"],
        model_first_value=case.get("model_first_value"))
    pg.dump()
    return pg, pg.finish(carrier_len)


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    R.score = B.score227
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
