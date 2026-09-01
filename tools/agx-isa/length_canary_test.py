#!/usr/bin/env python3
"""Check canonical Apple9 framing witnesses.

The built-in ledger is tools/agx-isa/length_canaries.json.  A future hardware
experiment can add experiments/EXP-*/framing_canaries.json with the same
top-level schema; this test discovers it automatically.
"""

import json
import sys
from pathlib import Path

import isadb


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def ledgers():
    yield HERE / "length_canaries.json"
    yield from sorted((ROOT / "experiments").glob("EXP-*/framing_canaries.json"))


def main():
    failures = []
    seen = set()
    count = 0

    for path in ledgers():
        doc = json.loads(path.read_text())
        if doc.get("schema") != 1 or not isinstance(doc.get("cases"), list):
            failures.append(f"{path}: unsupported schema")
            continue

        for case in doc["cases"]:
            count += 1
            cid = case["id"]
            key = f"{path.relative_to(ROOT)}::{cid}"
            if key in seen:
                failures.append(f"{key}: duplicate id")
                continue
            seen.add(key)

            raw = bytes.fromhex(case["hex"])
            expected = case["length"]
            got = isadb.instr_length(raw, 0)
            if got != expected:
                failures.append(f"{key}: length {got}, expected {expected}")
                continue
            if len(raw) < expected:
                failures.append(f"{key}: witness shorter than its expected instruction")
                continue

            try:
                rec, decoded = isadb.decode_one(raw, 0)
            except Exception as exc:
                failures.append(f"{key}: decode failed: {exc}")
                continue
            if decoded != expected:
                failures.append(f"{key}: decoder consumed {decoded}, expected {expected}")
                continue

            mnemonic = case.get("mnemonic")
            if mnemonic is not None and rec["mnemonic"] != mnemonic:
                failures.append(
                    f"{key}: decoded {rec['mnemonic']}, expected {mnemonic}"
                )
                continue

            if case.get("roundtrip", True):
                try:
                    rebuilt = isadb.assemble(rec["mnemonic"], rec["fields"])
                except Exception as exc:
                    failures.append(f"{key}: reassembly failed: {exc}")
                    continue
                if rebuilt != raw[:expected]:
                    failures.append(
                        f"{key}: reassembly {rebuilt.hex()} != {raw[:expected].hex()}"
                    )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"{len(failures)} failure(s), {count} case(s)")
        return 1

    print(f"PASS {count} framing canaries from {len(list(ledgers()))} ledger(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
