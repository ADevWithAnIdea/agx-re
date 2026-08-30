#!/usr/bin/env python3
"""EXP-0165 ESCAPE HATCH: put `sfu_marker` back to a zero-field descriptor.

EXP-0165 gave `sfu_marker` its two HW-measured live-bit fields (EXP-0146 on
M4/G16G, reproduced on G17P in three carriers by EXP-0157).  Because they are NEW
field names, tools/agx-isa/validate_labels.py hard-fails with exactly two
`MISSING label` errors until analysis/field_verdicts.json is merged into
validation.json (which this experiment may not edit).

Merging the verdicts is the intended fix.  This script is the alternative, if the
label owner wants validate_labels.py green BEFORE merging:

  python3 analysis/revert_sfu_marker_fields.py tools/agx-isa/db.json

It removes only the two fields and restores the pinned match; the corrected
semantics and provenance stay, because they are hardware facts either way.
"""
from __future__ import print_function
import json, sys

p = sys.argv[1]
db = json.load(open(p))
for i in db["instructions"]:
    if i["mnemonic"] != "sfu_marker":
        continue
    assert [f["name"] for f in i["fields"]] == ["b0_hi", "b1_hi"], \
        "sfu_marker does not carry EXP-0165's two fields"
    i["fields"] = []
    i["match"] = [[0, 8, 6], [8, 8, 2]]
    i["semantics"] += (" [EXP-0165 revert] The two fields were removed again so "
                       "validate_labels.py passes before the evidence rows exist; "
                       "the bit rules above are unchanged and still apply.")
    json.dump(db, open(p, "w"), indent=2)
    print("reverted sfu_marker to a zero-field descriptor in", p)
    break
else:
    raise SystemExit("sfu_marker not found")
