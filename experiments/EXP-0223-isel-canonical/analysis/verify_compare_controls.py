#!/usr/bin/env python3
"""Verify C1, stopped C2, and C2B compare-control results."""

import argparse
import json
import re
from collections import defaultdict


RELATIONS = ("lt", "gt", "eq", "sneg_lt", "sneg_gt",
             "flt", "fgt", "feq", "fnan")
HOST = {"lt": 43, "gt": 44, "eq": 44, "sneg_lt": 43, "sneg_gt": 44,
        "flt": 43, "fgt": 44, "feq": 44, "fnan": 44}


def rows(path, arm):
    return [r for r in (json.loads(x) for x in open(path, encoding="utf-8"))
            if r["arm"] == arm]


def integrity(rs, allow_fault=False):
    assert not any(r["outcome"] in ("hang", "measurement_failure", "victim") for r in rs)
    if not allow_fault:
        assert not any(r["outcome"] == "fault" for r in rs)
    assert not any(r["gate_a"]["n_bad"] or r["gate_a"]["n_alias"] or
                   r["donor_fields"] or r["foreign_retries"] or
                   not r.get("sentinel_ok", True) for r in rs)


def actual_u32(row, relation):
    data = bytearray(HOST[relation].to_bytes(4, "little"))
    for i in range(4):
        pair = row.get("observed", {}).get(f"out:{14400 + i}")
        if pair is not None:
            data[i] = pair[1]
    return int.from_bytes(data, "little")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("c1")
    ap.add_argument("c2_partial")
    ap.add_argument("c2b")
    args = ap.parse_args()

    c1 = rows(args.c1, "C1")
    assert len(c1) == 1280
    integrity(c1)
    c1_rel = RELATIONS[:5]
    vectors = {}
    for cc in range(256):
        z = {r["name"].split("_", 2)[2]: r for r in c1
             if r["name"].startswith(f"c1_cc{cc:02x}_")}
        vectors[cc] = tuple(actual_u32(z[rel], rel) for rel in c1_rel)

    # Primary compiler relations. Bits 3/4 alias in this envelope.
    expected = {
        4: (44, 43, 44, 43, 44),  # unsigned GT
        5: (43, 44, 44, 44, 43),  # unsigned LT
        6: (44, 43, 44, 44, 43),  # signed GT
        7: (43, 44, 44, 43, 44),  # signed LT
    }
    for low, vector in expected.items():
        for alias in (0, 8, 16, 24):
            assert vectors[low | alias] == vector
    for cc in range(256):
        if cc & 0x60:
            assert vectors[cc] == (40,) * 5

    c2 = rows(args.c2_partial, "C2")
    assert len(c2) == 1480
    integrity(c2, allow_fault=True)
    by_mode = defaultdict(list)
    for r in c2:
        mode = int(re.search(r"mode([0-9a-f]{2})", r["name"]).group(1), 16)
        by_mode[mode].append(r)
    assert set(by_mode) == set(range(256))
    for mode, rs in by_mode.items():
        assert 2 <= len(rs) <= 9
        if (mode & 3) == 2:
            assert not any(r["outcome"] == "fault" for r in rs)
        else:
            assert all(r["outcome"] == "fault" for r in rs)

    c2b = rows(args.c2b, "C2B")
    assert len(c2b) == 576
    integrity(c2b)
    signatures = defaultdict(list)
    for mode in range(256):
        if (mode & 3) != 2:
            continue
        z = {r["name"].split("_", 2)[2]: r for r in c2b
             if r["name"].startswith(f"c2b_mode{mode:02x}_")}
        signatures[tuple(actual_u32(z[rel], rel) for rel in RELATIONS)].append(mode)

    assert signatures[(43, 44, 44, 43, 44, 43, 44, 44, 44)] == \
        [0x02, 0x0A, 0x12, 0x1A, 0x82, 0x8A, 0x92, 0x9A]
    assert signatures[(44, 44, 43, 44, 44, 44, 44, 43, 44)] == \
        [0x06, 0x0E, 0x16, 0x1E, 0x86, 0x8E, 0x96, 0x9E]
    assert len(signatures) == 6

    # Source-class 100 is the GPR true source with release: r3 reads back zero
    # after every predicate outcome. No other non-destination change occurs.
    for r in c1:
        assert not any(not (14400 <= int(k.split(":")[1]) < 14404)
                       for k in r.get("observed", {})), r["name"]
    for r in c2b:
        mode = int(re.search(r"mode([0-9a-f]{2})", r["name"]).group(1), 16)
        extra = {k: v for k, v in r.get("observed", {}).items()
                 if not (14400 <= int(k.split(":")[1]) < 14404)}
        if (mode & 0xE0) == 0x80:
            assert extra == {"out:14448": [43, 0]}, (r["name"], extra)
        else:
            assert not extra, (r["name"], extra)

    print("PASS: C1 1280; C2 finite boundary 256/256; C2B 576; "
          "integer relational/equality compiler points verified")


if __name__ == "__main__":
    main()
