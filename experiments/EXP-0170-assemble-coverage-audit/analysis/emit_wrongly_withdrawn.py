#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0170 Arm D, step 3 -- emit analysis/wrongly_withdrawn.json.

Every withheld field whose EXP-0164 verdict does NOT survive re-scoring under the
unchanged EXP-0164 gate once (D.2) never-dispatched placeholders stop contributing
signatures and (D.3) runs the source experiment disowns stop being eligible.

This file is an EVIDENCE DOCUMENT FOR THE ORCHESTRATOR.  It is deliberately NOT in
FIELD-SWEEP-PROTOCOL 5 merge schema: no top-level `label`, and `_meta.mergeable` is
false, so work/merge_verdicts.py cannot consume it even by accident.  EXP-0170
promotes nothing.

Usage: python3 analysis/emit_wrongly_withdrawn.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))

REC = {
 # field -> (recommendation, why)  -- hand-written per field after reading the numbers
 "falu2.srcA_class": ("RESTORE-CANDIDATE",
   "The audit paired run01 against run02. EXP-0138's own README disowns run02 (killed by a "
   "machine-wide MTLCompilerService collapse) and names run06 as its replacement; the gated "
   "pair EXP-0138 actually analysed is run01+run06 with run05 as a third annotating run. "
   "Scored against an eligible partner the field reaches 100.00% agreement on 64 common "
   "values and passes the UNCHANGED gate. Placeholders are not involved (0 dropped)."),
 "falu2.srcB_class": ("RESTORE-CANDIDATE",
   "Same as falu2.srcA_class: 96.88% against the disowned run02, 100.00% against run05."),
}
# Pre-registered device scope of the G17P experiments in flight, read from their own
# committed PRE_REGISTRATION.md (cited per row).  D.6: where a G17P sweep will supersede
# an M4 row, say so and DEFER rather than restore a weak row and upgrade it an hour later.
IN_FLIGHT = {
 "cvt_f2h.op": ("EXP-0168-g17p-dst-resweep",
   "PRE_REGISTRATION.md:53 group B ('the 12 one-field-away'), swept in its 4.6", "DEFER"),
 "cvt_f2i.dst": ("EXP-0168-g17p-dst-resweep",
   "PRE_REGISTRATION.md:52 group A ('the `dst` field name', cvt_f2i listed), swept in its 4.6", "DEFER"),
 "pack_convert.b7": ("EXP-0168-g17p-dst-resweep",
   "PRE_REGISTRATION.md:53 group B, swept in its 4.7; its :363 already cites EXP-0144's "
   "pack_convert.b7 placeholders", "DEFER"),
 "unpack_convert.dst": ("EXP-0168-g17p-dst-resweep",
   "PRE_REGISTRATION.md:52 group A ('the `dst` field name', unpack_convert listed), swept in its 4.7", "DEFER"),
}

DEFAULT_144 = ("REASON-UNSUPPORTED-BUT-STILL-SHORT",
   "The audit's stated reason ('does not reproduce across the two gated runs at >=99% "
   "agreement') rests on m4_20260828_run03 and/or run05, which EXP-0144's own RESULTS.md "
   "disowns ('run01-run05 ... back no label'), and on never-dispatched "
   "`skipped_after_hangs` placeholders scored as observations. With placeholders dropped "
   "the same run pair agrees far better -- for five unpack_convert fields the audit's "
   "0.00% becomes 100.00%. BUT once the disowned runs are excluded EXP-0144 has only ONE "
   "admissible run per instrument, so the field re-scores SINGLE-RUN, not STABLE-LIVE: it "
   "cannot clear a CROSS-RUN gate on committed evidence either way. Note EXP-0144 RESULTS.md "
   "6.5 states it deliberately used a WITHIN-RUN majority-of-3 (escalated to 5) control "
   "instead of a cross-run gate, and why. Whether that control is accepted in place of a "
   "cross-run pair is an orchestrator policy call, not something this audit can settle.")


