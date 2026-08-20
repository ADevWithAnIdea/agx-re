#!/usr/bin/env python3
"""Verify only EXP-0059's honest stopped-state record; do not promote it."""
from __future__ import annotations
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=HERE/"raw/falu2i-property-v1.json"
assert p.is_file() and not p.is_symlink()
r=json.loads(p.read_text())
assert set(r)=={"schema","scope","descriptor","semantic_fields","excluded_nonsemantic_fields","domain","expected_vectors","unique_encodings","all_round_trip","input_sha256","encoding_sha256"}
assert r["descriptor"]=="falu2i" and r["expected_vectors"]==r["unique_encodings"]==1440 and r["all_round_trip"] is True
assert "capture_revision" not in r and "analyzer_sha256" not in r
print("PASS STOP: raw output intentionally lacks analyzer/revision capture binding; no promotion allowed")
