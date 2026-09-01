#!/usr/bin/env python3
"""Offline byte/provenance checks for EXP-0229."""

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run229 as X  # noqa: E402


def main():
    cases = [c for c in X.build_cases(False) if c["arm"] != "S0"]
    assert len(cases) == 9
    for case in cases:
        pg, prog = X.build_program_for(case, {"out": 0, "mem": 1, "imem": 2}, 2048)
        rows, bad, alias = X.S.gate_a_ledger(prog, pg.E.parts)
        assert not bad, (case["name"], bad)
        assert not alias, (case["name"], alias)
        assert not pg.E.led.nonsynthesised(), case["name"]
        body = prog[pg.body_start:pg.body_end]
        assert len(body[:10]) == 10
        assert body[0] == (0xC7 if case["direction"] else 0x47)
        assert body[1] == 0x06 and body[9] == case["rsv9"]
        parts = [p for p in pg.E.parts if pg.body_start <= p[0] < pg.body_end]
        assert [p[0] - pg.body_start for p in parts[:5]] == [0, 10, 12, 14, 16]
        assert len(rows) == len(pg.E.parts)
    print("EXP-0229 selftest: 9/9 programs; generated prefixes; Gate A clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
