#!/usr/bin/env python3
"""EXP-0213 -- per-FIELD cross-run agreement, keyed by (carrier, field, value).

    python3 analysis/per_field.py <runA.jsonl> <runB.jsonl> [--fields mode,amode,rsv11]

The whole-capture number in pairwise.py mixes the fields under test with the instrument's
own `_detect` / `_baseline` records.  This splits them, because "Gate E MET" is a statement
about a FIELD, not about a file.  Volatile fields are stripped with pairwise.py's own list.
"""
import argparse
import json
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pairwise import load, payload, outcome, actual_bytes           # noqa: E402

HARD = {"fault", "hang", "measurement_failure", "invalid_run", "undecodable",
        "not_written", "unreproduced", "ledger_mismatch", "foreign"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runA")
    ap.add_argument("runB")
    ap.add_argument("--fields", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    A, B = load(a.runA), load(a.runB)

    def index(R):
        d = defaultdict(list)
        for r in R:
            if not isinstance(r.get("value"), int) or r["value"] < 0:
                continue
            fn = r.get("field") or ""
            if fn.startswith("_"):
                continue
            d[(r.get("carrier"), fn, r["value"])].append(r)
        return d

    ia, ib = index(A), index(B)
    shared = sorted(set(ia) & set(ib), key=str)
    want = set(x for x in a.fields.split(",") if x)
    per = defaultdict(lambda: {"shared": 0, "agree": 0, "soft": 0, "hard_flip": 0,
                               "both_hard": 0, "ledger_diff": 0, "examples": []})
    perarm = defaultdict(lambda: [0, 0])
    for k in shared:
        carrier, fn, v = k
        if want and fn not in want:
            continue
        ra, rb = ia[k], ib[k]
        s = per[fn]
        s["shared"] += 1
        if sorted(str(actual_bytes(r)) for r in ra) != sorted(str(actual_bytes(r)) for r in rb):
            s["ledger_diff"] += 1
        oa = sorted(outcome(r) for r in ra)
        ob = sorted(outcome(r) for r in rb)
        ha, hb = all(o in HARD for o in oa), all(o in HARD for o in ob)
        if ha and hb:
            s["both_hard"] += 1
            continue
        if ha != hb:
            s["hard_flip"] += 1
            perarm[(fn, carrier)][1] += 1
            if len(s["examples"]) < 12:
                s["examples"].append({"carrier": carrier, "value": v, "A": oa, "B": ob,
                                      "class": "hard_flip"})
            continue
        if sorted(payload(r) for r in ra) == sorted(payload(r) for r in rb):
            s["agree"] += 1
            perarm[(fn, carrier)][0] += 1
        else:
            s["soft"] += 1
            perarm[(fn, carrier)][1] += 1
            if len(s["examples"]) < 12:
                pa = json.loads(payload(ra[0]))
                pb = json.loads(payload(rb[0]))
                diff = sorted(set(json.dumps({k2: pa.get(k2)}, sort_keys=True, default=str)
                                  for k2 in set(pa) | set(pb)
                                  if json.dumps(pa.get(k2), sort_keys=True, default=str)
                                  != json.dumps(pb.get(k2), sort_keys=True, default=str)))
                s["examples"].append({"carrier": carrier, "value": v, "A": oa, "B": ob,
                                      "class": "soft", "differing_keys": diff[:3]})
    out = {"runA": a.runA, "runB": a.runB, "fields": {}}
    for fn, s in sorted(per.items()):
        comparable = s["agree"] + s["soft"] + s["hard_flip"]
        out["fields"][fn] = dict(s, comparable=comparable,
                                 pct=(round(100.0 * s["agree"] / comparable, 4)
                                      if comparable else None))
    out["per_arm"] = {"%s@%s" % (f, c): {"agree": v[0], "disagree": v[1]}
                      for (f, c), v in sorted(perarm.items()) if v[1]}
    js = json.dumps(out, indent=1, sort_keys=True)
    print(js)
    if a.json:
        open(a.json, "w").write(js + "\n")


if __name__ == "__main__":
    main()