def main():
    d = json.load(open(os.path.join(HERE, "rescore_D.json")))
    elig = json.load(open(os.path.join(HERE, "run_eligibility.json")))["runs"]
    out = {}
    for key, v in sorted(d["fields"].items()):
        if v["verdict"] == "AGREES":
            continue
        rec, why = REC.get(key, DEFAULT_144)
        s1, s2, s3 = (v["S1_audit"], v["S2_placeholders_dropped"], v["S3_primary"])
        confl = {}
        for r in s3["runs_excluded_as_ineligible"]:
            e = elig.get(r.replace("EXP-0144/", "EXP-0144-m4-emit-pack/")) or {}
            if e.get("source_conflict"):
                confl[r] = e["source_conflict"]
        out[key] = {
          "mnemonic": v["mnemonic"], "field": v["field"],
          # merge_verdicts.py (DEF-0166-2) refuses a verdict whose bits have moved,
          # so the span is carried explicitly and checked against EXP-0164's db too.
          "start": v["start"], "width": v["width"],
          "span_moved_since_EXP-0164_db": v["span_moved_since_EXP-0164"],
          "label_when_withheld": v["label_when_withheld"],
          "target": v["target"], "evidence": v["evidence"],
          "recommendation": rec, "why": why,
          "g17p_sweep_in_flight": ({"experiment": IN_FLIGHT[key][0],
                                    "cite": IN_FLIGHT[key][1],
                                    "action": IN_FLIGHT[key][2],
                                    "note": "an M4 restoration here would be superseded; "
                                            "EXP-0170 recommends waiting for the G17P row"}
                                   if key in IN_FLIGHT else None),
          "audit_scoring_EXP-0164": {
             "bucket": s1["bucket"], "runA": s1["runA"], "runB": s1["runB"],
             "common": s1["common"], "agree_pct": s1["agree_pct"],
             "movedA": s1["movedA"], "movedB": s1["movedB"],
             "raw_files": s1["raw_files"]},
          "exp0170_scoring": {
             "S2_same_eligibility_placeholders_dropped": {
                "bucket": s2["bucket"], "runA": s2["runA"], "runB": s2["runB"],
                "common": s2["common"], "agree_pct": s2["agree_pct"],
                "placeholder_records_dropped": s2["placeholder_records_dropped"],
                "runs_used": s2["runs_used"]},
             "S3_primary_placeholders_dropped_and_disowned_runs_excluded": {
                "bucket": s3["bucket"], "runA": s3["runA"], "runB": s3["runB"],
                "common": s3["common"], "agree_pct": s3["agree_pct"],
                "runs_used": s3["runs_used"],
                "runs_excluded_as_ineligible": s3["runs_excluded_as_ineligible"]},
             "S3b_sensitivity_scope_md_runs_readmitted":
                v["S3b_sensitivity_scope_md_readmitted"]},
          "source_experiment_self_conflict": confl or None,
          "verdict": v["verdict"]}

    doc = {"_meta": {
      "generated_by": "EXP-0170/analysis/emit_wrongly_withdrawn.py",
      "mergeable": False,
      "NOT_a_merge_file":
        "deliberately NOT FIELD-SWEEP-PROTOCOL 5 schema -- no top-level `label` key, so "
        "work/merge_verdicts.py cannot consume it. EXP-0170 promotes NOTHING; this is a "
        "list for the orchestrator to rule on.",
      "gate": d["_meta"]["gate"],
      "scorings": d["_meta"]["scorings"],
      "population": "the 266 fields in EXP-0164's withhold_inert_single.json (81), "
                    "withhold_unstable.json (41) and withhold_unverifiable.json (144)",
      "verdict_totals_over_all_266": d["verdict_totals"],
      "listed_here": "only the fields whose verdict is NOT `AGREES`",
      "g17p_supersession": "4 of the 13 rows are inside EXP-0168-g17p-dst-resweep's "
                           "pre-registered device scope; see each row's g17p_sweep_in_flight. "
                           "falu2.srcA_class/srcB_class are in NEITHER EXP-0168's nor "
                           "EXP-0169's scope (EXP-0169 owns the UNVERIFIABLE 144; these are "
                           "in the UNSTABLE 41), so nothing in flight supersedes them."},
     "fields": out}
    json.dump(doc, open(os.path.join(HERE, "wrongly_withdrawn.json"), "w"),
              indent=1, sort_keys=True)
    print("listed %d of 266 (verdicts: %s)" % (len(out), d["verdict_totals"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
