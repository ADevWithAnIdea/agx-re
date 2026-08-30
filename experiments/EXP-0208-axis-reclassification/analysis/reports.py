#!/usr/bin/env python3
"""EXP-0208 step 6 -- the reports RESULTS.md is built from."""
import json, os, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(HERE, "axes.json")))
EV = json.load(open(os.path.join(HERE, "..", "work", "row_evidence.json")))

# 1 hazard inventory
haz = []
for k, v in A.items():
    h = v["axes"]["hazard"]
    if h.startswith("none") or h.startswith("no dispatched"):
        continue
    haz.append((k, v["label"], h, v["axes"]["counts"]))
json.dump([dict(row=k, label=l, hazard=h, counts=c) for k, l, h, c in haz],
          open(os.path.join(HERE, "hazard_inventory.json"), "w"), indent=1)

pred = [(k, h) for k, l, h, c in haz if re.search(r"contiguous wall|\(v & 0x|exactly \{", h)]
print("### rows with a hazard/no-effect fact:", len(haz))
print("### of those with an EXACT predicate:", len(pred))
for k, h in pred[:80]:
    print("   ", k, "::", h[:190])

# 2 contradictions between the note and the raw
contra = []
for k, v in A.items():
    note = (EV[k]["note"] or "").lower()
    ax = v["axes"]; live = ax["liveness"]
    c = None
    if re.search(r"\b0 (values dispatched|observations moved)\b|unverifiable", note) and \
       ax["counts"]["dispatched_distinct_values"] > 0:
        c = ("note says 0 values dispatched / UNVERIFIABLE; raw has %d distinct dispatched values "
             "in %s" % (ax["counts"]["dispatched_distinct_values"],
                        ", ".join(ax["evidence_experiments"]) or "a non-jsonl record"))
    elif re.search(r"fully inert|0 of 256 sub-values moved|never moved anything|0 observations moved",
                   note) and live.startswith("live"):
        c = "note says INERT / nothing moved; raw shows %s" % live[:150]
    elif "1 distinct valid payload" in note and \
         ax["counts"]["distinct_valid_payloads_max_single_carrier"] > 1:
        c = ("note says 1 distinct valid payload; raw shows %d distinct VALID payloads in a single "
             "carrier under the EXP-0191 validity rule"
             % ax["counts"]["distinct_valid_payloads_max_single_carrier"])
    elif re.search(r"\bno raw\b|no per-value records", note) and \
         ax["counts"]["records"] > 0:
        c = "note says no raw; %d per-case records found" % ax["counts"]["records"]
    if c:
        contra.append(dict(row=k, label=v["label"], note=EV[k]["note"][:400], contradiction=c))
json.dump(contra, open(os.path.join(HERE, "contradictions.json"), "w"), indent=1)
print("\n### rows where raw CONTRADICTS the current note:", len(contra))
for c in contra[:40]:
    print("   ", c["row"], "::", c["contradiction"][:170])

# 3 no-raw audit
nr = [k for k, v in A.items() if "no_raw_statement" in v["axes"]]
byev = collections.Counter(tuple(EV[k]["evidence"]) or ("<none>",) for k in nr)
print("\n### rows with NO dispatched raw:", len(nr))
for e, n in byev.most_common(20):
    print("   %4d %s" % (n, ",".join(e)))

# 4 axis cross-tab against the legacy label
tab = collections.Counter()
for k, v in A.items():
    tab[(v["label"], v["axes"]["liveness"].split(":")[0].split("(")[0].split("|")[0].strip())] += 1
print("\n### label x liveness")
for (l, li), n in sorted(tab.items()):
    print("   %4d  %-28s %s" % (n, l, li))
