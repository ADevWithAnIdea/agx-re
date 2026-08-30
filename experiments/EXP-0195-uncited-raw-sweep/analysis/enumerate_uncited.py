#!/usr/bin/env python3
"""EXP-0195 step 1: enumerate the blocked field rows that have per-case raw in an
experiment their own label does NOT cite -- the population EXP-0194 sec.2 identified as
structurally invisible to EXP-0164's citation-scoped audit.

Inputs (READ ONLY, nothing is written outside EXP-0195):
  experiments/EXP-0194-desk-promotion-audit/analysis/blocked_rows.json   (the 566 labels)
  <regenerated, byte-identical> raw_index.jsonl                          (9119 carrier groups)
Output: analysis/uncited_rows.json
"""
import json, os, collections, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
E0194 = os.path.join(ROOT, "experiments", "EXP-0194-desk-promotion-audit", "analysis")
INDEX = os.environ.get("E0195_INDEX", os.path.join(E0194, "raw_index.jsonl"))


def cited(expdir, ev):
    """Does evidence list `ev` name the experiment whose directory is `expdir`?

    Evidence strings are experiment IDs ('EXP-0138', 'EXP-M4-13', 'RT-ISA-FIX') and
    occasionally full directory names ('EXP-0168-g17p-dst-resweep'); directories are
    '<ID>-<slug>'.  This is exactly the resolution tools/agx-isa/validate_labels.py uses.
    """
    for c in ev or []:
        if expdir == c or expdir.startswith(c + "-") or c.startswith(expdir + "-"):
            return True
    return False


def main():
    blocked = json.load(open(os.path.join(E0194, "blocked_rows.json")))
    idx = collections.defaultdict(lambda: collections.defaultdict(list))
    for line in open(INDEX):
        g = json.loads(line)
        idx[(g["instr"], g["field"])][g["exp"]].append(g)

    rows, n_field, n_withraw = [], 0, 0
    for r in blocked:
        if r["field"] == "_instruction":
            continue                        # not a field: EXP-0194 bucket B
        n_field += 1
        key = (r["mn"], r["field"])
        exps = idx.get(key, {})
        if exps:
            n_withraw += 1
        ev = r["ev"] or []
        unc = sorted(e for e in exps if not cited(e, ev))
        cit = sorted(e for e in exps if cited(e, ev))
        if not unc:
            continue
        rows.append(dict(
            instr=key[0], field=key[1], label=r["label"], target_note=r.get("note", ""),
            evidence=ev, range=r.get("rng", ""),
            uncited_exps=unc, cited_exps_with_raw=cit,
            n_records_uncited=sum(g["n"] for e in unc for g in exps[e]),
            n_records_cited=sum(g["n"] for e in cit for g in exps[e]),
            n_groups_uncited=sum(len(exps[e]) for e in unc)))

    json.dump(rows, open(os.path.join(HERE, "uncited_rows.json"), "w"), indent=1)
    print("blocked field-labels                : %d" % len(blocked))
    print("  minus _instruction pseudo-fields  : %d" % sum(1 for r in blocked if r["field"] == "_instruction"))
    print("  real field rows                   : %d" % n_field)
    print("  of those, ANY per-case raw        : %d" % n_withraw)
    print("  of those, raw in a NON-CITED exp  : %d   <-- the EXP-0195 population" % len(rows))
    print()
    print("by current label:")
    for k, v in collections.Counter(r["label"] for r in rows).most_common():
        print("   %-26s %d" % (k, v))
    print()
    print("rows whose ONLY raw is uncited (label cites no experiment that has raw): %d"
          % sum(1 for r in rows if not r["cited_exps_with_raw"]))


main()
