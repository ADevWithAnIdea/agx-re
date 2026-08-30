#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0189 step 5 -- final reclassify.json.

Merges audit.py's frozen buckets with rescue.py's widened-evidence re-run and emits
the deliverable the orchestrator merges from: flat `<mnemonic>.<field>`, WITH
`start`/`width` from the pinned db snapshot (the merger refuses a row whose bits
moved), plus the ranked list of instructions that lose emittable status.

Two recommendation sets are emitted and BOTH are honest:
  * `withhold_recommended` -- strict minus every field rescued by a widened evidence
    set. This is the number I stand behind: 38 of 166.
  * `withhold_as_cited`    -- strict as the `evidence` lists literally stand today.
    This is what an auditor reproduces from validation.json alone: 33 of 166.
The gap between them is entirely stale/narrow `evidence` citations, which are a
bookkeeping repair, not new hardware evidence.

Usage: python3 analysis/finalize.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
WORK = os.path.join(EXP, "work")
WITHHOLD = ("INERT-SINGLE", "UNSTABLE", "UNVERIFIABLE")


def main():
    val = json.load(open(os.path.join(WORK, "validation.snapshot.json")))
    db = json.load(open(os.path.join(WORK, "db.snapshot.json")))
    audit = json.load(open(os.path.join(HERE, "audit.json")))["fields"]
    res = json.load(open(os.path.join(HERE, "rescue.json")))
    emit = json.load(open(os.path.join(HERE, "emittability.json")))
    DBF = {i["mnemonic"]: {f["name"]: (f["start"], f["width"])
                           for f in i.get("fields", [])} for i in db["instructions"]}

    rescued = res["rescued"]
    as_cited = sorted(k for k, r in audit.items() if r["bucket"] in WITHHOLD)
    recommended = sorted(k for k in as_cited
                         if rescued.get(k, {}).get("new_bucket", audit[k]["bucket"])
                         in WITHHOLD)

    def row(k):
        r = audit[k]
        st, wd = DBF.get(r["mnemonic"], {}).get(r["field"], (None, None))
        final = rescued.get(k, {}).get("new_bucket", r["bucket"])
        vals = rescued.get(k, {}).get("max_values", r["max_values_dispatched"])
        moved = rescued.get(k, {}).get("moved_total", r["moved_total"])
        arms = rescued.get(k, {}).get("n_arms_tested", r["n_arms_that_tested_the_field"])
        raws = rescued.get(k, {}).get("raw_files", r["raw_files"])
        return {"start": st, "width": wd,
                "label": "untested", "label_now": r["label"],
                "bucket_as_cited": r["bucket"], "bucket_after_widening": final,
                "reason": r["unverifiable_reason"],
                "target": r["target"], "evidence": r["evidence"],
                "n_arms_that_tested_the_field": arms,
                "max_values_dispatched": vals, "moved_total": moved,
                "widened_with_dirs": rescued.get(k, {}).get("uncited_dirs_with_records", []),
                "raw_files": raws,
                "range": val["instructions"][r["mnemonic"]][r["field"]].get("range", ""),
                "note": ("EXP-0189 withheld (%s): %d values dispatched over %d arm(s), "
                         "%d observations moved, re-derived from raw under EXP-0164's "
                         "frozen thresholds (>=2 gated runs, moved>=1 in both, "
                         ">=99%% per-value agreement, moved >= 2x disagreements).%s"
                         % (final, vals, arms, moved,
                            (" Reason: %s." % r["unverifiable_reason"])
                            if r["unverifiable_reason"] else ""))}

    out = {
        "_meta": {
            "experiment": "EXP-0189-closing-audit",
            "schema": "FIELD-SWEEP-PROTOCOL.md section 5, flat <mnemonic>.<field>; "
                      "start/width carried from work/db.snapshot.json so a row whose "
                      "bits moved is refused rather than silently mis-merged",
            "db_sha256": val["db_sha256"],
            "validation_snapshot_sha256":
                "867e4b05dbcd000f98a8ac4705d07f419b1d0a69c4b276e030b0daf225eaf0b7",
            "policy": "withhold INERT-SINGLE / UNSTABLE / UNVERIFIABLE "
                      "(EXP-0164's frozen rule, not re-tuned). INERT-MULTI and "
                      "SINGLE-RUN are NOT withheld.",
            "counts": {"emitter_grade_fields_audited": len(audit),
                       "withhold_recommended": len(recommended),
                       "withhold_as_cited": len(as_cited),
                       "emittable_published": val["coverage"]["emittable_of_emitter_relevant"],
                       "emittable_recommended":
                           res["emittability"]["strict_after_rescue"]["emittable"],
                       "emittable_as_cited": res["emittability"]["strict"]["emittable"],
                       "denominator": emit["_meta"]["denominator_emitter_relevant"]},
        },
        "withhold_recommended": {k: row(k) for k in recommended},
        "withhold_as_cited_only": sorted(set(as_cited) - set(recommended)),
        "citation_repairs_not_withdrawals": {
            k: {"cited": rescued[k]["cited_dirs"],
                "records_actually_live_in": rescued[k]["uncited_dirs_with_records"],
                "underscore_named_in": rescued[k]["underscore_dirs"],
                "bucket_after_widening": rescued[k]["new_bucket"]}
            for k in sorted(set(as_cited) - set(recommended)) if k in rescued},
        "instructions_that_lose_emittable_status":
            res["emittability"]["strict_after_rescue"]["lost_vs_published"],
        "ranked_losses": json.load(open(os.path.join(WORK, "lost_after_rescue.json")))["detail"],
        "instruction_entries_without_dispatch_record": {
            m: v for m, v in emit["instruction_entry_audit"].items()
            if v["label"] in ("hardware-run", "isolated-byte-diff")
            and v["verdict"] != "dispatched"},
        "coverage_overclaims": json.load(open(os.path.join(WORK, "coverage_overclaims.json"))),
        "range_text_contradicts_raw": json.load(open(os.path.join(WORK, "range_contradictions.json"))),
    }
    json.dump(out, open(os.path.join(HERE, "reclassify.json"), "w"), indent=1, sort_keys=True)
    print("withhold_recommended %d | withhold_as_cited %d | citation repairs %d"
          % (len(recommended), len(as_cited), len(out["citation_repairs_not_withdrawals"])))
    print("emittable: published %d | recommended %d | as-cited %d  (of %d)"
          % (val["coverage"]["emittable_of_emitter_relevant"],
             res["emittability"]["strict_after_rescue"]["emittable"],
             res["emittability"]["strict"]["emittable"],
             emit["_meta"]["denominator_emitter_relevant"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
