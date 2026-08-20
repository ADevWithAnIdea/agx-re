#!/usr/bin/env python3
"""Frozen EXP-0066 verifier skeleton; validates closed recorded public runs."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
assert {p.name for p in (HERE/"raw").iterdir()}=={"m4-20260820-run01","m4-20260820-run02"}
print("EXP-0066 raw tree present")
