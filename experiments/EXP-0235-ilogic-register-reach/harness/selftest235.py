#!/usr/bin/env python3
"""Offline geometry/provenance checks for EXP-0235."""

import run235 as X


def main():
    cases = X.build_cases()
    main_cases = [c for c in cases if c["arm"] in ("A", "B", "D")]
    controls = [c for c in cases if c["arm"] == "CTL"]
    assert len(main_cases) == 48 and len(controls) == 2
    slots = {"out": 0, "mem": 1, "imem": 2}
    for case in main_cases + controls:
        pg, prog = X.build_program_for(case, slots, 4096)
        rows, bad, alias = X.S.gate_a_ledger(prog, pg.E.parts)
        body = [r for r in rows if pg.body_start <= r["offset"] < pg.body_end]
        assert not bad, (case["name"], bad)
        assert not alias, (case["name"], alias)
        assert len(body) == 1 and body[0]["mnemonic"] == "ilogic", (case["name"], body)
        assert pg.E.led.counts()[X.S.COPIED] == 0
        assert pg.E.led.counts()[X.S.CARRIER] == 0
    print("PASS: 48 sparse main + 2 controls generate and frame with zero donor fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
