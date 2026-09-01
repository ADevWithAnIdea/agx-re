#!/usr/bin/env python3
"""Offline full-matrix construction gate for EXP-0228 Amendment 01."""

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run228_full as X  # noqa: E402


def main():
    cases = [c for c in X.build_cases(False) if c["arm"] != "S0"]
    full = [c for c in cases if c["arm"] == "FULL"]
    assert len(cases) == 65 and len(full) == 64
    assert {c["byte2"] for c in full} == set(X.ALL_BYTE2)
    for case in cases:
        pg, prog = X.B.build_program_for(
            case, {"out": 0, "mem": 1, "imem": 2}, 2048)
        rows, bad, alias = X.B.S.gate_a_ledger(prog, pg.E.parts)
        assert not bad, (case["name"], bad)
        assert not alias, (case["name"], alias)
        assert not pg.E.led.nonsynthesised(), case["name"]
        body = prog[pg.body_start:pg.body_end]
        assert body[:4] == bytes((0x09, 0x01, case["byte2"], 0x05))
        assert len(rows) == len(pg.E.parts)
    print("EXP-0228 full selftest: 65/65 programs; 64/64 byte+2 values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
