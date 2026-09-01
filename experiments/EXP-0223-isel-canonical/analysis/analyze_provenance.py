#!/usr/bin/env python3
"""Verify EXP-0223 P1's load-provenance partition from a raw sweep."""

import argparse
import json
import re


OLD = {1: 41, 2: 42, 3: 43, 4: 44}


def actual_byte(row, offset, expected):
    pair = row.get("observed", {}).get(f"out:{offset}")
    return expected if pair is None else pair[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep")
    args = ap.parse_args()
    rows = [json.loads(line) for line in open(args.sweep, encoding="utf-8")]
    rows = [r for r in rows if r["arm"] == "P1"]
    assert len(rows) == 256
    assert not any(r["outcome"] in ("fault", "hang", "measurement_failure", "victim")
                   for r in rows)
    assert not any(r["gate_a"]["n_bad"] or r["gate_a"]["n_alias"] or
                   r["donor_fields"] or r["foreign_retries"] or
                   not r["sentinel_ok"] for r in rows)

    good = bad = collateral = 0
    for r in rows:
        flags = int(re.search(r"_f([0-9a-f]{2})_", r["name"]).group(1), 16)
        canonical = (flags & 0xE0) == 0xC0
        loaded = ([int(r["name"][-1])] if "_one_" in r["name"]
                  else [1, 2, 3, 4])
        direction = "true" if "_true_" in r["name"] else "false"

        if canonical:
            assert r["match"], r["name"]
            good += 1
            continue

        assert not r["match"], r["name"]
        bad += 1
        # Every explicit load is lost: its destination retains the unique old
        # mov_imm seed.  The expected byte is the first member of the diff.
        for reg in loaded:
            off = 14400 + 16 * reg
            pair = r["observed"].get(f"out:{off}")
            assert pair is not None and pair[1] == OLD[reg], (r["name"], reg, pair)

        expected_d = ((73 if (3 in loaded) else 43) if direction == "true"
                      else (74 if (4 in loaded) else 44))
        got_d = actual_byte(r, 14400, expected_d)
        assert got_d == (43 if direction == "true" else 44), (r["name"], got_d)

        extra = {k: v for k, v in r["observed"].items()
                 if int(k.split(":")[1]) >= 14656}
        if extra:
            assert extra == {"out:14656": [100, 0], "out:14672": [101, 0],
                             "out:14688": [102, 0]}, (r["name"], extra)
            collateral += 1

    assert (good, bad, collateral) == (32, 224, 5)
    print("PASS: canonical 32/32; noncanonical 224/224 lose explicit loads; "
          "5 also lose r16..r18")


if __name__ == "__main__":
    main()
