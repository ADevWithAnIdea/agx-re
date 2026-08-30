#!/usr/bin/env python3
"""EXP-0195 step 7: emit the per-row classification table used in RESULTS.md."""
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
c = json.load(open(os.path.join(HERE, "classification.json")))
SHORT = {"DESK-PROMOTABLE": "RECOVERED", "AMBIGUOUS": "AMBIG", "HARDWARE-BLOCKED": "BLOCKED"}
order = {"DESK-PROMOTABLE": 0, "AMBIGUOUS": 1, "HARDWARE-BLOCKED": 2}
c.sort(key=lambda r: (order[r["verdict_uncited_only"]], r["stop_uncited"] or "G1", r["instr"], r["field"]))
L = ["| # | instruction | field | current label | uncited raw in | verdict | stop | clean | enc | payloads | runs | refusal on record |",
     "|--:|---|---|---|---|---|---|--:|--:|--:|--:|---|"]
for i, r in enumerate(c, 1):
    ex = ",".join(e.split("-")[0] + "-" + e.split("-")[1] for e in r["uncited_exps"])
    L.append("| %d | `%s` | `%s` | %s | %s | **%s** | %s | %s | %s | %s | %s | %s |"
             % (i, r["instr"], r["field"], r["label"], ex, SHORT[r["verdict_uncited_only"]],
                r["stop_uncited"] or "G1", r["n_clean_uncited"] if r["n_clean_uncited"] is not None else "-",
                r["n_enc_uncited"] if r["n_enc_uncited"] is not None else "-",
                r["n_payloads_uncited"] if r["n_payloads_uncited"] is not None else "-",
                r["n_runs_uncited"] if r["n_runs_uncited"] is not None else "-",
                "yes" if r["documented_refusal"] else "-"))
open(os.path.join(HERE, "row_table.md"), "w").write("\n".join(L) + "\n")
print("wrote row_table.md  (%d rows)" % len(c))
print(collections.Counter(r["verdict_uncited_only"] for r in c))
