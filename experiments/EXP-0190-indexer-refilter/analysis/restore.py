#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0190 step 6 -- what legitimately comes back, and what the correction is worth.

Reuses EXP-0189's `emittable_current` (imported, not reimplemented) and this
experiment's two audit runs (legacy index vs refiltered index).  Applies the frozen
restoration policy of PRE_REGISTRATION section 6:

    a withdrawn row (label `untested`, note recording an EXP-0164/EXP-0189 withholding)
    is restored ONLY if it buckets STABLE-LIVE -- >=99 % per-value cross-run agreement,
    moved >= 2.0 * disagreements, moved > 0.

Never-moving rows are listed separately and are NOT counted: per the dispatch they are
promotable only with a carrier-dimension argument this experiment does not make.

Writes analysis/restore.json.
Usage: python3 analysis/restore.py
"""
import copy, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
WORK = os.path.join(EXP, "work")
sys.path.insert(0, HERE)
from recount import emittable_current, EMIT_OK, WITHHOLD          # noqa: E402

# Rows a prior audit withdrew for a reason this experiment's movement gate cannot see.
# Restoring one here would be smuggling a different question past a gate that does not
# ask it, so each is listed with the ruling that must be answered first.
BLOCKED_BY_PRIOR_RULING = {
    "get_sr.form": (
        "EXP-0189 section 8a withdrew this on LABEL-DEFINITION grounds, not on movement: all 12 "
        "records carry oracle:null, match:false, outcome:'wrong_value' -- including cases "
        "whose bytes equal the arm's own unmutated anchor -- EXP-0178 filed no verdict for "
        "it (its field_verdicts.json has only sr_sel/dp_width/dp_marker), and EXP-0172 "
        "spanned the datapath-width dimension in both directions and concluded NOT "
        "emitter-grade. It passes THIS experiment's stable-live gate (2 values, three stage "
        "carriers, 100.00 % agreement) because that gate measures baseline-hash MOVEMENT, "
        "which EXP-0181 classifies as 'the BYTES are live -- nothing about semantics'. "
        "Movement was never the objection. Not restored here."),
}


def main():
    val = json.load(open(os.path.join(WORK, "validation.snapshot.json")))
    db = json.load(open(os.path.join(WORK, "db.snapshot.json")))
    A = json.load(open(os.path.join(HERE, "audit.json")))
    L = json.load(open(os.path.join(HERE, "audit_legacy.json")))
    cur, leg = A["fields"], L["fields"]
    DBF = {i["mnemonic"]: {f["name"]: (f["start"], f["width"]) for f in i.get("fields", [])}
           for i in db["instructions"]}

    def sw(idx):
        return sorted(k for k, r in idx.items()
                      if r["cohort"] == "emitter-grade" and r["bucket"] in WITHHOLD)

    base, rel, _ = emittable_current(val, db, [], [])
    e_leg, _, why_leg = emittable_current(val, db, sw(leg), [])
    e_cur, _, why_cur = emittable_current(val, db, sw(cur), [])

    # ---- which withdrawn rows come back ----------------------------------
    restore, blocked, inert_hold, still = {}, {}, {}, {}
    for k, r in sorted(cur.items()):
        if r["cohort"] != "withdrawn":
            continue
        mn, fn = r["mnemonic"], r["field"]
        st, wd = DBF.get(mn, {}).get(fn, (None, None))
        row = val["instructions"][mn][fn]
        rec = {
            "start": st, "width": wd,
            "label_now": row.get("label"),
            "recommend_label": "hardware-run",
            "bucket": r["bucket"],
            "target": r["target"],
            "evidence": r["evidence"],
            "range_now": row.get("range", ""),
            "note_now": row.get("note", ""),
            "n_arms_that_tested_the_field": r["n_arms_that_tested_the_field"],
            "max_values_dispatched": r["max_values_dispatched"],
            "moved_total": r["moved_total"],
            "arms_tested": r["arms_tested"],
            "raw_files": r["raw_files"],
            "bucket_under_legacy_index": leg[k]["bucket"],
            "recovered_by": ("underscore-refilter" if leg[k]["bucket"] != r["bucket"]
                             else "evidence-citation-repair (already committed); the "
                                  "underscore refilter changes nothing for this row"),
            "cross_run": [
                {"experiment": e, "arm": a, "moved_total": v["moved_total"],
                 "n_gated_runs": v["n_gated_runs"], "cross_run": v["cross_run"],
                 "attribution": v["attribution"],
                 "runs": {rr: {kk: vv[kk] for kk in ("n_values", "moved", "n_cases",
                                                     "n_contam", "labels")}
                          for rr, vv in v["runs"].items()}}
                for e, ex in r["per_experiment"].items() for a, v in ex.items()
                if v["stable_live"]],
        }
        if k in BLOCKED_BY_PRIOR_RULING:
            rec["not_restored_because"] = BLOCKED_BY_PRIOR_RULING[k]
            blocked[k] = rec
        elif r["bucket"] == "STABLE-LIVE":
            restore[k] = rec
        elif r["bucket"] == "INERT-MULTI":
            rec["recommend_label"] = "untested"
            rec["not_restored_because"] = (
                "never moved on any arm. Per the dispatch a never-moving field is "
                "promotable only if the carriers differ in the dimension the field "
                "controls; that is a per-field semantic argument this experiment does not "
                "make. Listed, not counted.")
            inert_hold[k] = rec
        else:
            still[k] = {"bucket": r["bucket"], "reason": r["unverifiable_reason"],
                        "moved_total": r["moved_total"],
                        "max_values_dispatched": r["max_values_dispatched"],
                        "n_arms_that_tested_the_field": r["n_arms_that_tested_the_field"]}

    # ---- what restoring them is worth ------------------------------------
    val2 = copy.deepcopy(val)
    for k, rec in restore.items():
        mn, fn = k.split(".", 1)
        val2["instructions"][mn][fn]["label"] = rec["recommend_label"]
    e_res, _, _ = emittable_current(val2, db, sw(cur), [])
    n_eg = (val["coverage"]["by_label"]["hardware-run"] +
            val["coverage"]["by_label"]["isolated-byte-diff"])

    out = {
        "_meta": {
            "experiment": "EXP-0190-indexer-refilter",
            "schema": "FIELD-SWEEP-PROTOCOL.md section 5, flat <mnemonic>.<field>, with "
                      "start/width from work/db.snapshot.json (the merger refuses a row "
                      "whose bits moved)",
            "db_sha256": val["db_sha256"],
            "policy": "PRE_REGISTRATION section 6: restore iff STABLE-LIVE under the "
                      "unchanged EXP-0164 thresholds (>=99 % per-value cross-run "
                      "agreement, moved >= 2.0 * disagreements, moved > 0)",
            "published_today": {"emittable_of_emitter_relevant":
                                val["coverage"]["emittable_of_emitter_relevant"],
                                "emitter_grade_fields": n_eg,
                                "total_fields": val["coverage"]["total_fields"]},
            "counts": {"withdrawn_rows_audited":
                       sum(1 for r in cur.values() if r["cohort"] == "withdrawn"),
                       "restored": len(restore),
                       "blocked_by_prior_ruling": len(blocked),
                       "not_restored_never_moved": len(inert_hold),
                       "remain_withheld": len(still)},
        },
        "headline": {
            "C1_published_rule_no_withholding": len(base),
            "strict_rederivation_with_LEGACY_index": len(e_leg),
            "strict_rederivation_with_CORRECTED_index": len(e_cur),
            "instructions_the_legacy_index_would_have_withdrawn":
                sorted(set(base) - set(e_leg)),
            "why_each": {m: why_leg[m] for m in sorted(set(base) - set(e_leg))},
            "instructions_the_corrected_index_withdraws": sorted(set(base) - set(e_cur)),
            "emittable_after_restoration": len(e_res),
            "emitter_grade_fields_after_restoration": n_eg + len(restore),
        },
        "restore": restore,
        "blocked_by_prior_ruling": blocked,
        "not_restored_requires_dimension_argument": inert_hold,
        "remain_withheld": still,
    }
    json.dump(out, open(os.path.join(HERE, "restore.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(out["_meta"]["counts"], sort_keys=True))
    print(json.dumps(out["headline"], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
