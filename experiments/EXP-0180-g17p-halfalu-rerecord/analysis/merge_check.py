#!/usr/bin/env python3
"""EXP-0180 merge gate. REFUSES any row whose db.json `start`/`width` has moved since this
experiment measured it, and any row missing a required coverage key.

Run before the orchestrator merges analysis/field_verdicts.json into
tools/agx-isa/validation.json. Exit code 1 means DO NOT MERGE.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
REPO = EXP.parents[1]
REQUIRED = ("values_dispatched", "distinct_bytes", "encodable_range", "start", "width",
            "coverage_pct", "thin", "under_covered", "measured_encodable_range",
            "expressiveness", "verdict_class", "label", "target", "range")


def main():
    v = json.loads((EXP / "analysis" / "field_verdicts.json").read_text())
    live = json.loads((REPO / "tools/agx-isa/db.json").read_text())
    INS = {i["mnemonic"]: i for i in live["instructions"]}
    frozen = json.loads((EXP / "work" / "frozen" / "db.json").read_text())
    FINS = {i["mnemonic"]: i for i in frozen["instructions"]}
    bad = []
    for key, row in sorted(v.items()):
        mn, fn = key.split(".", 1)
        for name, tbl in (("live", INS), ("frozen", FINS)):
            f = next((x for x in tbl.get(mn, {}).get("fields", []) if x["name"] == fn), None)
            if f is None:
                bad.append((key, "%s db.json no longer defines this field" % name))
            elif f["start"] != row["start"] or f["width"] != row["width"]:
                bad.append((key, "%s span moved: db=%d/%d verdict=%d/%d"
                            % (name, f["start"], f["width"], row["start"], row["width"])))
        missing = [k for k in REQUIRED if k not in row]
        if missing:
            bad.append((key, "missing coverage keys: %r" % missing))
        if row["label"] == "hardware-run" and row.get("expressiveness") not in ("YES",):
            if row["verdict_class"].startswith("INERT"):
                bad.append((key, "hardware-run on an INERT reading whose dimension is not "
                                 "expressible by these carriers (gate_expressiveness)"))
    for key, why in bad:
        print("REFUSE %-34s %s" % (key, why))
    print("\n%d rows checked, %d refusals" % (len(v), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
