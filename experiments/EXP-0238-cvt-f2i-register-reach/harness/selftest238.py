#!/usr/bin/env python3
"""Offline geometry/provenance checks for EXP-0238."""

import run238 as X


def main():
    slots = {"out": 0, "mem": 1, "imem": 2}
    cases = X.build_cases()
    main_cases = [c for c in cases if c["arm"] in ("S", "D", "L")]
    controls = [c for c in cases if c["arm"] == "CTL"]
    assert len(main_cases) == 456 and len(controls) == 2
    assert len({c["code"] for c in main_cases if c["role"] == "source"}) == 256
    assert len({c["code"] for c in main_cases if c["role"] == "destination"}) == 192
    for case in main_cases + controls:
        pg, prog = X.build_program_for(case, slots, 4096)
        rows, bad, alias = X.S.gate_a_ledger(prog, pg.E.parts)
        body = [r for r in rows if pg.body_start <= r["offset"] < pg.body_end]
        assert not bad, (case["name"], bad)
        assert not alias, (case["name"], alias)
        assert len(body) == 1 and body[0]["mnemonic"] == "cvt_f2i", (case["name"], body)
        assert pg.body_end - pg.body_start == 10
        assert pg.E.led.counts()[X.S.COPIED] == 0
        assert pg.E.led.counts()[X.S.CARRIER] == 0
        actual = bytes.fromhex(body[0]["actual_bytes"])
        if case["role"] == "source":
            assert actual[5] == case["code"]
        elif case["role"] == "destination":
            assert actual[3] == case["code"]
        else:
            assert actual[3] == case["register"] << 1
            assert actual[5] == case["register"] << 2
    print("PASS: 456 positive cases and two controls generate one exact 10B cvt_f2i with zero donor fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
