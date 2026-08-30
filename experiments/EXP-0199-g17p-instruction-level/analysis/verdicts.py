#!/usr/bin/env python3
"""verdicts.py -- EXP-0199 analysis. **SUPERSEDED by analysis/gates.py**, which scores the
AMENDMENT-01 gated confirmation captures against the five gates of
RE_EXPERIMENT_PROCESS_CORRECTIONS.md. Retained because it is the analysis the ORIGINAL
frozen contract specified, and the original contract and its captures are retained too.
It reads the two DISCOVERY runs (g17p_run01* / g17p_run02*) and writes
analysis/gate_report_original_contract.json -- a DIFFERENT file from gates.py's
analysis/gate_report.json, so running it can never overwrite the amended analysis.

The gate, verbatim from CAPTURE_CONTRACT.json:
  * two runs;
  * per-value cross-run agreement >= 0.99;
  * movement rule  `moved >= 2.0 * disagree AND moved > 0`  -- deliberately NOT
    `moved >= 2.0 * max(disagree, 1)`, which cannot promote a width-1 field by
    arithmetic (FIELD-SWEEP-PROTOCOL sec.5b);
  * measurement failures are EXCLUDED from agreement and from values_dispatched
    (DEF-0178-1), and a field whose measurement-failure rate exceeds 1% is refused.

    python3 analysis/verdicts.py
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
RAW = os.path.join(EXP, "raw")
RUN1 = ["g17p_run01a", "g17p_run01b", "g17p_run01c"]
RUN2 = ["g17p_run02a", "g17p_run02b", "g17p_run02c"]
MEAS_FAIL = {"measurement_failed"}


def load(ids):
    out = {}
    meta = {}
    for rid in ids:
        p = os.path.join(RAW, rid, "sweep.jsonl")
        if not os.path.exists(p):
            continue
        for ln in open(p):
            r = json.loads(ln)
            out[r["case"]] = r
            meta[r["case"]] = rid
    return out, meta


def key(r):
    """The observation used for cross-run agreement: outcome + the surface
    identity.  Faults compare on their OS classification, not their text."""
    o = r["outcome"]
    ob = r.get("observed", {})
    if o in ("fault", "hang"):
        return (o, r.get("errdom", ""))
    if "h" in ob:
        return (o, ob["h"])
    if "ph" in ob and "dh" in ob:
        return (o, ob["ph"], ob["dh"])
    if "ph" in ob:
        return (o, ob["ph"])
    return (o,)


def main():
    A, _ = load(RUN1)
    B, _ = load(RUN2)
    common = sorted(set(A) & set(B))
    print("run01 cases %d  run02 cases %d  common %d" % (len(A), len(B), len(common)))

    # ---- per (instr, field, site) tallies -------------------------------
    groups = collections.defaultdict(list)
    for c in common:
        r = A[c]
        if not r.get("field"):
            continue
        groups[(r.get("instr"), r["field"], r.get("site"))].append(c)

    report = {}
    for g, cases in sorted(groups.items(), key=str):
        instr, field, site = g
        n = agree = disagree = mf = moved = 0
        outc = collections.Counter()
        accepted = []
        for c in cases:
            ra, rb = A[c], B[c]
            if ra["outcome"] in MEAS_FAIL or rb["outcome"] in MEAS_FAIL:
                mf += 1
                continue
            n += 1
            outc[ra["outcome"]] += 1
            if key(ra) == key(rb):
                agree += 1
            else:
                disagree += 1
            if ra["outcome"] != "ok":
                moved += 1
            else:
                accepted.append(ra.get("value"))
        report["%s.%s@%s" % (instr, field, site)] = dict(
            n=n, agree=agree, disagree=disagree, measurement_failed=mf,
            agreement=round(agree / n, 5) if n else None,
            moved=moved, outcomes=dict(outc),
            accepted_values=accepted if len(accepted) <= 64 else
            ("%d values" % len(accepted)),
            gate_movement=(moved >= 2.0 * disagree and moved > 0),
            gate_agreement=(n > 0 and agree / n >= 0.99),
            gate_measfail=(mf <= 0.01 * max(len(cases), 1)))
    return A, B, common, report


def mask_of(vals):
    """The tightest (mask, value) rule that admits exactly `vals` over 0..255,
    or None if no single mask/value rule fits.  Reported as evidence about what
    the hardware ACCEPTS, to be compared with db.json's declared match bits."""
    if not vals:
        return None
    vals = sorted(set(vals))
    ones = 0xFF
    zeros = 0xFF
    for v in vals:
        ones &= v
        zeros &= (~v) & 0xFF
    mask = ones | zeros
    val = vals[0] & mask
    admitted = [v for v in range(256) if (v & mask) == val]
    return dict(mask="0x%02x" % mask, value="0x%02x" % val,
                exact=(admitted == vals), n_admitted=len(admitted),
                n_observed=len(vals))


if __name__ == "__main__":
    A, B, common, report = main()
    for k, v in report.items():
        acc = v["accepted_values"]
        m = mask_of(acc) if isinstance(acc, list) and acc and \
            all(isinstance(x, int) for x in acc) else None
        print("%-46s n=%-4d agree=%-7s moved=%-4d disagree=%-3d mf=%d  %s" %
              (k, v["n"], v["agreement"], v["moved"], v["disagree"],
               v["measurement_failed"], json.dumps(v["outcomes"])))
        if m:
            print("      accepted(ok) = %s  -> rule (v & %s) == %s  exact=%s" %
                  (acc if len(acc) <= 40 else "%d values" % len(acc),
                   m["mask"], m["value"], m["exact"]))
    json.dump(report, open(os.path.join(HERE, "gate_report_original_contract.json"), "w"), indent=1)
    print("\nwrote analysis/gate_report_original_contract.json")
