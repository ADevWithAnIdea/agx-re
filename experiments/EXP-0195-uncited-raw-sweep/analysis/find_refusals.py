#!/usr/bin/env python3
"""EXP-0195 step 2b: for each of the 132 rows, is there ALREADY a documented refusal?

EXP-0194 sec.3 found that 31 of its 46 AMBIGUOUS rows carry an explicit refusal in their
current validation.json note (EXP-0164 "withheld", EXP-0189 "UNSTABLE", EXP-0169
"disagreed with the HOST-COMPUTED oracle" / "no (arm,carrier) passed its liveness ladder",
EXP-0179 "DECLINED", EXP-0141 "NOT PROMOTED").  A row carrying one must not be re-promoted
by an analysis with strictly less information than the audit that demoted it.

Two sources, both read-only:
  1. the field's own note in tools/agx-isa/validation.json
  2. any line of any committed experiments/*/RESULTS.md or PROGRESS.md that names the row
     and also carries a refusal token
"""
import json, os, re, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

TOKENS = [
    "withheld", "withhold", "not promoted", "no promotion", "declined", "decline",
    "unstable", "does not take it", "refus", "demoted", "demote", "not emittable",
    "disagreed with the host", "liveness ladder", "veto", "retract", "reverted",
    "0 observations moved", "did not move", "never moved", "inconclusive", "quarantin",
]
TOKRE = re.compile("|".join(re.escape(t) for t in TOKENS), re.I)

rows = json.load(open(os.path.join(HERE, "uncited_rows.json")))
val = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "validation.json")))

hits = collections.defaultdict(list)

# source 1 -- the label's own note
for r in rows:
    k = "%s.%s" % (r["instr"], r["field"])
    try:
        note = val["instructions"][r["instr"]][r["field"]].get("note") or ""
    except Exception:
        note = ""
    if note and TOKRE.search(note):
        hits[k].append(dict(src="validation.json note", text=note[:400]))

# source 2 -- committed narrative
keys = {("%s.%s" % (r["instr"], r["field"])): (r["instr"], r["field"]) for r in rows}
for p in sorted(glob.glob(os.path.join(ROOT, "experiments", "*", "RESULTS.md"))
                + glob.glob(os.path.join(ROOT, "experiments", "*", "PROGRESS.md"))):
    rel = os.path.relpath(p, ROOT)
    try:
        lines = open(p, errors="replace").read().split("\n")
    except Exception:
        continue
    for ln, line in enumerate(lines, 1):
        if not TOKRE.search(line):
            continue
        for k, (mn, fld) in keys.items():
            if k in line or (mn in line and re.search(r"[`\s.|]" + re.escape(fld) + r"[`\s,.)|]", line)):
                hits[k].append(dict(src="%s:%d" % (rel, ln), text=line.strip()[:400]))

json.dump({k: v for k, v in hits.items()}, open(os.path.join(HERE, "documented_refusals.json"), "w"), indent=1)
print("rows (of %d) carrying a documented refusal: %d" % (len(rows), len(hits)))
print("  ... from the validation.json note itself : %d"
      % sum(1 for v in hits.values() if any(h["src"] == "validation.json note" for h in v)))
print("  ... from a committed RESULTS/PROGRESS.md : %d"
      % sum(1 for v in hits.values() if any(h["src"] != "validation.json note" for h in v)))
