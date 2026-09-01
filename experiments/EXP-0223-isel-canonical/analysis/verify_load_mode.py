#!/usr/bin/env python3
"""Verify EXP-0223's two P1 runs and D1 distance sweep."""

import argparse
import json
import re


OLD = {1: 41, 2: 42, 3: 43, 4: 44}


def read(path, arm):
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    rows = [r for r in rows if r["arm"] == arm]
    assert not any(r["outcome"] in ("fault", "hang", "measurement_failure", "victim")
                   for r in rows)
    assert not any(r["gate_a"]["n_bad"] or r["gate_a"]["n_alias"] or
                   r["donor_fields"] or r["foreign_retries"] or
                   not r["sentinel_ok"] for r in rows)
    return rows


def flags(row):
    return int(re.search(r"_f([0-9a-f]{2})_", row["name"]).group(1), 16)


def assert_stale(row, loaded):
    for reg in loaded:
        pair = row["observed"].get(f"out:{14400 + (16 * reg)}")
        assert pair is not None and pair[1] == OLD[reg], (row["name"], reg, pair)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("p1_run1")
    ap.add_argument("p1_run2")
    ap.add_argument("d1")
    args = ap.parse_args()

    p1s = [read(args.p1_run1, "P1"), read(args.p1_run2, "P1")]
    for rows in p1s:
        assert len(rows) == 256
        for r in rows:
            if (flags(r) & 0xE0) == 0xC0:
                assert r["match"], r["name"]
            else:
                assert not r["match"], r["name"]
                loaded = ([int(r["name"][-1])] if "_one_" in r["name"]
                          else [1, 2, 3, 4])
                assert_stale(r, loaded)

    by_run = [{r["name"]: r for r in rows} for rows in p1s]
    assert set(by_run[0]) == set(by_run[1])
    assert not any(by_run[0][n]["prog_sha256"] != by_run[1][n]["prog_sha256"]
                   for n in by_run[0])
    canonical_names = [n for n, r in by_run[0].items()
                       if (flags(r) & 0xE0) == 0xC0]
    assert not any(by_run[0][n]["out_sha256"] != by_run[1][n]["out_sha256"]
                   for n in canonical_names)

    d1 = read(args.d1, "D1")
    assert len(d1) == 192
    for r in d1:
        if (flags(r) & 0xE0) == 0xC0:
            assert r["match"], r["name"]
        else:
            assert not r["match"], r["name"]
            gap = int(r["name"].rsplit("gap", 1)[1])
            assert_stale(r, [1, 2, 3] + ([4] if gap < 16 else []))
            # At gap 16 the last-issued load reaches r4 by the later state dump,
            # but the select itself still consumes r4's stale seed.  Its result
            # therefore remains 43/44, never the loaded T/F value 73/74.
            if gap == 16:
                assert f"out:{14400 + (16 * 4)}" not in r["observed"], r["name"]
            direction = "true" if "_true_" in r["name"] else "false"
            expected = 73 if direction == "true" else 74
            pair = r["observed"].get("out:14400")
            got = expected if pair is None else pair[1]
            assert got == (43 if direction == "true" else 44), (r["name"], got)

    print("PASS: P1 canonical 64/64; noncanonical stale 448/448; "
          "D1 canonical 24/24; 168/168 noncanonical selects consume stale values")


if __name__ == "__main__":
    main()
