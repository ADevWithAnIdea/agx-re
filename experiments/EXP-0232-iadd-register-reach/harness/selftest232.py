#!/usr/bin/env python3
"""Offline geometry and provenance checks for EXP-0232."""

import run232 as X


def main():
    cases = X.build_cases(include_hazard=True)
    main = [c for c in cases if c["arm"] in ("A", "B", "D")]
    controls = [c for c in cases if c["arm"] == "CTL"]
    hazards = [c for c in cases if c["arm"] == "H"]
    boundary2 = [c for c in cases if c["arm"] == "H2"]
    assert len(main) == 191 and len(controls) == 2
    assert len(hazards) == 7
    assert len(boundary2) == 5
    slots = {"out": 0, "mem": 1, "imem": 2}
    for case in main + controls + hazards + boundary2:
        pg, prog = X.build_program_for(case, slots, 4096)
        rows, bad, alias = X.S.gate_a_ledger(prog, pg.E.parts)
        body = [r for r in rows if pg.body_start <= r["offset"] < pg.body_end]
        assert not bad, (case["name"], bad)
        assert not alias, (case["name"], alias)
        assert len(body) == 1 and body[0]["mnemonic"] == "iadd2", (case["name"], body)
        assert pg.E.led.counts()[X.S.COPIED] == 0
        assert pg.E.led.counts()[X.S.CARRIER] == 0
    print("PASS: 191 main + 2 controls + 12 boundary cases generate and frame with zero donor fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
