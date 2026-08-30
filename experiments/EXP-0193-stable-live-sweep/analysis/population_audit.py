#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0193 -- apply EXP-0192's frozen criterion to the FULL 337-arm STABLE-LIVE population.

THIS FILE CONTAINS NO CRITERION.  It is a scope driver.

EXP-0192 froze its rule in `EXP-0192/PRE_REGISTRATION.md` section 4.2 before it looked at any
count, validated it against a control that fired correctly, applied it to FOUR rows, and
recorded in its own RESULTS.md section 7 that "the full 337-arm STABLE-LIVE population was not
re-scored under this criterion; that sweep is the obvious successor and is mechanical from
analysis/valid_payload_audit.py".  This script is that sweep and nothing else.

Every decision function is IMPORTED from the committed implementation and called unmodified:

    V0192.index_pass / arm_stats   <- EXP-0192, splits collect_raw.py::sig_of into
                                      (hard-class, observation-hash)
    V0192.record_pass              <- EXP-0192, record-level second pass over raw/**.jsonl
    V0192.classify_row             <- EXP-0192, THE CRITERION (Case A / B / C)
    V0192.db_geom / live_labels / load / sha_files
    DG.payload_of / HARD / CONTAM  <- EXP-0191, via EXP-0192, unmodified

EXP-0192's `main()` is NOT called: it would rewrite EXP-0192's committed outputs.  Nothing
under experiments/EXP-0192-fault-as-movement/ is written by this script.

What this script adds is ONLY:
  * the population -- every field carried by an arm audit.py marked `stable_live`, enumerated
    exactly as EXP-0191/analysis/detection_gate.py builds its `slcheck` (lines 417-431);
  * bookkeeping: control checks R1/R2, the projected label counts, the output files.

Outputs (analysis/):
  population_audit.json   -- every STABLE-LIVE field: arms, cases, fault cells, distinct VALID
                             payloads, distinct legal values, case
  reclassify.json         -- ONLY the emitter-grade Case C rows, flat <mnemonic>.<field> with
                             start/width.  Written only if that set is non-empty.
"""
import collections
import importlib.util
import json
import os
import sys

# Importing another experiment's committed script must not leave a __pycache__ behind in
# its directory: EXP-0192's and EXP-0191's analysis/ trees are read-only to this experiment.
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
ROOT = os.path.abspath(os.path.join(EXPDIR, ".."))

E0190 = os.path.join(EXPDIR, "EXP-0190-indexer-refilter")
E0191 = os.path.join(EXPDIR, "EXP-0191-detection-gate")
E0192 = os.path.join(EXPDIR, "EXP-0192-fault-as-movement")

# ---- import EXP-0192's implementation, unmodified.  Its module-level code also imports
# ---- EXP-0191's payload_of/HARD/CONTAM and re-asserts the HARD-set drift check.
_spec = importlib.util.spec_from_file_location(
    "valid_payload_audit", os.path.join(E0192, "analysis", "valid_payload_audit.py"))
V0192 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V0192)

DG = V0192.DG
HARD = V0192.HARD
CONTAM = V0192.CONTAM
EMIT_OK = V0192.EMIT_OK
CONTROLS = list(V0192.CONTROLS)          # ["call.b5"] -- R1
E0192_ROWS = list(V0192.ROWS)            # the four rows EXP-0192 examined -- R2

# Sanity: the imported module must still resolve the shared corpus, not this experiment's dir.
assert V0192.EXPDIR == EXPDIR, "EXP-0192 module resolved a different experiments/ root"
assert V0192.ROOT == ROOT, "EXP-0192 module resolved a different repo root"

# ---- PRE_REGISTRATION section 5: expectations recorded BEFORE this ran -----
R1_EXPECT = {
    "row": "call.b5",
    "case": "A",
    "arms": {
        "EXP-0179-g17p-call|C1_flat/idx15|B5":
            {"n_cases": 768, "n_fault_cells": 384, "V_valid_payloads": 3,
             "V_all_signatures": 4, "L_legal_values": 128},
        "EXP-0179-g17p-call|C2_nested/idx7|B5":
            {"n_cases": 768, "n_fault_cells": 416, "V_valid_payloads": 4,
             "V_all_signatures": 5, "L_legal_values": 128},
        "EXP-0179-g17p-call|S_kchain_compiled|S":
            {"n_cases": 512, "n_fault_cells": 320, "V_valid_payloads": 2,
             "V_all_signatures": 3, "L_legal_values": 96},
    },
}
R2_EXPECT = {"ret.linkmode": "A", "ret_luse.linkmode": "C",
             "jump_cond.offset": "C", "n3_sample_read.tail": "C"}


def resolver():
    """EXP-0191/analysis/detection_gate.py::resolver(), same behaviour."""
    dirs = sorted(d for d in os.listdir(EXPDIR)
                  if os.path.isdir(os.path.join(EXPDIR, d)))

    def rd(eid):
        if eid in dirs:
            return eid
        c = [d for d in dirs if d.startswith(eid + "-")]
        return c[0] if len(c) == 1 else eid
    return rd


def stable_live_population(audit, rd):
    """PRE_REGISTRATION section 2.  Same enumeration as detection_gate.py's `slcheck`."""
    arms = collections.defaultdict(list)
    for k, r in sorted(audit.items()):
        for eid, ex in (r.get("per_experiment") or {}).items():
            for armkey, v in ex.items():
                if v.get("stable_live"):
                    arms["%s|%s" % (rd(eid), armkey)].append(k)
    return {a: sorted(set(fs)) for a, fs in sorted(arms.items())}


def emittable_set(db, labels_of):
    """tools/agx-isa/validate_labels.py's emittable rule, over a label lookup function.

    `labels_of(mnemonic, fieldname) -> label`, `labels_of(mnemonic, None) -> _instruction
    label`.  Reproduced here ONLY to project a count without editing validation.json; it
    decides nothing about the criterion."""
    out = []
    for ins in db["instructions"]:
        m = ins["mnemonic"]
        fields = ins.get("fields", [])
        all_emit = True
        for f in fields:
            if labels_of(m, f["name"]) not in EMIT_OK:
                all_emit = False
        instlab, instnote = labels_of(m, None), labels_of(m, "_note")
        if not fields:
            all_emit = instlab in EMIT_OK
        if "EMITTABLE VETO" in (instnote or ""):
            all_emit = False
        if instlab not in EMIT_OK:
            all_emit = False
        if all_emit:
            out.append(m)
    return sorted(out)


def project_counts(val, db, withheld):
    """Label counts now, and if `withheld` were moved to `untested`.  Bookkeeping only."""
    def mk(drop):
        def labels_of(m, fn):
            e = val["instructions"].get(m) or {}
            if fn is None:
                return ((e.get("_instruction") or {}).get("label"))
            if fn == "_note":
                return ((e.get("_instruction") or {}).get("note") or "")
            if "%s.%s" % (m, fn) in drop:
                return "untested"
            return (e.get(fn) or {}).get("label")
        return labels_of

    n_fields = 0
    n_emit_now = 0
    for ins in db["instructions"]:
        for f in ins.get("fields", []):
            n_fields += 1
            lab = ((val["instructions"].get(ins["mnemonic"]) or {})
                   .get(f["name"]) or {}).get("label")
            if lab in EMIT_OK:
                n_emit_now += 1
    dw = {i["mnemonic"] for i in db["instructions"]
          if i.get("emitter_role") == "data-word"}
    now = emittable_set(db, mk(set()))
    after = emittable_set(db, mk(set(withheld)))
    now_rel = [m for m in now if m not in dw]
    after_rel = [m for m in after if m not in dw]
    n_rel = len([i for i in db["instructions"]
                 if i.get("emitter_role") != "data-word"])
    return {
        "total_fields": n_fields,
        "emitter_grade_fields_now": n_emit_now,
        "emitter_grade_fields_after": n_emit_now - len(withheld),
        "emitter_relevant_instructions": n_rel,
        "emittable_now": len(now_rel),
        "emittable_after": len(after_rel),
        "emittable_lost": sorted(set(now_rel) - set(after_rel)),
        "headline_now": "%d of %d emittable, %d of %d emitter-grade fields"
                        % (len(now_rel), n_rel, n_emit_now, n_fields),
        "headline_after": "%d of %d emittable, %d of %d emitter-grade fields"
                          % (len(after_rel), n_rel,
                             n_emit_now - len(withheld), n_fields),
    }


def main():
    idx, audit, val, db, gate = V0192.load()
    geom = V0192.db_geom(db)
    labels = V0192.live_labels(val)
    rd = resolver()

    # ---- population (PRE_REGISTRATION section 2) ---------------------------
    sl_arms = stable_live_population(audit, rd)
    P = sorted({f for fs in sl_arms.values() for f in fs})
    n_exp = len({a.split("|", 1)[0] for a in sl_arms})
    sys.stderr.write("population: %d STABLE-LIVE arms, %d fields, %d experiments\n"
                     % (len(sl_arms), len(P), n_exp))

    slkey = "stable_live_arms_with_fewer_than_2_distinct_valid_payloads"
    seven = (gate.get(slkey)
             or gate.get("_meta", {}).get("post_hoc_not_pre_registered", {}).get(slkey)
             or {})
    if not seven:
        for v in gate.values():
            if isinstance(v, dict) and slkey in v:
                seven = v[slkey]
                break
    seven_arms = seven.get("arms", seven) if isinstance(seven, dict) else {}

    scope = sorted(set(P) | set(E0192_ROWS))
    sys.stderr.write("scope rows: %d (population %d + EXP-0192 rows)\n"
                     % (len(scope), len(P)))

    # ---- 1. index-level pass, EXP-0192's own function ----------------------
    per_row = {}
    for i, row in enumerate(scope + CONTROLS):
        per_row[row] = V0192.index_pass(idx, row)
        if (i + 1) % 100 == 0:
            sys.stderr.write("  index_pass %d/%d\n" % (i + 1, len(scope) + len(CONTROLS)))
    sys.stderr.write("index_pass done\n")

    # ---- 2. record-level second pass, EXP-0192's own function --------------
    # `want` is built exactly as EXP-0192's main() builds it.
    want = set()
    for row, arms in per_row.items():
        for armk in arms:
            e, _, a = armk.partition("|")
            want.add((e, a))
    for armk in (seven_arms if isinstance(seven_arms, dict) else {}):
        e, _, a = armk.partition("|")
        want.add((e, a))
    sys.stderr.write("record_pass over %d arms in %d experiments ...\n"
                     % (len(want), len({e for e, _ in want})))
    rec = V0192.record_pass(want)
    sys.stderr.write("record_pass done (%d arms with records)\n" % len(rec))

    # ---- 3. the criterion, EXP-0192's own function, unmodified -------------
    verdicts = {}
    for row in scope + CONTROLS:
        arms = per_row[row]
        case, why = V0192.classify_row(arms, rec, row)
        au = audit.get(row, {})
        verdicts[row] = {
            "live_label": (labels.get(row) or {}).get(
                "label", "(absent from validation.json)"),
            "live_range": (labels.get(row) or {}).get("range"),
            "snapshot_label": au.get("label"),
            "bucket": au.get("bucket"),
            "moved_total": au.get("moved_total"),
            "stable_live_arms": sorted(a for a, fs in sl_arms.items() if row in fs),
            "target": au.get("target"),
            "evidence": au.get("evidence"),
            "n_attributing_arms": len(arms),
            "arms": arms,
            "record_level": {k: v.get(row) for k, v in rec.items() if row in v},
            "cross_run": {k: v.get("cross_run")
                          for ex in au.get("per_experiment", {}).values()
                          for k, v in ex.items()},
            "case": case,
            "verdict": {"A": "STANDS", "B": "STANDS (legality-only)",
                        "C": "WITHHOLD"}.get(case, case),
            "reason": why,
            "geometry": geom.get(row),
            "in_population": row in P,
            "is_control": row in CONTROLS,
            "was_examined_by_EXP_0192": row in E0192_ROWS,
        }

    # ---- 4. controls -------------------------------------------------------
    r1 = {"expected": R1_EXPECT, "observed_case": verdicts["call.b5"]["case"],
          "observed_arms": {k: {kk: v[kk] for kk in
                                ("n_cases", "n_fault_cells", "V_valid_payloads",
                                 "V_all_signatures", "L_legal_values")}
                            for k, v in verdicts["call.b5"]["arms"].items()}}
    r1_case_ok = r1["observed_case"] == R1_EXPECT["case"]
    r1_arms_ok = all(
        r1["observed_arms"].get(a, {}).get(k) == v
        for a, exp in R1_EXPECT["arms"].items() for k, v in exp.items())
    r1["case_matches"] = r1_case_ok
    r1["arms_match"] = r1_arms_ok
    r1["V_observed"] = [r1["observed_arms"].get(a, {}).get("V_valid_payloads")
                        for a in R1_EXPECT["arms"]]
    r1["pass"] = bool(r1_case_ok and r1_arms_ok)

    r2 = {r: {"expected": c, "observed": verdicts[r]["case"],
              "agree": verdicts[r]["case"] == c} for r, c in R2_EXPECT.items()}
    r2_pass = all(v["agree"] for v in r2.values())

    pipeline_ok = r1["pass"] and r2_pass

    # ---- 5. verdict sets ---------------------------------------------------
    caseA = sorted(r for r in scope if verdicts[r]["case"] == "A")
    caseB = sorted(r for r in scope if verdicts[r]["case"] == "B")
    caseC = sorted(r for r in scope if verdicts[r]["case"] == "C")
    unver = sorted(r for r in scope if verdicts[r]["case"] == "UNVERIFIABLE-HERE")

    # EXP-0192's own withholding filter, unchanged.
    withhold = {r: verdicts[r] for r in caseC
                if verdicts[r]["live_label"] in EMIT_OK and r not in CONTROLS}
    already = sorted(r for r in caseC if r in E0192_ROWS)
    newC = sorted(r for r in caseC if r not in E0192_ROWS)

    proj = project_counts(val, db, sorted(withhold)) if pipeline_ok else None

    out = {
        "_meta": {
            "experiment": "EXP-0193-stable-live-sweep",
            "question": ("apply EXP-0192's frozen fault-as-movement criterion to the FULL "
                         "337-arm STABLE-LIVE population -- every field carried by an arm "
                         "audit.py marked stable_live -- and report whether any further row "
                         "fires Case C"),
            "criterion": ("EXP-0192/PRE_REGISTRATION.md section 4.2, INHERITED UNCHANGED. "
                          "EXP-0193 adds no case, tunes no threshold, and calls "
                          "EXP-0192/analysis/valid_payload_audit.py::classify_row directly."),
            "criterion_owner": "EXP-0192-fault-as-movement",
            "repo_revision_at_preregistration":
                "7286bf04c500f726fbe3bf096a166e90b6a34e0f",
            "reused_implementations": [
                "EXP-0192/analysis/valid_payload_audit.py "
                "(index_pass, arm_stats, record_pass, classify_row, db_geom, "
                "live_labels, load, sha_files) -- imported, main() NOT called",
                "EXP-0191/analysis/detection_gate.py::payload_of / HARD / CONTAM "
                "(via EXP-0192, unmodified)",
                "EXP-0190/analysis/collect_raw.py (via work/raw_index.json.gz; its "
                "sig_of signature is split, not recomputed)",
                "EXP-0190/analysis/audit.py (via analysis/audit.json)"],
            "input_hashes": V0192.sha_files([
                "tools/agx-isa/validation.json", "tools/agx-isa/db.json",
                "experiments/EXP-0190-indexer-refilter/work/raw_index.json.gz",
                "experiments/EXP-0190-indexer-refilter/analysis/audit.json",
                "experiments/EXP-0191-detection-gate/analysis/detection_gate.py",
                "experiments/EXP-0191-detection-gate/analysis/gate_results.json",
                "experiments/EXP-0192-fault-as-movement/analysis/valid_payload_audit.py",
                "experiments/EXP-0192-fault-as-movement/analysis/valid_payload_audit.json",
                "experiments/EXP-0192-fault-as-movement/analysis/reclassify.json"]),
            "hard_classes": sorted(HARD),
            "contaminated_outcomes": sorted(CONTAM),
            "controls": CONTROLS,
            "rows_examined_by_EXP_0192": E0192_ROWS,
            "device_contacted": False,
        },
        "population": {
            "definition": ("every <mnemonic>.<field> key of EXP-0190/analysis/audit.json "
                           "for which some per_experiment[eid][arm].stable_live is true; "
                           "same enumeration as EXP-0191 detection_gate.py slcheck"),
            "n_stable_live_arms": len(sl_arms),
            "n_stable_live_arms_committed_by_EXP_0191":
                (seven.get("n_stable_live_arms_checked")
                 if isinstance(seven, dict) else None),
            "n_fields": len(P),
            "n_experiments": n_exp,
            "n_scope_rows_scored": len(scope),
            "arms": sl_arms,
        },
        "controls": {
            "R1_call_b5_positive_control": r1,
            "R2_EXP_0192_rederivation": {"per_row": r2, "pass": r2_pass},
            "pipeline_ok": pipeline_ok,
            "R3_discrimination": {
                "n_case_A": len(caseA), "n_case_B": len(caseB), "n_case_C": len(caseC),
                "both_directions_observed": bool(caseA and caseC)},
            "R4_attribution": {"n_unverifiable_here": len(unver), "rows": unver},
        },
        "summary": {
            "n_rows_examined": len(scope),
            "case_A_stands": caseA,
            "case_B_stands_legality_only": caseB,
            "case_C_all": caseC,
            "case_C_already_withheld_by_EXP_0192": already,
            "case_C_new_in_EXP_0193": newC,
            "case_C_emitter_grade_actionable": sorted(withhold),
            "unverifiable_here": unver,
            "criterion_fired_on_a_new_row": bool(withhold),
            "projected_counts": proj,
        },
        "seven_stable_live_arms_from_EXP_0191": seven,
        "verdicts": verdicts,
    }
    with open(os.path.join(HERE, "population_audit.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True, default=list)
        f.write("\n")

    if not pipeline_ok:
        sys.stderr.write("\n*** CONTROL FAILURE -- PIPELINE BROKEN. "
                         "NO VERDICT IS REPORTED. ***\n")
        sys.stderr.write(json.dumps({"R1": {k: r1[k] for k in
                                            ("pass", "case_matches", "arms_match",
                                             "V_observed", "observed_case")},
                                     "R2": r2}, indent=1))
        sys.stderr.write("\n")
        return 3

    if withhold:
        rc = {"_meta": {
            "experiment": "EXP-0193-stable-live-sweep",
            "trigger": "EXP-0192/PRE_REGISTRATION.md section 4.2 Case C, inherited unchanged",
            "scope": "the full 337-arm STABLE-LIVE population",
            "action": ("RECOMMENDED withholding to `untested`; this experiment edits no "
                       "label. The orchestrator owns validation.json.")}}
        for r, v in sorted(withhold.items()):
            g = geom.get(r) or {}
            rc[r] = {"current_label": v["live_label"],
                     "start": g.get("start"), "width": g.get("width"),
                     "case": "C", "reason": v["reason"],
                     "L_legal_values_max": max(a["L_legal_values"]
                                               for a in v["arms"].values()),
                     "V_valid_payloads_max": max(a["V_valid_payloads"]
                                                 for a in v["arms"].values()),
                     "n_fault_cells": {k: a["n_fault_cells"]
                                       for k, a in v["arms"].items()},
                     "arms": sorted(v["arms"]),
                     "stable_live_arms": v["stable_live_arms"],
                     "target": v["target"], "evidence": v["evidence"],
                     "recommended_note": (
                         "EXP-0193 withheld: the STABLE-LIVE promotion rests only on "
                         "ok<->fault signature transitions. No arm produced two distinct "
                         "VALID observation payloads, while >=2 field values ran legally "
                         "and were indistinguishable -- an inertness observation that "
                         "collect_raw.py::sig_of re-scored as movement. Criterion "
                         "inherited unchanged from EXP-0192. The fault wall itself "
                         "remains a valid legal-set bound.")}
        with open(os.path.join(HERE, "reclassify.json"), "w") as f:
            json.dump(rc, f, indent=1, sort_keys=True)
            f.write("\n")

    print(json.dumps({"population": {k: v for k, v in out["population"].items()
                                     if k != "arms"},
                      "controls": {"R1_pass": r1["pass"], "R1_V": r1["V_observed"],
                                   "R2_pass": r2_pass,
                                   "R3": out["controls"]["R3_discrimination"],
                                   "R4_unverifiable": len(unver)},
                      "summary": {k: v for k, v in out["summary"].items()
                                  if k != "case_A_stands"}}, indent=1))
    for r in caseC + caseB + unver:
        v = verdicts[r]
        print("%-28s %-20s case=%s  V=%s L=%s faults=%s arms=%d" % (
            r, v["live_label"], v["case"],
            [a["V_valid_payloads"] for a in v["arms"].values()],
            [a["L_legal_values"] for a in v["arms"].values()],
            [a["n_fault_cells"] for a in v["arms"].values()],
            v["n_attributing_arms"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
