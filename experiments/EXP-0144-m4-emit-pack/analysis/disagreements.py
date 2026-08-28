#!/usr/bin/env python3
"""Per-(instr,byte) count of where the REVALIDATION overturned the contaminated
original runs. Feeds the per-field `note` required by the coordinator's rule 2.
Writes analysis/reval_vs_original.json."""
import collections, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
from verdicts import load_run   # noqa: E402

rv, _, shards = load_run("m4_20260828_rv01")
orig = {}
for n in ("m4_20260828_run03", "m4_20260828_run05"):
    o, _, _ = load_run(n)
    for i, r in o.items():
        if r.get("validity") == "valid":
            orig.setdefault(i, []).append((n, r))

per = collections.defaultdict(lambda: {"compared": 0, "overturned": 0, "examples": []})
for i, r in rv.items():
    if r.get("validity") != "valid" or r.get("arm") not in ("F", "W"):
        continue
    key = "%s.byte%s" % (r["instr"], r.get("byte"))
    for n, o in orig.get(i, []):
        per[key]["compared"] += 1
        if o["outcome"] != r["outcome"]:
            per[key]["overturned"] += 1
            if len(per[key]["examples"]) < 4:
                per[key]["examples"].append(
                    {"case": r["name"], "original_run": n, "original": o["outcome"],
                     "revalidated": r["outcome"], "votes": r.get("votes")})
out = {k: v for k, v in sorted(per.items())}
(HERE / "reval_vs_original.json").write_text(json.dumps(out, indent=1, sort_keys=True))
tot_c = sum(v["compared"] for v in out.values())
tot_o = sum(v["overturned"] for v in out.values())
print("compared %d (instr,byte) measurements against the originals; %d overturned (%.2f%%)"
      % (tot_c, tot_o, 100.0 * tot_o / max(1, tot_c)))
print("bytes with any overturn:", sum(1 for v in out.values() if v["overturned"]))
