#!/usr/bin/env python3
"""Metadata-only audit for EXP-0058's pre-payload bounded stop."""
from __future__ import annotations
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent; root=HERE/"raw/m4-20260819-transition02"
assert (root/"analysis_failure.json").is_file()
failure=json.loads((root/"analysis_failure.json").read_text())
assert failure=={"error":"AssertionError(\"required mappings absent: ['va_100000b8000']\")"}
for trial in sorted((root/"trials").iterdir()):
 run=json.loads((trial/"run.json").read_text());assert run["exit"]==0 and "RESULT ok=1" in run["stdout"]
 # Only names/types are examined for payloads. Never open/hash a .bin.
 state=trial/"state"; assert state.is_dir() and not state.is_symlink()
 for p in state.iterdir(): assert p.is_file() and not p.is_symlink()
assert not (root/"trials/plain_compute-only/state/va_100000b8000.bin").exists()
print("PASS public reads valid; metadata-first stop retained; payloads unopened")
