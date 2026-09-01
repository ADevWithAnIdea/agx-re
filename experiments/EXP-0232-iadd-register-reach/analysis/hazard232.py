#!/usr/bin/env python3
"""Verify EXP-0232's amended G17P destination boundary run."""

import json
import sys
from pathlib import Path


EXPECTED = {
    "h_ctl_pre95": "exact",
    "h_d95": "fault",
    "h_ctl_post95": "exact",
    "h_d96": "fault",
    "h_ctl_post96": "exact",
    "h_d127": "fault",
    "h_ctl_post127": "exact",
}


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: hazard232.py RUN")
    rows = [json.loads(line) for line in open(Path(argv[1]) / "sweep.jsonl")]
    got = {r["name"]: r for r in rows if r.get("arm") == "H"}
    failures = []
    for name, expected in EXPECTED.items():
        rec = got.get(name)
        if rec is None:
            failures.append(name + ":missing")
            continue
        ga = rec.get("gate_a", {})
        body = rec.get("under_test", [])
        if not rec.get("dispatched_bytes_verified") or ga.get("n_bad") != 0 \
                or ga.get("n_alias") != 0 or len(body) != 1 \
                or body[0].get("mnemonic") != "iadd2":
            failures.append(name + ":gate-a")
        ledger = rec.get("ledger", {})
        if rec.get("donor_fields") or ledger.get("COPIED") or ledger.get("CARRIER"):
            failures.append(name + ":donor")
        if expected == "exact":
            if rec.get("status") != "OK" or not rec.get("match"):
                failures.append(name + ":not-exact")
        elif rec.get("outcome") != "fault" or rec.get("status") == "HANG":
            failures.append(name + ":not-contained-fault")
    result = {
        "run": argv[1], "expected": EXPECTED,
        "seen": {name: {"status": rec.get("status"), "outcome": rec.get("outcome"),
                         "match": rec.get("match")}
                 for name, rec in got.items()},
        "failures": failures, "pass": not failures and len(got) == len(EXPECTED),
    }
    out = Path(__file__).with_name("hazard_result.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
