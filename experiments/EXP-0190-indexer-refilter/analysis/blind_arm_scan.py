#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0190 step 7 -- the hunt for a tenth check that cannot come out the other way.

`audit.py`'s inert buckets (INERT-MULTI, INERT-SINGLE) are computed from `moved`, which
is derived from the hash of each record's `observed`.  There is NO detection-power
conjunct anywhere in the chain.  So an arm whose observable never varies -- for any
field, at any value -- returns `moved = 0` by construction, and the audit reads that as
"the field is inert" rather than "the instrument could not answer".

This script measures how big that is:

  1. for every (experiment, arm) group of NON-underscore field records, count the
     distinct `observed` payloads;
  2. list the groups that recorded EXACTLY ONE distinct observation (or none at all)
     over >= 8 records -- those arms cannot return `moved >= 1`;
  3. cross-reference: which INERT-* fields have ALL of their tested arms in that set.

An arm with one distinct observation is not *proof* of no detection power -- the
hardware may genuinely be inert for everything that arm tried.  That is exactly the
ambiguity: nothing inside the arm's own field records distinguishes the two.  The
corpus DOES contain the positive controls that would (`_detect`, `__ladder_L_*`,
`_live_control`), and the audit discards every one of them through the same `_` filter
this experiment repaired.

Writes analysis/blind_arms.json.
Usage: python3 analysis/blind_arm_scan.py
"""
import collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
MIN_RECORDS = 8


def resolver():
    dirs = sorted(d for d in os.listdir(EXPDIR) if os.path.isdir(os.path.join(EXPDIR, d)))

    def rd(eid):
        if eid in dirs:
            return eid
        c = [d for d in dirs if d.startswith(eid + "-")]
        return c[0] if len(c) == 1 else eid
    return rd


def main():
    stat = collections.defaultdict(lambda: {"n": 0, "empty": 0, "distinct": set()})
    for exp in sorted(os.listdir(EXPDIR)):
        raw = os.path.join(EXPDIR, exp, "raw")
        if not os.path.isdir(raw):
            continue
        for dp, _, fns in os.walk(raw):
            for fn in fns:
                if not fn.endswith(".jsonl"):
                    continue
                for line in open(os.path.join(dp, fn), errors="replace"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(r, dict):
                        continue
                    f, i = r.get("field"), r.get("instr")
                    if not (isinstance(f, str) and isinstance(i, str)) or f.startswith("_"):
                        continue
                    ac = [str(r[k]) for k in ("carrier", "arm") if r.get(k) not in (None, "")]
                    s = stat[(exp, "|".join(ac) if ac else "-")]
                    s["n"] += 1
                    ob = r.get("observed")
                    if ob in (None, {}, [], ""):
                        s["empty"] += 1
                    else:
                        s["distinct"].add(json.dumps(ob, sort_keys=True))

    empty = {k: v["n"] for k, v in stat.items() if v["n"] >= 2 and v["empty"] == v["n"]}
    single = {k: v["n"] for k, v in stat.items()
              if v["n"] >= MIN_RECORDS and v["empty"] == 0 and len(v["distinct"]) == 1}
    blind = set(empty) | set(single)

    rd = resolver()
    audit = json.load(open(os.path.join(HERE, "audit.json")))["fields"]
    hits = {}
    for k, r in sorted(audit.items()):
        if r["bucket"] not in ("INERT-MULTI", "INERT-SINGLE") or not r["arms_tested"]:
            continue
        keys = []
        for a in r["arms_tested"]:
            eid, _, arm = a.partition(":")
            keys.append((rd(eid), arm))
        if all(x in blind for x in keys):
            hits[k] = {"bucket": r["bucket"], "cohort": r["cohort"],
                       "label_now": r["label"], "evidence": r["evidence"],
                       "n_arms_tested": len(keys),
                       "max_values_dispatched": r["max_values_dispatched"],
                       "arms": ["%s|%s" % x for x in keys],
                       "records_per_arm": {"%s|%s" % x: stat[x]["n"] for x in keys},
                       "arm_distinct_observations": {"%s|%s" % x: len(stat[x]["distinct"])
                                                     for x in keys}}
    out = {"_meta": {
        "experiment": "EXP-0190-indexer-refilter",
        "finding": "DEF-0190-1: the inert buckets have no detection-power conjunct",
        "min_records_for_single_observation_group": MIN_RECORDS,
        "n_arms_with_no_observation_at_all": len(empty),
        "n_arms_with_exactly_one_distinct_observation": len(single),
        "records_in_those_arms": sum(empty.values()) + sum(single.values()),
        "n_inert_fields_whose_every_arm_is_blind": len(hits),
        "n_of_those_currently_emitter_grade": sum(
            1 for v in hits.values() if v["cohort"] == "emitter-grade")},
        "arms_with_no_observation_at_all": {"%s|%s" % k: v for k, v in sorted(empty.items())},
        "arms_with_exactly_one_distinct_observation": {
            "%s|%s" % k: v for k, v in sorted(single.items())},
        "inert_fields_whose_every_tested_arm_is_blind": hits}
    json.dump(out, open(os.path.join(HERE, "blind_arms.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(out["_meta"], indent=1, sort_keys=True))
    for k, v in sorted(hits.items()):
        if v["cohort"] == "emitter-grade":
            print("  EMITTER-GRADE  %-28s %-12s arms=%s" % (k, v["bucket"], v["arms"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
