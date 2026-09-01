#!/usr/bin/env python3
"""Formal two-run G17P canonical isel10 source-boundary gate for EXP-0234."""

import json
import sys
from pathlib import Path


EXPECTED = {}
for short in ("a", "b", "t", "f"):
    EXPECTED.update({
        "h_%s_ctl_pre96" % short: "exact",
        "h_%s_r96" % short: "fault",
        "h_%s_ctl_mid96" % short: "exact",
        "h_%s_r127" % short: "fault",
        "h_%s_ctl_post127" % short: "exact",
    })


def load(path):
    rows = [json.loads(line) for line in open(Path(path) / "sweep.jsonl")]
    return {r["name"]: r for r in rows if r.get("arm") == "H"}


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: boundary232.py RUN01 RUN02")
    a, b = load(argv[1]), load(argv[2])
    failures = []
    for name, expected in EXPECTED.items():
        if name not in a or name not in b:
            failures.append(name + ":missing")
            continue
        ra, rb = a[name], b[name]
        for rec in (ra, rb):
            ga = rec.get("gate_a", {})
            body = rec.get("under_test", [])
            if not rec.get("dispatched_bytes_verified") or ga.get("n_bad") != 0 \
                    or ga.get("n_alias") != 0 or len(body) != 1 \
                    or body[0].get("mnemonic") != "isel10":
                failures.append(name + ":gate-a")
            ledger = rec.get("ledger", {})
            if rec.get("donor_fields") or ledger.get("COPIED") or ledger.get("CARRIER"):
                failures.append(name + ":donor")
            if expected == "exact" and (rec.get("status") != "OK" or not rec.get("match")):
                failures.append(name + ":not-exact")
            if expected == "fault" and (rec.get("outcome") != "fault"
                                        or rec.get("status") == "HANG"):
                failures.append(name + ":not-contained-fault")
        if ra.get("prog_sha256") != rb.get("prog_sha256") \
                or ra.get("under_test") != rb.get("under_test"):
            failures.append(name + ":byte-disagreement")
        if expected == "exact" and ra.get("isel_reach_probe", {}).get("observed") \
                != rb.get("isel_reach_probe", {}).get("observed"):
            failures.append(name + ":observation-disagreement")
    result = {
        "runs": argv[1:], "expected": EXPECTED, "failures": failures,
        "pass": not failures and set(a) == set(EXPECTED) and set(b) == set(EXPECTED),
    }
    out = Path(__file__).with_name("boundary_result.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
