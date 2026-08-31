#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""annotate.py -- write each row's measured dashboard effect back into the proposal.

Metadata only: it never changes which experiments are proposed, so the four scored
runs stay valid. `dashboard_effect` records what the seven dashboards did with the
addition, INCLUDING the five rows where an addition pulls geometry DOWN because the
added experiment brings Gate A disagreements. Those five are kept: excluding
evidence because it is inconvenient is how a repair becomes a wish.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import dashboards as DB

W = os.path.join(EXP, "work")
det = {t: json.load(open(os.path.join(W, "reports_%s" % t, "dashboard_detail.json")))
       for t in ("base", "prop", "base_leg", "prop_leg")}
p = os.path.join(EXP, "analysis", "citation_additions.json")
P = json.load(open(p))
nup = ndown = 0
for key, spec in P.items():
    eff = {}
    for d in det["base"]:
        a = det["base"][d].get(key)
        if a is None:
            continue
        b = det["prop"][d].get(key)
        c = det["prop_leg"][d].get(key)
        if a["status"] != b["status"]:
            eff[d] = {"from": a["status"], "to": b["status"],
                      "direction": "up" if DB.rank(d, b["status"]) > DB.rank(d, a["status"])
                                   else "DOWN",
                      "why_after": b["why"]}
            if eff[d]["direction"] == "up":
                nup += 1
            else:
                ndown += 1
        if c and b and c["status"] != b["status"]:
            eff.setdefault(d, {})["with_legacy_index"] = c["status"]
    spec["dashboard_effect"] = eff
    spec["moves_a_rung"] = bool(eff)
json.dump(P, open(p, "w"), indent=1, sort_keys=True)
print("annotated %d rows; %d rung increases, %d rung DECREASES" % (len(P), nup, ndown))
