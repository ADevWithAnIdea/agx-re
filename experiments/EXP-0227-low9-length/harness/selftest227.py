#!/usr/bin/env python3
"""Offline construction, provenance, and framing checks for EXP-0227."""

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run227 as X  # noqa: E402


def main():
    cases = [c for c in X.build_cases(False) if c["arm"] != "S0"]
    assert len(cases) == 5
    for case in cases:
        pg, prog = X.build_program_for(
            case, {"out": 0, "mem": 1, "imem": 2}, 2048)
        rows, bad, alias = X.S.gate_a_ledger(prog, pg.E.parts)
        assert not bad, (case["name"], bad)
        assert not alias, (case["name"], alias)
        assert pg.E.led.nonsynthesised() == []
        body = prog[pg.body_start:pg.body_end]
        expected_prefix = bytes((0x09, 0x01, case["byte2"], 0x05))
        assert body[:4] == expected_prefix, (case["name"], body[:4].hex())
        marker_parts = [part for part in pg.E.parts
                        if pg.body_start + 4 <= part[0] < pg.body_start + 14]
        assert [p[0] - pg.body_start for p in marker_parts] == [4, 6, 8, 10, 12]
        assert all(len(p[3]) == 2 and p[1] == "mov_imm" for p in marker_parts)
        under_test = [r for r in rows if pg.body_start <= r["offset"] < pg.body_end]
        assert under_test[0]["actual_bytes"] == expected_prefix.hex()
    print("EXP-0227 selftest: 5/5 cases generated; Gate A clean; no donor fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
