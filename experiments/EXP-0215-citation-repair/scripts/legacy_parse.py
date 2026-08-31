#!/usr/bin/env python3
"""Re-run tools/agx-isa/legacy_index.py against the FROZEN db.json, writing into
EXP-0215's own work dir. EXP-0211's committed index is never touched.

A re-parse is required, not optional: EXP-0212 moved five field spans and added
thirteen fields after EXP-0211's index was written, and every legacy attribution
is a byte index resolved through db.json.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import evidence_index as EI
_orig = EI.load_db
EI.load_db = lambda path=None: _orig(os.path.join(EXP, "work", "db_frozen.json"))
import legacy_index as LI
LI.OUTDIR = os.path.join(EXP, "work", "legacy_index")
os.makedirs(LI.OUTDIR, exist_ok=True)
em = LI.run_parse(None)
with open(os.path.join(LI.OUTDIR, "legacy_records.jsonl"), "w") as fh:
    for r in em.records:
        fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
with open(os.path.join(LI.OUTDIR, "compile_only_records.jsonl"), "w") as fh:
    for r in em.compile_only:
        fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
json.dump({"records": len(em.records), "compile_only": len(em.compile_only),
           "candidates": em.stats["candidates"], "unparsed": em.stats["unparsed"],
           "per_parser": {k: dict(v) for k, v in em.per_parser.items()}},
          open(os.path.join(LI.OUTDIR, "parse_stats.json"), "w"), indent=1, default=str)
print("records", len(em.records), "compile_only", len(em.compile_only))
