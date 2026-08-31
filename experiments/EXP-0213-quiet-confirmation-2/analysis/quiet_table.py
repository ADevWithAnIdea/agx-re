#!/usr/bin/env python3
"""EXP-0213 -- one row per capture: measured quiet signals + device reset counters."""
import glob
import json
import os
import sys

rows = []
for d in sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "raw", "*"))):
    p = os.path.join(d, "quietcheck.json")
    if not os.path.exists(p):
        continue
    try:
        q = json.load(open(p))
    except Exception:                                                # noqa: BLE001
        continue
    rows.append((os.path.basename(d), q))
print("%-42s %-5s %6s %7s %5s %5s %6s %8s %8s %6s %5s"
      % ("capture", "QUIET", "smpls", "span_s", "fgnL", "fgnS", "compsv",
         "rec_pre", "rec_post", "delta", "ioerr"))
tot = 0
for name, q in rows:
    tot += (q.get("recovery_delta") or 0)
    print("%-42s %-5s %6s %7s %5s %5s %6s %8s %8s %6s %5s"
          % (name, q.get("QUIET"), q.get("samples"), q.get("span_s"),
             q.get("max_foreign_runner_live"), q.get("max_foreign_runner_strict"),
             q.get("compiler_svc_max"), q.get("recovery_pre"), q.get("recovery_post"),
             q.get("recovery_delta"), q.get("ioreg_errors")))
print("captures=%d  all QUIET=%s  total recoveryCount delta over the session=%d"
      % (len(rows), all(q.get("QUIET") for _, q in rows), tot))
notq = [n for n, q in rows if not q.get("QUIET")]
if notq:
    print("NOT QUIET:", notq)
