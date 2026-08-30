#!/usr/bin/env python3
"""EXP-0194 step 6: POSITIVE CONTROL for the adjudicator.

A gate that says NO to everything is as broken as one that says YES to everything.
Run the identical G1..G8 chain over the 543 fields validation.json ALREADY calls
emitter-grade.  If almost none of them pass, the gate is not measuring desk
promotability -- it is just refusing.  Reported, not hidden.
"""
import json, os, subprocess, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
db = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "db.json")))
val = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "validation.json")))
EMIT = {"hardware-run", "isolated-byte-diff"}
DW = {i["mnemonic"] for i in db["instructions"] if i.get("emitter_role") == "data-word"}
rows = []
for i in db["instructions"]:
    m = i["mnemonic"]
    if m in DW:
        continue
    e = val["instructions"][m]
    for f in i.get("fields", []):
        if e[f["name"]]["label"] in EMIT:
            rows.append(dict(mn=m, field=f["name"], label=e[f["name"]]["label"],
                             ev=e[f["name"]].get("evidence") or []))
json.dump(rows, open(os.path.join(HERE, "control_rows.json"), "w"))
print("emitter-grade fields to control against: %d" % len(rows))
