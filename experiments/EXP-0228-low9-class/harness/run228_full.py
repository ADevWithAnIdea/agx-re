#!/usr/bin/env python3
"""EXP-0228 Amendment 01: full 64-value selector-0/1 length sweep."""

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run228 as B  # noqa: E402


C, R = B.C, B.R
ALL_BYTE2 = tuple(v for v in range(256) if (v & 7) in (0, 1))


def build_cases(include_hazard=False):
    out = [case for case in B.ORIG_CASES(False) if case["arm"] == "S0"]
    for byte2 in ALL_BYTE2:
        B.add_case(out, byte2, "FULL")
    out.append({
        "i": len(out), "name": "ctl_b20_wrong_r6", "arm": "CTL",
        "kind": "low9_length", "expect_match": False,
        "predicted_bucket": "refute", "byte2": 0x20,
        "first_reg": 6, "first_value": 87, "model_first_value": 88,
        "expected_length": 4,
    })
    return out


def main():
    C.build_cases = build_cases
    C.build_program_for = B.build_program_for
    R.score = B.B.score227
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
