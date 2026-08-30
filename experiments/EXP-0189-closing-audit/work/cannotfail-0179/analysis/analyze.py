#!/usr/bin/env python3
"""EXP-0179 analysis: cross-run gate + per-field metrics.

  python3 analysis/analyze.py --runs g17p_..._run01 g17p_..._run02 \
                              [--out analysis/gate.json]

Computes, per (field, carrier):
  values_dispatched   -- distinct field values with at least one VALID case
  distinct_bytes      -- distinct hex encodings of the instruction under test
  agreement           -- fraction of values whose (outcome, facts-signature)
                         agree across the two runs, VALID cases only
  movement            -- values whose signature differs from the field's
                         BASELINE value signature (host-known baseline, not a
                         GPU-refreshed one)
  disagreements       -- values that differ across runs
  promotable          -- agreement >= 0.99 AND movement >= 2 * disagreements

`rt_ok` is present in the raw and is READ BY NOTHING here
(FIELD-SWEEP-PROTOCOL 3b: a round trip is not an emitter gate).
"""
from __future__ import print_function

import argparse
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent

BASELINE_VALUE = {"call.b3": 0x1a, "call.b5": 0x00, "call.b6": 0x56,
                  "call.tail": 0x00, "ret.scoreboard": 0x00,
                  "ret.linkmode": 0x02}
AGREEMENT_MIN = 0.99
MOVEMENT_RATIO_MIN = 2.0


def sig(rec):
    """The comparable signature of a case: what the hardware DID, not how the
    harness felt about it."""
    f = rec.get("facts") or {}
    return (rec.get("outcome"),
            f.get("callee_ran"), f.get("returned"), f.get("landing"),
            tuple(f.get("collateral") or []),
            (rec.get("observed") or {}).get("regs") and
            tuple((rec.get("observed") or {}).get("regs")))


def load(run):
    p = EXP / "raw" / run / "sweep.jsonl"
    out = []
    if not p.exists():
        return out
    for ln in p.read_text().splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", default=str(HERE / "gate.json"))
    args = ap.parse_args()

    runs = {r: load(r) for r in args.runs}
    for r, recs in runs.items():
        print("%s: %d records" % (r, len(recs)))

    # index: (field_key, carrier, value) -> per-run record
    idx = defaultdict(dict)
    fields = set()
    carriers = defaultdict(set)
    falsifiers = defaultdict(lambda: defaultdict(list))
    for r, recs in runs.items():
        for rec in recs:
            if rec.get("skipped"):
                continue
            fk = "%s.%s" % (rec.get("instr"), rec.get("field"))
            if rec.get("falsifier"):
                falsifiers[r][fk].append(rec)
            if not isinstance(rec.get("value"), int):
                continue
            if rec.get("width") != 8:
                continue
            fields.add(fk)
            carriers[fk].add(rec["carrier"])
            idx[(fk, rec["carrier"], rec["value"])][r] = rec

    report = {"runs": args.runs, "agreement_min": AGREEMENT_MIN,
              "movement_ratio_min": MOVEMENT_RATIO_MIN,
              "note": "rt_ok is present in the raw and is read by NOTHING here "
                      "(FIELD-SWEEP-PROTOCOL 3b).",
              "fields": {}}

    for fk in sorted(fields):
        base_v = BASELINE_VALUE.get(fk)
        per_carrier = {}
        for car in sorted(carriers[fk]):
            vals = sorted(v for (f, c, v) in idx if f == fk and c == car)
            valid_vals = []
            distinct_bytes = set()
            agree = 0
            compared = 0
            disagree_vals = []
            sigs = {}
            outcomes = defaultdict(int)
            hangs = []
            for v in vals:
                per_run = idx[(fk, car, v)]
                recs = [per_run[r] for r in args.runs if r in per_run]
                if not recs:
                    continue
                for rec in recs:
                    if rec.get("bytes"):
                        distinct_bytes.add(rec["bytes"])
                    outcomes[rec.get("outcome")] += 1
                    if rec.get("outcome") == "hang":
                        hangs.append(v)
                vrecs = [rec for rec in recs if rec.get("validity") == "valid"]
                if vrecs:
                    valid_vals.append(v)
                    sigs[v] = sig(vrecs[0])
                if len(recs) >= 2 and all(rec.get("validity") == "valid"
                                          for rec in recs):
                    compared += 1
                    if sig(recs[0]) == sig(recs[1]):
                        agree += 1
                    else:
                        disagree_vals.append(v)
            base_sig = sigs.get(base_v)
            moved = [v for v, s in sigs.items()
                     if base_sig is not None and s != base_sig]
            agreement = (agree / float(compared)) if compared else 0.0
            disagreements = len(disagree_vals)
            promotable = (compared > 0 and agreement >= AGREEMENT_MIN
                          and (disagreements == 0
                               or len(moved) >= MOVEMENT_RATIO_MIN * disagreements))
            per_carrier[car] = {
                "values_dispatched": len(valid_vals),
                "values_seen": len(vals),
                "distinct_bytes": len(distinct_bytes),
                "encodable_range": 256,
                "cross_run_compared": compared,
                "agreement": round(agreement, 6),
                "disagreements": disagreements,
                "disagreeing_values": disagree_vals[:64],
                "movement": len(moved),
                "moved_values": moved[:64],
                "baseline_value": base_v,
                "baseline_signature_present": base_sig is not None,
                "outcomes": dict(outcomes),
                "hang_values": sorted(set(hangs)),
                "contiguous_hang_run": _contiguous(sorted(set(hangs))),
                "promotable": bool(promotable),
            }
        n_ok = sum(1 for c in per_carrier.values() if c["promotable"])
        report["fields"][fk] = {
            "carriers": per_carrier,
            "n_carriers": len(per_carrier),
            "n_promotable_carriers": n_ok,
            "gate_pass": bool(n_ok >= 2),
        }

    report["falsifiers"] = {
        r: {fk: [{"field": x.get("field"), "value": x.get("value"),
                  "outcome": x.get("outcome"), "facts": x.get("facts"),
                  "carrier": x.get("carrier")} for x in recs]
            for fk, recs in d.items()}
        for r, d in falsifiers.items()}

    Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True))
    print("wrote", args.out)
    for fk, d in sorted(report["fields"].items()):
        print("  %-18s carriers=%d promotable=%d gate=%s"
              % (fk, d["n_carriers"], d["n_promotable_carriers"], d["gate_pass"]))


def _contiguous(vals):
    """Longest run of consecutive integers -- the CONTIGUOUS-HAZARD detector
    FIELD-SWEEP-PROTOCOL 3(c) requires. A long run means a per-value hang budget
    CANNOT characterise the region and a named mapping pass is needed."""
    if not vals:
        return {"longest": 0, "start": None}
    best = cur = 1
    bstart = start = vals[0]
    for i in range(1, len(vals)):
        if vals[i] == vals[i - 1] + 1:
            cur += 1
        else:
            cur = 1
            start = vals[i]
        if cur > best:
            best, bstart = cur, start
    return {"longest": best, "start": bstart}


if __name__ == "__main__":
    main()
