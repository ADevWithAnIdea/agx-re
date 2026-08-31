#!/usr/bin/env python3
"""Rebuild the evidence-index cache against the CURRENT db.json, into EXP-0215's
own work dir. EXP-0209's committed cache is never written.

Why a rebuild is mandatory: EXP-0212 moved 5 field spans and added 13 fields.
evidence_index's K2 byte-span keying and its Gate A decode both read db.json, and
its per-experiment cache key is a fingerprint of the EXPERIMENT's files only -- it
does not notice that db.json changed. Scoring today's spans against yesterday's
cache is exactly the "record swept the OLD span" hazard.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import evidence_index as EI

EI.CACHE = os.path.join(ROOT, "experiments", "EXP-0215-citation-repair", "work", "index")
os.makedirs(EI.CACHE, exist_ok=True)
# pin db.json to the frozen copy so a concurrent edit cannot move the spans mid-run
EI.load_db = (lambda _orig: (lambda path=None: _orig(
    os.path.join(ROOT, "experiments", "EXP-0215-citation-repair", "work", "db_frozen.json"))))(EI.load_db)
if __name__ == "__main__":
    EI.build(sys.argv[1:] or None, force=True)
