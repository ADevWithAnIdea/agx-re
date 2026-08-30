#!/usr/bin/env python3
"""Arm O — adjudicate `ret.scoreboard` against the PRE-REGISTERED bar.

PRE_REGISTRATION section 9 / H6, frozen before any case ran:

  POSITIVE CONTROL (must fire, or the arm is VOID): at the BASELINE scoreboard
  value there must exist a filler length F* at which the callee's asynchronous
  `device_load` has NOT landed and a larger F at which it HAS -- reproducibly in
  both gated runs. If the load always lands, or never does, the instrument is
  not measuring ordering and the arm proves nothing.

  PROMOTION (narrow, and the only thing that overturns three prior declines):
  that threshold must SHIFT as a function of the `scoreboard` value, the same
  way in both runs. Only a shift is ordering-specific power.

  NOT A PROMOTION: a scoreboard value that breaks the program at every filler
  length, or that changes the dump in the completion-flushed sense EXP-0172
  already measured and correctly declined.

`R_LOAD` is loaded from a ramp buffer whose word 0 is 0x600D0000. "Landed" means
that value is in the register at dump time; anything else (the seed, zero, or
poison) means it had not.
"""
from __future__ import print_function

import json
from collections import defaultdict
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H  # noqa: E402

RUNS = ("g17p_20260830_run13O", "g17p_20260830_run14O")
LANDED = 0x600D0000
BASELINE_SB = 0x00


def load(r):
    return [json.loads(l) for l in
            (EXP / "raw" / r / "sweep.jsonl").read_text().splitlines() if l.strip()]


def filler_of(rec):
    n = rec.get("note") or ""
    return int(n.split("filler=")[1]) if "filler=" in n else None


data = {}
victims = 0
for run in RUNS:
    for x in load(run):
        if x["arm"] != "O":
            continue
        if x.get("validity") == "invalid_victim":
            victims += 1
            continue
        f = filler_of(x)
        regs = (x.get("observed") or {}).get("regs")
        landed = bool(regs and regs[H.R_LOAD] == LANDED)
        data[(run, x["carrier"], x["value"], f)] = {
            "landed": landed, "outcome": x["outcome"],
            "reg": (regs[H.R_LOAD] if regs else None),
            "os_class": x.get("os_class"),
        }

carriers = sorted({k[1] for k in data})
fillers = sorted({k[3] for k in data if k[3] is not None})
sbs = sorted({k[2] for k in data})

report = {
    "runs": list(RUNS), "carriers": carriers, "fillers": fillers,
    "scoreboard_values": [hex(s) for s in sbs],
    "landed_marker": hex(LANDED), "R_LOAD": H.R_LOAD,
    "invalid_victim_excluded": victims,
    "bar": ("PRE_REGISTRATION section 9: positive control must fire, then the "
            "filler-length threshold must SHIFT with the scoreboard value in "
            "BOTH runs. Anything less = VOID / decline."),
}

# ---- the positive control -------------------------------------------------
control = {}
for run in RUNS:
    for car in carriers:
        seq = [(f, data.get((run, car, BASELINE_SB, f), {}).get("landed"))
               for f in fillers]
        control["%s|%s" % (run, car)] = {
            "landed_by_filler": {str(f): v for f, v in seq},
            "any_not_landed": any(v is False for _, v in seq),
            "any_landed": any(v is True for _, v in seq),
            "threshold": next((f for f, v in seq if v), None) if any(
                v is False for _, v in seq) else None,
        }
report["positive_control"] = control
fired = all(c["any_not_landed"] and c["any_landed"] for c in control.values())
report["positive_control_fired"] = bool(fired)

# ---- would the threshold shift? (only meaningful if the control fired) ----
thresholds = defaultdict(dict)
for run in RUNS:
    for car in carriers:
        for sb in sbs:
            seq = [(f, data.get((run, car, sb, f), {}).get("landed")) for f in fillers]
            thresholds["%s|%s" % (run, car)][hex(sb)] = (
                next((f for f, v in seq if v), None)
                if any(v is False for _, v in seq) else
                ("always" if all(v for _, v in seq) else "never"))
report["thresholds_by_scoreboard"] = {k: v for k, v in thresholds.items()}
distinct = {k: sorted({str(x) for x in v.values()}) for k, v in thresholds.items()}
report["distinct_thresholds_per_arm"] = distinct
report["threshold_shifts_with_scoreboard"] = bool(
    fired and all(len(v) > 1 for v in distinct.values()))

if not fired:
    report["VERDICT"] = (
        "ARM VOID. The positive control did NOT fire: the load's landedness does "
        "not vary with filler length at the baseline scoreboard value, so this "
        "carrier is not measuring ordering at all. `ret.scoreboard` therefore "
        "stays DECLINED at `corpus-correlation`, exactly as pre-registered, and "
        "for the same reason EXP-0172 and two earlier experiments declined it. A "
        "clever instrument does not get to talk past a failed control.")
elif not report["threshold_shifts_with_scoreboard"]:
    report["VERDICT"] = (
        "CONTROL FIRED, PROMOTION DECLINED. A filler-length threshold exists, so "
        "the instrument does measure ordering -- but the threshold does NOT shift "
        "with the scoreboard value, which is the only thing that would have "
        "demonstrated ordering-specific power. `ret.scoreboard` stays "
        "`corpus-correlation`.")
else:
    report["VERDICT"] = (
        "CONTROL FIRED AND THE THRESHOLD SHIFTS. This is the pre-registered "
        "promotion condition; check it holds identically in BOTH runs before "
        "acting on it.")

(HERE / "order_arm.json").write_text(json.dumps(report, indent=1, sort_keys=True))
print(json.dumps({k: report[k] for k in
                  ("positive_control_fired", "threshold_shifts_with_scoreboard",
                   "invalid_victim_excluded", "distinct_thresholds_per_arm",
                   "VERDICT")}, indent=1, sort_keys=True))
print()
for k, v in sorted(control.items()):
    print("%-46s landed_by_filler=%s" % (k, v["landed_by_filler"]))
