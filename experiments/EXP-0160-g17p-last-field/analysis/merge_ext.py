#!/usr/bin/env python3
"""EXP-0160: fold Addendum A's two `srcB` verdicts into field_verdicts.json.

`analysis/field_verdicts.json` is the FIELD-SWEEP-PROTOCOL section 5 deliverable
the orchestrator merges, so it must carry every field this experiment decided.
The extension's own output (`field_verdicts_ext.json`) is kept alongside it,
unmodified, as the raw product of the extension runs.

  python3 analysis/merge_ext.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
main = json.loads((HERE / "field_verdicts.json").read_text())
ext = json.loads((HERE / "field_verdicts_ext.json").read_text())

for k, v in ext.items():
    if k == "_meta":
        main.setdefault("_meta", {})["addendum_A"] = v
    elif k in ("arms", "extra_probes"):
        main.setdefault(k, {}).update(v)
    elif k == "db_defects":
        continue                      # identical block, already present
    else:
        main[k] = v

(HERE / "field_verdicts.json").write_text(json.dumps(main, indent=1, sort_keys=True))
labs = {k: v["label"] for k, v in main.items()
        if isinstance(v, dict) and "label" in v}
print(json.dumps(labs, indent=1, sort_keys=True))
