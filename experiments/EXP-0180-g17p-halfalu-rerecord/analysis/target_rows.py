#!/usr/bin/env python3
"""EXP-0180 -- resolve the 25 target ROW-CLAIMS over their 16 distinct fields,
and re-check every span against THIS experiment's PINNED db.json.

Two claim sets from the dispatch:
  (a) HELD-BY-EXP-0169 -- 16 rows whose only passing liveness ladder was the
      WITHDRAWN C2_load carrier (analysis/field_verdicts_held_c2load.json).
  (b) CITES-EXP-M4-14  -- 9 rows whose committed evidence is EXP-M4-14, which
      EXP-0164 established has NO raw/ tree at all.

Writes work/target_rows.json. Offline; no device. Reads only committed repo
files and this experiment's frozen db.json.
"""
import json, sys, hashlib
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
REPO = EXP.parents[1]
FROZEN = EXP / "work" / "frozen"

HELD = json.loads((REPO / "experiments/EXP-0169-g17p-rerecord/analysis/"
                   "field_verdicts_held_c2load.json").read_text())
VAL = json.loads((REPO / "tools/agx-isa/validation.json").read_text())
DB = json.loads((FROZEN / "db.json").read_text())
INS = {i["mnemonic"]: i for i in DB["instructions"]}

held_rows = sorted(k for k in HELD if k != "_meta")

m4_rows = []
for mn, tbl in VAL["instructions"].items():
    for fname, row in tbl.items():
        if fname == "_instruction":
            continue
        if "EXP-M4-14" in (row.get("evidence") or []):
            m4_rows.append("%s.%s" % (mn, fname))
m4_rows = sorted(m4_rows)
m4_half = [r for r in m4_rows if r.split(".")[0] in ("half_alu_ext8", "half_alu_fma12")]

out = {"_meta": {
    "experiment": "EXP-0180-g17p-halfalu-rerecord",
    "db_sha256": hashlib.sha256((FROZEN / "db.json").read_bytes()).hexdigest(),
    "validation_sha256": hashlib.sha256(
        (REPO / "tools/agx-isa/validation.json").read_bytes()).hexdigest(),
    "held_by_0169": len(held_rows),
    "cites_expm414_all_instructions": len(m4_rows),
    "cites_expm414_half_family": len(m4_half),
}, "rows": {}}

for key in sorted(set(held_rows) | set(m4_half)):
    mn, fn = key.split(".", 1)
    spec = INS.get(mn)
    f = None
    if spec:
        for x in spec["fields"]:
            if x["name"] == fn:
                f = x
                break
    vrow = VAL["instructions"].get(mn, {}).get(fn, {})
    h = HELD.get(key, {})
    rec = {
        "instr": mn, "field": fn,
        "in_held_set": key in held_rows,
        "cites_expm414": key in m4_half,
        "db_start": f["start"] if f else None,
        "db_width": f["width"] if f else None,
        "db_present": f is not None,
        "held_start": h.get("start"), "held_width": h.get("width"),
        "span_moved_since_0169": (
            None if (f is None or h.get("start") is None)
            else (f["start"] != h["start"] or f["width"] != h["width"])),
        "current_label": vrow.get("label"),
        "current_target": vrow.get("target"),
        "current_evidence": vrow.get("evidence"),
        "current_range": vrow.get("range"),
        "current_note": vrow.get("note"),
        "encodable_range": (1 << f["width"]) if f else None,
    }
    out["rows"][key] = rec

(EXP / "work" / "target_rows.json").write_text(json.dumps(out, indent=1, sort_keys=True))
print("distinct fields:", len(out["rows"]))
print("held-by-0169   :", len(held_rows))
print("cites EXP-M4-14 (half family):", len(m4_half))
print("cites EXP-M4-14 (whole db)   :", len(m4_rows))
print("row-claims (a)+(b)           :", len(held_rows) + len(m4_half))
moved = [k for k, v in out["rows"].items() if v["span_moved_since_0169"]]
print("spans moved since EXP-0169   :", moved or "NONE")
missing = [k for k, v in out["rows"].items() if not v["db_present"]]
print("fields absent from pinned db :", missing or "NONE")
print()
for k, v in sorted(out["rows"].items()):
    print("%-36s held=%-5s m414=%-5s start=%-3s w=%-3s enc=%-22s label=%-20s target=%-5s ev=%s"
          % (k, v["in_held_set"], v["cites_expm414"], v["db_start"], v["db_width"],
             v["encodable_range"], v["current_label"], v["current_target"],
             ",".join(v["current_evidence"] or [])))
