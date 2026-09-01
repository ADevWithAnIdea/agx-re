#!/usr/bin/env python3
"""Offline geometry and provenance checks for EXP-0233."""

import run233 as X


def main():
    cases = X.build_cases(include_hazard=True)
    main = [c for c in cases if c["arm"] in ("X", "Y", "D")]
    controls = [c for c in cases if c["arm"] == "CTL"]
    hazards = [c for c in cases if c["arm"] == "H"]
    assert len(main) == 192 and len(controls) == 2
    assert len(hazards) == 5
    slots = {"out": 0, "mem": 1, "imem": 2}
    for case in main + controls + hazards:
        pg, prog = X.build_program_for(case, slots, 4096)
        rows, bad, alias = X.S.gate_a_ledger(prog, pg.E.parts)
        body = [r for r in rows if pg.body_start <= r["offset"] < pg.body_end]
        assert not bad, (case["name"], bad)
        assert not alias, (case["name"], alias)
        assert len(body) == 1 and body[0]["mnemonic"] == "imad", (case["name"], body)
        assert pg.E.led.counts()[X.S.COPIED] == 0
        assert pg.E.led.counts()[X.S.CARRIER] == 0
    print("PASS: 192 main + 2 controls + 5 boundary cases generate and frame with zero donor fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
