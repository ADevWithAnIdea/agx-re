#!/usr/bin/env python3
"""EXP-0146 shared loader: read raw/<run>/sweep.jsonl into a case-keyed dict."""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402


def key(r):
    return (r["instr"], r["carrier"], r["field"], json.dumps(r["value"]))


def load(run_id):
    out = {}
    order = []
    p = EXP / "raw" / run_id / "sweep.jsonl"
    for line in p.open():
        r = json.loads(line)
        if r["field"].startswith("_") or r["instr"] == "_meta":
            out.setdefault("_special", []).append(r)
            continue
        k = key(r)
        out[k] = r
        order.append(k)
    out["_order"] = order
    return out


def field_widths():
    """mnemonic -> {field: width} straight from tools/agx-isa/db.json (read-only)."""
    w = {}
    for d in isadb.DB:
        w[d["mnemonic"]] = {f["name"]: f["width"] for f in d["fields"]}
    return w


def words(r):
    return tuple(r.get("observed", {}).get("words") or ())
