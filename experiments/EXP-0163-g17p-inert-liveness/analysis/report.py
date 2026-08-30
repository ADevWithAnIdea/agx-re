#!/usr/bin/env python3
"""report.py -- EXP-0163: render the verdict tables for RESULTS.md from the
machine-readable analysis outputs, so the prose cannot drift from the data.

    python3 analysis/report.py > analysis/verdict_tables.md

CLEAN-ROOM: formats our own analysis of our own captured observations.
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import carriers as CA  # noqa: E402

V = json.load(open(os.path.join(HERE, "field_verdicts.json")))
try:
    R = json.load(open(os.path.join(HERE, "bit_rules.json")))
except FileNotFoundError:
    R = {}

runs = V["runs"]
F = V["fields"]

def rule_for(field_key):
    mn, fn = field_key.split(".", 1)
    rows = []
    for k, per in sorted(R.items()):
        arm, f = k.split("|")
        if f != fn or not arm.startswith(mn + "@"):
            continue
        rs = list(per.values())
        agree = len({(tuple(r["moved"]), tuple(r["live_bits"])) for r in rs}) == 1
        r0 = rs[0]
        rows.append((arm, r0, agree, [r["n_moved"] for r in rs]))
    return rows

print("### Bucket summary\n")
print("| field | bucket | live on | inert on (carriers w/ proven detection power) |")
print("|---|---|---|---|")
buckets = collections.Counter()
for k, v in sorted(F.items()):
    buckets[v["bucket"]] += 1
    live = ", ".join(a.split("@")[1] for a in v["live_arms"]) or "—"
    inert = ", ".join(v["inert_carriers"]) or "—"
    print(f"| `{k}` | **{v['bucket']}** | {live[:90]} | {inert[:90]} |")
print()
print("Totals: " + ", ".join(f"**{b}** {n}" for b, n in sorted(buckets.items())))
print(f"\nRuns compared: {', '.join(runs)}\n")

print("\n### LIVE fields — exact rules\n")
print("| field | arm (carrier) | moved / swept | equivalence classes | live bits | exact rule | cross-run |")
print("|---|---|---|---|---|---|---|")
for k, v in sorted(F.items()):
    if v["bucket"] != "LIVE":
        continue
    for arm, r0, agree, counts in rule_for(k):
        if r0["n_moved"] == 0:
            continue
        print("| `%s` | `%s` | %d/%d | %d | %s | %s | %s |" % (
            k, arm.split("@")[1], r0["n_moved"], r0["n"], r0["n_equiv_classes"],
            ",".join(str(b) for b in r0["live_bits"]) or "—",
            r0["rule"][:70], "agree" if agree else "**DISAGREE** " + str(counts)))

print("\n\n### INERT-ROBUST fields — the envelope actually tested\n")
print("| field | carriers (all with proven detection power) | arms | values per arm | total inert observations |")
print("|---|---|---|---|---|")
for k, v in sorted(F.items()):
    if v["bucket"] != "INERT-ROBUST":
        continue
    arms = v["inert_arms"]
    n = 0
    per = set()
    for a in arms:
        for rn in runs:
            n += F[k]["arms"][a]["per_run"][rn]["n"]
            per.add(F[k]["arms"][a]["per_run"][rn]["n"])
    print("| `%s` | %s | %d | %s | %d |" % (
        k, ", ".join(v["inert_carriers"]), len(arms),
        "/".join(str(x) for x in sorted(per)), n))

print("\n\n### STILL-UNDERPOWERED fields\n")
print("| field | why | carriers reached |")
print("|---|---|---|")
for k, v in sorted(F.items()):
    if v["bucket"] != "STILL-UNDERPOWERED":
        continue
    why = []
    if len(v["inert_carriers"]) < 3:
        why.append(f"only {len(v['inert_carriers'])} distinct carrier(s) with "
                   f"proven detection power (bar is 3)")
    if v["underpowered_arms"]:
        why.append(f"{len(v['underpowered_arms'])} arm(s) without detection "
                   f"power or with cross-run disagreement")
    print("| `%s` | %s | %s |" % (k, "; ".join(why) or "—",
                                  ", ".join(v["inert_carriers"]) or "—"))

print("\n\n### Detection power, per arm\n")
dp = V["detection_power"]
noc = [a for a, per in dp.items()
       if not all(x.get("detect_ok_strict") for x in per.values())]
print(f"{len(dp) - len(noc)} of {len(dp)} arms pass the strict gate "
      f"(status OK + observation changed + still decodes as the arm's mnemonic) "
      f"in every run.")
if noc:
    print("\nArms WITHOUT strict detection power (excluded from every verdict):\n")
    for a in sorted(noc):
        print(f"- `{a}` — " + json.dumps(dp[a], sort_keys=True)[:300])
