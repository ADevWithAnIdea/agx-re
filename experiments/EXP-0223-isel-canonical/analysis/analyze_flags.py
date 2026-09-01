#!/usr/bin/env python3
"""Recompute EXP-0223 L1's flags-byte partition from the raw capture."""

import argparse
import json
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep")
    args = ap.parse_args()
    rows = [json.loads(line) for line in open(args.sweep, encoding="utf-8")]
    rows = [r for r in rows if r["arm"] == "L1"]
    assert len(rows) == 512
    assert not any(r["outcome"] in ("fault", "hang", "measurement_failure", "victim")
                   for r in rows)
    assert not any(r["gate_a"]["n_bad"] or r["gate_a"]["n_alias"] or
                   r["donor_fields"] or r["foreign_retries"] or
                   not r["sentinel_ok"] for r in rows)

    for direction in ("true", "false"):
        groups = defaultdict(list)
        for r in rows:
            if not r["name"].endswith("_" + direction):
                continue
            flags = int(r["name"][8:10], 16)
            old = 40
            t, f = 43, 44
            got = t if direction == "true" else f
            for key, values in r.get("observed", {}).items():
                if key == "out:14400":
                    got = values[1]
            groups[got].append(flags)

            if flags & 0x10:
                predicted = old
            elif (flags & 0x7) == 0:
                predicted = t if direction == "true" else f
            elif flags & 0x4:
                predicted = f
            else:
                predicted = t
            assert got == predicted, (direction, flags, got, predicted)

            # The only observed byte may be the destination's low byte.  In
            # particular no source-dump byte changed in this carrier.
            assert all(key == "out:14400" for key in r.get("observed", {}))

        print(direction, {got: len(values) for got, values in sorted(groups.items())})

    print("PASS: 512/512 accepted; exact flags model; integrity gates clean")


if __name__ == "__main__":
    main()
