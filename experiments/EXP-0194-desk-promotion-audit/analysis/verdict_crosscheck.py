#!/usr/bin/env python3
"""EXP-0194 step 4: does any experiment's OWN committed analysis/field_verdicts*.json
already carry an emitter-grade verdict for a field that validation.json now shows
blocked?  Such a row needs no device: the adjudication is already committed.
"""
import json, os, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
EMIT = {"hardware-run", "isolated-byte-diff"}
val = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "validation.json")))
blocked = {(r["mn"], r["field"]): r for r in json.load(open(os.path.join(HERE, "blocked_rows.json")))}

hits = collections.defaultdict(list)
for p in sorted(glob.glob(os.path.join(ROOT, "experiments", "*", "analysis", "field_verdicts*.json"))):
    try:
        d = json.load(open(p))
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    exp = os.path.relpath(p, ROOT).split(os.sep)[1]
    for k, v in d.items():
        if not isinstance(v, dict) or "label" not in v:
            continue
        if "." not in k:
            continue
        mn, _, fld = k.partition(".")
        if (mn, fld) not in blocked:
            continue
        lab = v.get("label")
        alt = v.get("label_isolated_pair")
        if lab in EMIT:
            hits[(mn, fld)].append(dict(file=os.path.relpath(p, ROOT), exp=exp, label=lab,
                                        target=v.get("target"), range=v.get("range"),
                                        note=v.get("note", ""), semantics=v.get("semantics", ""),
                                        deterministic=v.get("deterministic"),
                                        live=v.get("live"), cross_run=v.get("cross_run"),
                                        primary=True))
        elif alt in EMIT:
            hits[(mn, fld)].append(dict(file=os.path.relpath(p, ROOT), exp=exp,
                                        label=lab, alt_label=alt, target=v.get("target"),
                                        range=v.get("range"), note=v.get("note", ""),
                                        primary=False))

prim = {k: v for k, v in hits.items() if any(h["primary"] for h in v)}
alt = {k: v for k, v in hits.items() if k not in prim}
print("blocked rows with a committed PRIMARY emitter-grade verdict elsewhere: %d" % len(prim))
print("blocked rows with only an `label_isolated_pair` alternative:           %d" % len(alt))
print()
for k in sorted(prim):
    cur = val["instructions"][k[0]][k[1]]
    print("%-24s %-16s  now=%-26s cites=%s" % (k[0], k[1], cur["label"] + "/" + str(cur.get("target")),
                                               ",".join(cur.get("evidence") or []) or "-"))
    for h in prim[k]:
        if h["primary"]:
            print("      committed %s/%s in %s  range=%r" % (h["label"], h["target"], h["file"], h["range"]))
            if h.get("note"):
                print("        note: %s" % h["note"][:200])
    print("      current note: %s" % (cur.get("note", "") or "-")[:300])
    print()
json.dump({("%s.%s" % k): v for k, v in hits.items()},
          open(os.path.join(HERE, "verdict_crosscheck.json"), "w"), indent=1)
