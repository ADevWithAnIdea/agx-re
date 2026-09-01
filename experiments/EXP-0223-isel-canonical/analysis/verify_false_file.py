#!/usr/bin/env python3
"""Verify S1's false-source class and release map."""

import argparse
import json


def actual_reg(row, reg, expected):
    data = bytearray(expected.to_bytes(4, "little"))
    base = 14400 + (16 * reg)
    for i in range(4):
        pair = row.get("observed", {}).get(f"out:{base + i}")
        if pair is not None:
            data[i] = pair[1]
    return int.from_bytes(data, "little")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep")
    args = ap.parse_args()
    rows = [r for r in (json.loads(x) for x in open(args.sweep, encoding="utf-8"))
            if r["arm"] == "S1"]
    assert len(rows) == 512
    assert not any(r["outcome"] in ("fault", "hang", "measurement_failure", "victim")
                   for r in rows)
    assert not any(r["gate_a"]["n_bad"] or r["gate_a"]["n_alias"] or
                   r["donor_fields"] or r["foreign_retries"] or
                   not r["sentinel_ok"] for r in rows)

    for row in rows:
        ff = int(row["name"][5:7], 16)
        direction = "true" if row["name"].endswith("_true") else "false"
        source_class = ff >> 5
        if direction == "true":
            want_d = 43
        elif source_class in (0, 4):
            want_d = 44
        elif source_class == 1:
            want_d = 0x0001D500
        else:
            want_d = 0
        want_f = 0 if source_class == 4 else 44
        assert actual_reg(row, 0, 43 if direction == "true" else 44) == want_d, row["name"]
        assert actual_reg(row, 4, 44) == want_f, row["name"]

        allowed = set(range(14400, 14404)) | set(range(14464, 14468))
        assert not any(int(k.split(":")[1]) not in allowed
                       for k in row.get("observed", {})), row["name"]

    print("PASS: 512/512; false-source classes and unconditional F release exact")


if __name__ == "__main__":
    main()
