#!/usr/bin/env python3
"""EXP-0188 A3 RE-SCOPING: build `harness/arms188_gated.json` from the frozen
`harness/arms188.json`, with the reason for every reduction recorded in the file.

WHY, stated as a measurement rather than a preference. The pre-freeze hazard
probe found FOUR `if_push` occurrences -- the FIRST push of `cf_nl2`, `cf_nlif`,
`cf_wbrk` and `cf_lcont`, all `scope_kind == 0x1a` loop-iteration regions -- where
`scope` values with bit 1 CLEAR fault or hang and values with bit 1 SET run
correctly. A hang costs the watchdog times the majority-of-3 confirmation: run02
measured 27 records in 70.9 s with 7 hangs, i.e. ~8 s per hang case at a 2 s
watchdog. A dense 256-value sweep of one such occurrence is ~7-11 minutes, and
four of them, twice, does not fit the window.

FIELD-SWEEP-PROTOCOL 3(c) is explicit that a per-field HANG BUDGET is the wrong
answer -- it guarantees the region is never mapped, which is how `frag_color_pack`'s
wall at 0xC0 escaped three experiments. So the budget is NOT reinstated: there is
still no abort path, and the hazardous region is still dispatched in full. What
changes is WHERE:

  * A5, after measuring it: at ~8 s per hang case a dense 256-value sweep of ONE
    hazardous occurrence is ~18 minutes, so a gated PAIR containing one does not
    fit the window at all. The dense map is therefore SPLIT OUT of the gated pair
    into a named, non-gated MAPPING PASS exactly as FIELD-SWEEP-PROTOCOL 3(c)
    prescribes ("declare a named, non-gated mapping pass ... and dispatch the
    whole range"), run separately if the window allows and reported as NOT RUN if
    it does not. The gated pair is not weakened by this: the effect it has to
    detect is a two-class partition, and it is measured at ALL FOUR hazardous
    occurrences instead of one.
  * All four hazardous occurrences keep the FOUR-VALUE hazard probe
    (0x00 / 0x54 / 0x56 / 0xFF) inside both gated runs, so the bit-1 rule is
    REPLICATED on three further carriers under the same gate -- 3 independent
    reproductions of the effect rather than 3 more copies of the same 11 minutes.
  * The clean `if_push` occurrences are reduced to five, chosen to span all four
    observed `scope_kind` values (0x1a, 0x21, 0x25, 0x29) and both compiled
    `scope` values. Occurrences beyond that are duplicates along the dimension.
  * `simd_ballot`/`simd_shuffle` keep one occurrence per carrier -- the carrier IS
    the dimension (divergence depth 0,1,2,3 + loop), so a second occurrence in the
    same kernel adds no dimension spread.
  * `iadd2` is unchanged: all seven operand formats, dense.

Every arm dropped here is recorded in `dropped_arms` with its reason, and the
frozen `arms188.json` is not modified.
"""
import json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
doc = json.loads((EXP / "harness" / "arms188.json").read_text())

HAZ_DENSE = set()          # A5: see the note below
HAZ_PROBE = {"cf_nl2#0", "cf_nlif#0", "cf_wbrk#0", "cf_lcont#0"}
PROBE_VALUES = [0x00, 0x54, 0x56, 0xFF]
# five clean occurrences spanning every observed scope_kind and both scope values
CLEAN_KEEP = {"cf_nl2#1", "cf_nl3#1", "cf_nl3#2", "cf_ifnl#0", "cf_lcont#2"}
SD_KEEP_OCC = 0            # one occurrence per SIMD carrier: the carrier is the dimension

keep, dropped = [], []
for a in doc["arms"]:
    occ_id = "%s#%d" % (a["carrier"], a["occ"])
    if a["instr"] == "if_push":
        if occ_id in HAZ_DENSE or occ_id in CLEAN_KEEP:
            keep.append(a)
        elif occ_id in HAZ_PROBE:
            b = dict(a)
            if a["role"] == "target":
                b["values"] = PROBE_VALUES
                b["note"] = ("A3: hazard REPLICATION at four values (0x00/0x54/"
                             "0x56/0xFF); the dense map of this hazard is carried "
                             "by cf_nl2#0 in the same runs")
            keep.append(b)
        else:
            dropped.append({"arm": a["arm"], "reason": "duplicate along the "
                            "dimension: its scope_kind and compiled scope value "
                            "are already covered by a retained occurrence"})
        continue
    if a["instr"] in ("simd_ballot", "simd_shuffle"):
        if a["occ"] == SD_KEEP_OCC:
            keep.append(a)
        else:
            dropped.append({"arm": a["arm"], "reason": "second occurrence in the "
                            "same kernel: the CARRIER is the dimension "
                            "(divergence depth), so this adds no spread"})
        continue
    keep.append(a)

out = {"generated_from": "harness/arms188.json",
       "rule": "analysis/gen_gated_arms.py docstring (amendment A3)",
       "dropped_carriers": doc.get("dropped_carriers", []),
       "dropped_arms": dropped, "arms": keep}
p = EXP / "harness" / "arms188_gated.json"
p.write_text(json.dumps(out, indent=1, sort_keys=True))
print("gated arms=%d cases=%d dropped_arms=%d -> %s"
      % (len(keep), sum(len(a["values"]) for a in keep), len(dropped), p))
