#!/usr/bin/env python3
"""Manifest EXP-0056's metadata-only stopped run without opening payloads."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()
files=[]
for p in sorted((HERE/"raw").rglob("*")):
 if p.is_file(): files.append({"path":str(p.relative_to(HERE)),"bytes":p.stat().st_size,"sha256":sha(p)})
if any(x["path"].endswith((".bin",".meta")) for x in files):raise SystemExit("EXP-0056 stopped run must contain no payload files")
(HERE/"manifest.json").write_text(json.dumps({"schema":1,"status":"STOPPED_BEFORE_PAYLOAD_CAPTURE","pre_registration_sha256":"fd0df7965ded35fe89bbe2390b785d0950c8aa77f2a8075dfc8e013fca728080","files":files},indent=2,sort_keys=True)+"\n")
