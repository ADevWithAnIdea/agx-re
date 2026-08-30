#!/usr/bin/env python3
"""EXP-0188 PRE-FREEZE HAZARD PROBE (calibration only -- NO VERDICT MAY CITE IT).

Writes `harness/arms_hazprobe.json`: the same `if_push.scope` occurrences as the
frozen arm list, but four values only -- 0x00, the compiled 0x54, the documented
alternate bank 0x56, and 0xFF.

WHY. The pre-freeze pilot found that the FIRST loop-iteration push of `cf_nl2`
turns every sampled off-baseline value into a contained FAULT or a GPU HANG,
while three other loop-iteration pushes are clean at the same values. A hang
costs the watchdog plus a child restart, times the majority-of-3 confirmation, so
sizing the gated pair requires knowing HOW MANY occurrences behave that way --
guessing would either blow the window or silently truncate the sweep.

This is exactly the use FIELD-SWEEP-PROTOCOL 3(c) sanctions: when adjacent values
suggest a CONTIGUOUS hazard, stop treating it as a per-value accident and map it
deliberately, in a named non-gated pass, instead of letting a budget guarantee the
region is never characterised.

CLEAN-ROOM: OWN-SHADER. Only our own compiled MSL is dispatched.
"""
import json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
doc = json.loads((EXP / "harness" / "arms188.json").read_text())
out = []
for a in doc["arms"]:
    if a["role"] == "target" and a["instr"] == "if_push":
        b = dict(a)
        b["values"] = [0x00, 0x54, 0x56, 0xFF]
        b["note"] = "PRE-FREEZE HAZARD PROBE, four values"
        out.append(b)
p = EXP / "harness" / "arms_hazprobe.json"
p.write_text(json.dumps({"generated_from": "harness/arms188.json",
                         "purpose": "pre-freeze hazard map, calibration only",
                         "dropped_carriers": [], "arms": out}, indent=1,
                        sort_keys=True))
print("hazard-probe arms=%d cases=%d -> %s" % (len(out), 4 * len(out), p))
