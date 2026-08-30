#!/usr/bin/env python3
"""EXP-0157: adjudicate the lease-held fault-confirmation pass (FIELD-SWEEP-PROTOCOL 7A).

EXP-0153 showed that majority-of-3 in an unlocked run, even when two independent
runs agree, is NOT sufficient for a `fault` verdict: four of its five "faults"
were `wrong_value` when re-run 5x under the GPU lease. So every `fault`/`hang`
in this experiment's gated captures is re-run 5x under `~/agxre/gpulease.sh`,
and this script reports, per field, how many of those held up.

A case is CONFIRMED a fault if a majority of its lease repeats faulted, and
REFUTED (re-classified) otherwise. Cases the pass did not reach are reported as
UNCONFIRMED -- never silently treated as confirmed.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(p):
    p = Path(p)
    out = []
    for f in (sorted(p.rglob("sweep.jsonl")) if p.is_dir() else [p]):
        for line in open(f):
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def key(r):
    return (r["arm"], r["carrier"], r["instr"], r["anchor_idx"], r["field"], r["value"])


def main():
    gated = []
    for p in sys.argv[1:-1]:
        gated += load(p)
    reval = load(sys.argv[-1])

    claimed = {}
    for r in gated:
        if str(r.get("field", "")).startswith("_"):
            continue
        if r["outcome"] in ("fault", "hang", "nondeterministic"):
            claimed.setdefault(key(r), r["outcome"])

    reps = collections.defaultdict(list)
    for r in reval:
        if str(r.get("field", "")).startswith("_"):
            continue
        reps[key(r)].append(r["outcome"])

    per_field = collections.defaultdict(lambda: collections.Counter())
    detail = {}
    for k, oc in claimed.items():
        rs = reps.get(k)
        f = "%s.%s@%s" % (k[2], k[4], k[1])
        if not rs:
            per_field[f]["unconfirmed"] += 1
            continue
        nf = sum(1 for x in rs if x in ("fault", "hang"))
        if nf * 2 > len(rs):
            per_field[f]["confirmed"] += 1
        else:
            per_field[f]["refuted"] += 1
            detail.setdefault(f, []).append(
                {"value": k[5], "gated": oc, "lease_repeats": rs})

    tot = collections.Counter()
    for f, c in per_field.items():
        tot.update(c)
    report = {"_doc": __doc__.strip(),
              "totals": dict(tot),
              "per_field": {f: dict(c) for f, c in sorted(per_field.items())},
              "refuted_examples": {f: v[:8] for f, v in sorted(detail.items())}}
    Path(HERE / "fault_confirmation.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n")
    print("claimed fault/hang cases: %d" % len(claimed))
    print("totals:", dict(tot))
    for f, c in sorted(per_field.items()):
        if c.get("refuted") or c.get("unconfirmed"):
            print("  %-34s %s" % (f, dict(c)))


if __name__ == "__main__":
    main()
