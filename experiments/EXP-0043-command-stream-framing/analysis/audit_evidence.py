#!/usr/bin/env python3
"""Audit raw EXP-0043 capture completeness without interpreting payloads."""

from __future__ import annotations

import argparse
import pathlib
import re

HEADER = re.compile(r"size=0x([0-9a-fA-F]+) read=0x([0-9a-fA-F]+)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=pathlib.Path)
    args = parser.parse_args()
    run = args.run
    snapshots = incomplete = malformed = 0
    for path in sorted(run.glob("cases/*/dumps/dump*/*.hex")):
        snapshots += 1
        with path.open(errors="replace") as stream:
            header = stream.readline()
        match = HEADER.search(header)
        if not match:
            malformed += 1
            print(f"MALFORMED_SNAPSHOT {path}")
        elif int(match.group(1), 16) != int(match.group(2), 16):
            incomplete += 1
            print(f"INCOMPLETE_SNAPSHOT {path} {match.group(0)}")

    exits = failures = 0
    for path in sorted(run.glob("cases/*/exit-status.txt")):
        exits += 1
        try:
            value = int(path.read_text().strip())
        except ValueError:
            value = -1
        if value:
            failures += 1
            print(f"NONZERO_EXIT {path} value={value}")

    traces = list(run.glob("cases/*/iotrace.log"))
    empty_traces = [path for path in traces if path.stat().st_size == 0]
    for path in empty_traces:
        print(f"EMPTY_TRACE {path}")
    print(
        f"SUMMARY run={run.name} snapshots={snapshots} incomplete={incomplete} "
        f"malformed={malformed} cases={exits} nonzero_exits={failures} "
        f"traces={len(traces)} empty_traces={len(empty_traces)}"
    )
    return int(bool(incomplete or malformed or failures or empty_traces or not snapshots))


if __name__ == "__main__":
    raise SystemExit(main())
