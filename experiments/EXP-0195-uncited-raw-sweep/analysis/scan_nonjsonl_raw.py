#!/usr/bin/env python3
"""EXP-0195 step 6: bound EXP-0194 limitation 5.5 -- "I only read .jsonl under raw/".

The 132-row population is defined over .jsonl per-case raw.  If per-case records for a
blocked row live in a .json file under raw/ instead, both EXP-0194 and this experiment are
blind to them, and 132 is a floor rather than the true count.  This walks every
experiments/**/raw/**/*.json, looks for objects that carry BOTH a `field` and a `bytes`
key (the per-case shape adjudicate2.py needs), and reports which blocked rows they touch
and whether the holding experiment is cited by the label.
"""
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
E0194 = os.path.join(ROOT, "experiments", "EXP-0194-desk-promotion-audit", "analysis")
blocked = {(r["mn"], r["field"]): r for r in json.load(open(os.path.join(E0194, "blocked_rows.json")))}


def cited(expdir, ev):
    return any(expdir == c or expdir.startswith(c + "-") or c.startswith(expdir + "-") for c in ev or [])


def walk(o, sink, depth=0):
    if depth > 8:
        return
    if isinstance(o, dict):
        f, b = o.get("field"), o.get("bytes")
        ins = o.get("instr") or o.get("instruction") or o.get("mnemonic")
        if f is not None and isinstance(b, str) and ins is not None:
            sink.append((str(ins), str(f)))
        for v in o.values():
            walk(v, sink, depth + 1)
    elif isinstance(o, list):
        for v in o[:20000]:
            walk(v, sink, depth + 1)


found = collections.defaultdict(collections.Counter)
nfiles = nhit = 0
for dp, dn, fn in os.walk(os.path.join(ROOT, "experiments")):
    if os.sep + "raw" + os.sep not in dp + os.sep:
        continue
    for f in sorted(fn):
        if not f.endswith(".json"):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT)
        exp = rel.split(os.sep)[1]
        nfiles += 1
        if os.path.getsize(p) > 200 * 1024 * 1024:
            continue
        try:
            o = json.load(open(p, errors="replace"))
        except Exception:
            continue
        sink = []
        walk(o, sink)
        for k in set(sink):
            if k in blocked:
                found[k][exp] += sum(1 for x in sink if x == k)
                nhit += 1

print("experiments/**/raw/**/*.json scanned : %d" % nfiles)
print("blocked rows with per-case (instr,field,bytes) records in a .json raw file: %d" % len(found))
new_pop = []
jsonl_pop = {(r["instr"], r["field"]) for r in json.load(open(os.path.join(HERE, "uncited_rows.json")))}
for k in sorted(found):
    ev = blocked[k]["ev"]
    unc = [e for e in found[k] if not cited(e, ev)]
    tag = "ALREADY in the 132" if k in jsonl_pop else ("NEW uncited row" if unc else "cited only")
    print("   %-22s %-16s cites=%-24s json-raw in %s   [%s]"
          % (k[0], k[1], ",".join(ev) or "-", dict(found[k]), tag))
    if unc and k not in jsonl_pop:
        new_pop.append(k)
print()
print("rows this adds to the uncited-raw population: %d" % len(new_pop))
json.dump([{"instr": k[0], "field": k[1], "exps": dict(found[k])} for k in sorted(found)],
          open(os.path.join(HERE, "nonjsonl_raw_rows.json"), "w"), indent=1)
