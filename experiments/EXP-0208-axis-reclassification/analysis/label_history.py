#!/usr/bin/env python3
"""EXP-0208 step 4 -- reconstruct each field row's LABEL HISTORY from git.

RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 9 requires two facts per row: whether the
experiment passed its OWN pre-registered gate at the time, and whether the evidence is
sufficient for today's gates. The first is directly recoverable: if a row ever HELD an
emitter-grade label in a committed revision of validation.json, that experiment's frozen
gate was met at the time by the orchestrator who merged it.
"""
import json, os, subprocess, sys, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
P = "tools/agx-isa/validation.json"

log = subprocess.run(["git", "-C", ROOT, "log", "--reverse", "--format=%H\t%ad\t%s",
                      "--date=short", "--", P], capture_output=True, text=True).stdout
commits = [l.split("\t", 2) for l in log.strip().splitlines()]
hist = collections.defaultdict(list)
for sha, date, subj in commits:
    blob = subprocess.run(["git", "-C", ROOT, "show", f"{sha}:{P}"], capture_output=True, text=True).stdout
    try:
        v = json.loads(blob)
    except Exception:
        sys.stderr.write("unparsable at %s\n" % sha); continue
    for m, fields in v.get("instructions", {}).items():
        for f, rec in fields.items():
            if f.startswith("_") or not isinstance(rec, dict): continue
            lab = rec.get("label")
            if lab is None: continue
            k = f"{m}.{f}"
            if not hist[k] or hist[k][-1]["label"] != lab:
                hist[k].append(dict(sha=sha[:8], date=date, subj=subj, label=lab,
                                    evidence=rec.get("evidence") or []))
json.dump(hist, open(os.path.join(HERE, "label_history.json"), "w"), indent=0)
print("rows with history:", len(hist), "commits:", len(commits))
