#!/usr/bin/env python3
"""Offline byte, boundary, and provenance checks for EXP-0228."""

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run228 as X  # noqa: E402


def main():
    cases = [c for c in X.build_cases(False) if c["arm"] != "S0"]
    assert len(cases) == 23
    assert len({c["byte2"] for c in cases if c["arm"] != "CTL"}) == 22
    for case in cases:
        assert (case["byte2"] & 7) in (0, 1)
        pg, prog = X.build_program_for(case, {"out": 0, "mem": 1, "imem": 2}, 2048)
        rows, bad, alias = X.S.gate_a_ledger(prog, pg.E.parts)
        assert not bad, (case["name"], bad)
        assert not alias, (case["name"], alias)
        assert not pg.E.led.nonsynthesised(), case["name"]
        body = prog[pg.body_start:pg.body_end]
        assert body[:4] == bytes((0x09, 0x01, case["byte2"], 0x05))
        parts = [p for p in pg.E.parts if pg.body_start <= p[0] < pg.body_end]
        assert [p[0] - pg.body_start for p in parts[:6]] == [0, 4, 6, 8, 10, 12]
        assert len(rows) == len(pg.E.parts)
    print("EXP-0228 selftest: 23/23 programs; 22 byte+2 points; Gate A clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
