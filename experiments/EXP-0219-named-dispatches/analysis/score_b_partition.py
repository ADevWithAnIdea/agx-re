#!/usr/bin/env python3
"""EXP-0219 part-B, Gate E in the form the observable admits.

`tex_sample.mode` bit 6 makes the observation a function of the DISPATCH INDEX,
so cross-run payload equality -- the criterion EXP-0213 used, and the one it
failed on -- cannot be met by ANY capture of this field, on any machine, however
quiet.  What CAN be reproduced, and what this scores, is:

  (1) the LIVE/INERT partition per arm: does the bit6-set payload SET differ from
      its bit6-clear twin's, over the 32 matched pairs;
  (2) the PERIOD STRUCTURE: every alternating sequence has smallest period in
      {4, 8};
  (3) the bit6-CLEAR control: 0 unstable values, every arm, every capture.
"""
import json
import collections
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
RUNS = ["g17p_e0219_B_rep_run01", "g17p_e0219_B_rep_run02", "g17p_e0219_B_rep_run03"]
QUAD = [v for v in range(256) if (v & 0x40) and not (v & 0x08) and not (v & 0x04)]


def payloads(run):
    per = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in (json.loads(l) for l in (EXP / "raw" / run / "sweep.jsonl").open()):
        if r["field"] == "mode":
            per[r["carrier"]][r["value"]].add(
                json.dumps(r["observed"].get("probe"), sort_keys=True))
    return per


out = {}
tab = {}
for run in RUNS:
    p = payloads(run)
    for arm in sorted(p):
        diff = sum(1 for v in QUAD if p[arm][v] != p[arm][v ^ 0x40])
        tab.setdefault(arm, {})[run] = "%d/32" % diff
out["bit6_live_pairs_per_arm"] = tab
out["partition_identical_across_all_three_captures"] = {
    arm: (len({("live" if int(x.split("/")[0]) > 0 else "inert")
               for x in d.values()}) == 1) for arm, d in tab.items()}
out["live_arms"] = sorted(a for a, d in tab.items()
                          if all(int(x.split("/")[0]) > 0 for x in d.values()))
out["inert_arms"] = sorted(a for a, d in tab.items()
                           if all(int(x.split("/")[0]) == 0 for x in d.values()))
print(json.dumps(out, indent=1))
