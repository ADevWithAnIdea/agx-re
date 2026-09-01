#!/usr/bin/env python3
"""Offline geometry/provenance checks for EXP-0231."""

import run231 as X


def main():
    cases = X.build_cases()
    main = [c for c in cases if c["arm"] == "M"]
    controls = [c for c in cases if c["arm"] == "CTL"]
    assert len(main) == 144
    assert len(controls) == 2
    assert len({(c["source"], c["destination"], c["gap"]) for c in main}) == 144
    slots = {"out": 0, "mem": 1, "imem": 2}
    for case in main + controls:
        pg, prog = X.build_program_for(case, slots, 4096)
        rows, bad, alias = X.S.gate_a_ledger(prog, pg.E.parts)
        body = [r for r in rows if pg.body_start <= r["offset"] < pg.body_end]
        assert not bad, (case["name"], bad)
        assert not alias, (case["name"], alias)
        assert len(body) == case["gap"] + 2, (case["name"], body)
        assert body[0]["mnemonic"] == "device_store"
        assert body[-1]["mnemonic"] == "device_load"
        assert pg.E.led.counts()[X.S.COPIED] == 0
        assert pg.E.led.counts()[X.S.CARRIER] == 0
    print("PASS: 144 main + 2 controls generate, frame, and use no donor fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
