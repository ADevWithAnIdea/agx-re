#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0169 step 0 -- how many of EXP-0164's 144 UNVERIFIABLE fields are
unverifiable only because the field's `evidence` list points at the wrong
experiments?

EXP-0164/analysis/audit.py::gather() collects observations ONLY from the
experiments named in that field's `evidence` array in validation.json:

    for eid in evidence:
        d = resolve(eid)
        if not d or key not in index.get(d, {}): continue

So a field whose promotion cites EXP-0016 is judged on EXP-0016's raw alone,
even when a LATER experiment swept the very same db field, value by value, with
bit-exact attributable records.  That is correct behaviour for an audit of a
*promotion* -- the promotion really was made on the cited evidence -- but it
means some of the 144 need a citation fix, not a device.

This script re-runs EXP-0164's OWN gate (`stable_live`, thresholds frozen in its
PRE_REGISTRATION section 5 and reproduced verbatim below) over the WHOLE raw
index instead of only the cited experiments, and reports, for each of the 144:

  RECOVERABLE-BY-CITATION  an uncited experiment already carries per-value
                           records that pass EXP-0164's own promotion gate;
  RECORDS-BUT-FAILS-GATE   records exist somewhere but do not clear the gate
                           (single gated run, no movement, or < 99% agreement);
  NO-RECORDS-ANYWHERE      no attributable per-value record exists in the whole
                           corpus -- these are the ones that need the device.

READ-ONLY.  Writes analysis/recitation_recovery.json.

Usage:  python3 analysis/collect_raw.py && python3 analysis/recitation.py
"""
import collections
import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
WORK = os.path.join(EXP, "work")
WITHHOLD = os.path.join(EXPDIR, "EXP-0164-inert-audit", "analysis",
                        "withhold_unverifiable.json")

# --- EXP-0164 PRE_REGISTRATION section 5, verbatim -------------------------
NONGATED = re.compile(r"(prefreeze|smoke|pilot|quarantine|burned)", re.I)
MIN_COMMON = 2
MIN_AGREE_PCT = 99.0
MOVED_OVER_DISAGREE = 2.0


def cross_run(runs):
    """EXP-0164/analysis/audit.py::cross_run, verbatim."""
    order = sorted(runs.items(), key=lambda kv: (-kv[1]["n_values"], kv[0]))
    if len(order) < 2:
        return None
    (ra, ea), (rb, eb) = order[0], order[1]
    ka, kb = ea["keys"], eb["keys"]
    common = set(ka) & set(kb)
    agree = sum(1 for k in common if ka[k] == kb[k])
    n = len(common)
    return {"runA": ra, "runB": rb,
            "n_valuesA": ea["n_values"], "n_valuesB": eb["n_values"],
            "movedA": ea["moved"], "movedB": eb["moved"],
            "common": n, "agree": agree, "disagreements": n - agree,
            "agree_pct": round(100.0 * agree / n, 2) if n else None}


def stable_live(c):
    """EXP-0164/analysis/audit.py::stable_live, verbatim."""
    if c is None or c["common"] < MIN_COMMON:
        return False
    if c["movedA"] < 1 or c["movedB"] < 1:
        return False
    if c["agree_pct"] is None or c["agree_pct"] < MIN_AGREE_PCT:
        return False
    return min(c["movedA"], c["movedB"]) >= MOVED_OVER_DISAGREE * c["disagreements"]


def cited(exp_dir, evidence):
    return any(exp_dir == e or exp_dir.startswith(e + "-") for e in evidence)


def main():
    idx = json.load(gzip.open(os.path.join(WORK, "raw_index.json.gz"), "rt"))
    index = idx["index"]
    partial = set(idx["_meta"]["partial_runs"])
    W = json.load(open(WITHHOLD))
    fields = sorted(k for k in W if k != "_meta")

    out = {"_meta": {
        "generated_by": "EXP-0169/analysis/recitation.py",
        "question": ("of EXP-0164's 144 UNVERIFIABLE fields, how many already "
                     "have attributable per-value records in the corpus under an "
                     "experiment their validation.json `evidence` list does not "
                     "cite?"),
        "gate": "EXP-0164 audit.py::stable_live, thresholds copied verbatim",
        "raw_index": "work/raw_index.json.gz (EXP-0164 collect_raw.py, unmodified)",
        "note": ("A PASS here is an AUDITABILITY finding about the citation "
                 "list, not a new hardware claim, and not a substitute for the "
                 "fresh gated capture where the field is load-bearing."),
    }}
    counts = collections.Counter()
    for key in fields:
        ev = W[key]["evidence"]
        hits = []
        any_records = []
        for exp, keys in index.items():
            if key not in keys:
                continue
            for arm, runs in keys[key].items():
                gruns = {r: e for r, e in runs.items()
                         if not NONGATED.search(r) and (exp + "/" + r) not in partial}
                rec = {"exp": exp, "arm": arm,
                       "cited": cited(exp, ev),
                       "n_gated_runs": len(gruns),
                       "attribution": sorted({a for e in runs.values()
                                              for a in e["attribution"]}),
                       "n_values_max": max((e["n_values"] for e in runs.values()),
                                           default=0),
                       "moved_total": sum(e["moved"] for e in runs.values())}
                any_records.append(rec)
                if not gruns:
                    continue
                c = cross_run(gruns)
                rec2 = dict(rec)
                rec2["cross_run"] = c
                rec2["stable_live"] = stable_live(c)
                if rec2["stable_live"]:
                    hits.append(rec2)
        if hits:
            verdict = ("RECOVERABLE-BY-CITATION"
                       if all(not h["cited"] for h in hits)
                       else "RECOVERABLE-IN-CITED-EXPERIMENT")
        elif any_records:
            verdict = "RECORDS-BUT-FAILS-GATE"
        else:
            verdict = "NO-RECORDS-ANYWHERE"
        counts[verdict] += 1
        out[key] = {"verdict": verdict,
                    "cited_evidence": ev,
                    "reason_exp0164": W[key]["reason"],
                    "passing": hits,
                    "records_anywhere": any_records}
    out["_meta"]["counts"] = dict(counts)
    dst = os.path.join(HERE, "recitation_recovery.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    for k, v in sorted(counts.items()):
        print("%-32s %d" % (k, v))
    print("-> " + dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
