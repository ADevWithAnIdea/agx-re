#!/usr/bin/env python3
"""Verify EXP-0056's bounded metadata-only failure record."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((HERE/"manifest.json").read_text());assert m["status"]=="STOPPED_BEFORE_PAYLOAD_CAPTURE"
assert not list((HERE/"raw").rglob("*.bin")) and not list((HERE/"raw").rglob("*.meta"))
for x in m["files"]:
 p=HERE/x["path"];assert p.is_file() and p.stat().st_size==x["bytes"] and sha(p)==x["sha256"]
r=json.loads((HERE/"raw/m4-20260819-transition01/trials/plain_compute-only/run.json").read_text())
assert r["exit"]==6 and "RESULT ok=0" in r["stdout"]
t=(HERE/"raw/m4-20260819-transition01/trials/plain_compute-only/trace.log").read_text()
assert all(f"va=0x{x}" not in t for x in ("100000b8000","10000158000","18000","88000"))
print("PASS metadata-only stopped run; no payload retained or opened")
