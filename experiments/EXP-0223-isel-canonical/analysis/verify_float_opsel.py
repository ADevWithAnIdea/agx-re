#!/usr/bin/env python3
"""Verify F1 float semantics and compare-source release controls."""

import argparse
import json
import re
import struct


def fbits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


EXPECTED = {
    "fpos_lt": (fbits(1.0), fbits(2.0), 43),
    "fneg_lt": (fbits(-2.0), fbits(-1.0), 44),
    "fneg_gt": (fbits(-1.0), fbits(-2.0), 43),
    "fzero": (fbits(-0.0), fbits(0.0), 43),
    "fnan": (0x7FC00000, fbits(1.0), 44),
    "feq": (fbits(1.0), fbits(1.0), 44),
    "fneq": (fbits(1.0), fbits(2.0), 43),
}


def actual_reg(row, reg, expected):
    data = bytearray(expected.to_bytes(4, "little"))
    base = 14400 + (16 * reg)
    for i in range(4):
        pair = row.get("observed", {}).get(f"out:{base + i}")
        if pair is not None:
            data[i] = pair[1]
    return int.from_bytes(data, "little")


def relation(row):
    return next(rel for rel in EXPECTED if row["name"].endswith("_" + rel))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep")
    args = ap.parse_args()
    rows = [r for r in (json.loads(x) for x in open(args.sweep, encoding="utf-8"))
            if r["arm"] == "F1"]
    assert len(rows) == 448
    assert not any(r["outcome"] in ("fault", "hang", "measurement_failure", "victim")
                   for r in rows)
    assert not any(r["gate_a"]["n_bad"] or r["donor_fields"] or
                   r["foreign_retries"] or not r["sentinel_ok"] for r in rows)

    clean = {0, 1, 2, 3, 6, 7}
    for row in rows:
        op = int(re.search(r"_op([0-9a-f]{2})_", row["name"]).group(1), 16)
        aliases = row["gate_a"]["n_alias"]
        if op in clean:
            assert aliases == 0, row["name"]
        elif op in (4, 5):
            assert aliases == 1 and row["gate_a"]["alias"][0]["kind"] == \
                "descriptor_ambiguity", row["name"]
        else:
            assert aliases > 0, row["name"]

    expected_result = {
        "cc2": {"fpos_lt": 44, "fneg_lt": 44, "fneg_gt": 43,
                "fzero": 44, "fnan": 44},
        "cc3": {"fpos_lt": 43, "fneg_lt": 43, "fneg_gt": 44,
                "fzero": 44, "fnan": 44},
        "eq": {"feq": 43, "fneq": 44, "fzero": 43, "fnan": 44},
    }
    releases = {0: (False, False), 1: (True, False),
                2: (False, True), 3: (True, True),
                6: (False, True), 7: (True, True)}

    for row in rows:
        op = int(re.search(r"_op([0-9a-f]{2})_", row["name"]).group(1), 16)
        if op not in clean:
            continue
        rel = relation(row)
        group = "eq" if "_eq_" in row["name"] else \
            ("cc2" if "_cc2_" in row["name"] else "cc3")
        a, b, host_d = EXPECTED[rel]
        assert actual_reg(row, 0, host_d) == expected_result[group][rel], row["name"]
        release_a, release_b = releases[op]
        assert actual_reg(row, 1, a) == (0 if release_a else a), row["name"]
        assert actual_reg(row, 2, b) == (0 if release_b else b), row["name"]

        allowed = set(range(14400, 14404))
        if release_a:
            allowed.update(range(14416, 14420))
        if release_b:
            allowed.update(range(14432, 14436))
        assert not any(int(k.split(":")[1]) not in allowed
                       for k in row.get("observed", {})), row["name"]

    print("PASS: 84 clean generated cases; float GT/LT/EQ; opsel source-release map")


if __name__ == "__main__":
    main()
