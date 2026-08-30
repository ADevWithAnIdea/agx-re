#!/usr/bin/env python3
"""EXP-0206 verdict emitter -- turns `analysis/gate206.json` (which is itself
recomputed from raw on every invocation) into `analysis/field_verdicts.json` in
the shape the dispatch and `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 2
require.

  python3 analysis/emit_verdicts.py           # after verdicts206.py has run

Per field, keyed `<mnemonic>.<field>`:

  label      one of the EIGHT labels of docs/evidence-classification.md, and
             nothing else. It is CAPPED BY THE SEMANTICS AXIS: a field with
             `sem_checked == 0` or with no surviving model is never proposed above
             `corpus-correlation`, whatever its liveness looks like.
  verdict    the six independent axes -- encoding geometry, liveness, semantics,
             compiler recipe, target, reproducibility -- which must never imply
             one another.
  counts     exact numerators AND denominators. Never a percentage alone.
             Includes, per the dispatch: the number of DISTINCT VALID PAYLOADS and
             the number of LEGAL VALUES, since that is the ratio the audit applies.
  hard       fault / hang / invalid / measurement_failure, counted SEPARATELY from
             valid payloads. A GPU fault is never evidence of a semantic.
  start/width/range/target/evidence/note as the dispatch specifies.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))

import targets206 as T          # noqa: E402

# The legacy label is capped by the semantics axis (PRE_REGISTRATION_A2 section A2.6).
LEGACY = {
    "PROMOTED_SEMANTIC": "hardware-run",
    "PROMOTED_LIVE_ONLY": "corpus-correlation",
    "INERT_CONFIRMED": "hardware-run",
    "UNRESOLVED": "untested",
}


def main():
    gate = json.load(open(os.path.join(HERE, "gate206.json")))
    arms = gate["arms"]
    out = {
        "_experiment": "EXP-0206",
        "_target": "G17P (Apple A18 Pro, applegpu_g17p, AGXAcceleratorG17P, 5 cores, "
                   "macOS 26.6 build 25G5043d, Metal family Apple9)",
        "_gate": "PRE_REGISTRATION.md section 7 + PRE_REGISTRATION_A2.md Gates A/B/C/E; "
                 "recomputed from raw by analysis/verdicts206.py, which refuses to run "
                 "if its five-case self-test fails",
        "_runs": gate["_runs"],
        "_concurrency": gate["_concurrency"],
        "_label_rule": "the legacy label is CAPPED BY THE SEMANTICS AXIS: no field "
                       "with sem_checked == 0 or with no surviving pre-registered "
                       "model is proposed above `corpus-correlation`, whatever its "
                       "liveness looks like (RE_EXPERIMENT_PROCESS_CORRECTIONS "
                       "section 3 Gate C).",
    }

    for key, f in sorted(gate["fields"].items()):
        t = T.BY_KEY[key]
        mnem, field = t["mnemonic"], t["field"]
        vkey = "%s.%s" % (mnem, field)
        if key.endswith("@synth_mid"):
            vkey = "%s.%s@synth_mid" % (mnem, field)
        start, width = None, None
        for a, st in arms.items():
            if st.get("key") == key and st.get("role") == "target":
                start = st.get("start_hint")
        # start/width come from the pinned db via the arm records in raw
        rec = next((st for a, st in arms.items()
                    if st.get("key") == key and st.get("role") == "target"), {})
        axes_per_arm = f.get("axes_per_arm", {})
        live = [v["liveness"] for v in axes_per_arm.values()]
        sem = [v["semantics"] for v in axes_per_arm.values()]
        promoted = bool(f["arms_promoted"])
        all_inert = bool(f["arms_inert"]) and not f["arms_unresolved"]
        surviving = f["surviving_models"]
        if promoted and surviving:
            state = "PROMOTED_SEMANTIC"
        elif promoted:
            state = "PROMOTED_LIVE_ONLY"
        elif all_inert and surviving:
            state = "INERT_CONFIRMED"
        else:
            state = "UNRESOLVED"
        out[vkey] = {
            "label": LEGACY[state],
            "verdict": state,
            "axes": {
                "encoding_geometry": sorted({v["encoding_geometry"]
                                             for v in axes_per_arm.values()}),
                "liveness": sorted(set(live)),
                "semantics": sorted(set(sem)),
                "compiler_recipe": sorted({v["compiler_recipe"]
                                           for v in axes_per_arm.values()}),
                "target": "G17P-direct",
                "reproducibility": sorted({v["reproducibility"]
                                           for v in axes_per_arm.values()}),
            },
            "target": "G17P",
            "evidence": ["EXP-0206"],
            "start": rec.get("start"),
            "width": rec.get("width"),
            "range": None,               # filled by RESULTS.md authoring step
            "counts": {
                "n_arms": f["n_arms"],
                "distinct_valid_payloads_max_per_arm": f["V_max_per_arm"],
                "legal_values_total": f["L_total"],
                "ledger_ok": f["ledger_ok_total"],
                "ledger_bad": f["ledger_bad_total"],
                "distinct_actual_encodings_per_arm":
                    f["distinct_actual_encodings_per_arm"],
                "semantic_buckets": f["buckets_total"],
                "contaminated_cases": f["contaminated_cases"],
                "cross_run_agreement_min": f["agreement_min"],
            },
            "hard_outcomes_counted_separately": f["hard_total"],
            "semantic_models": f["semantic_models"],
            "surviving_models": surviving,
            "arms_promoted": f["arms_promoted"],
            "arms_inert": f["arms_inert"],
            "arms_unresolved": f["arms_unresolved"],
            "note": "",
        }

    p = os.path.join(HERE, "field_verdicts.json")
    with open(p, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("wrote %s" % p)
    for k, v in sorted(out.items()):
        if k.startswith("_"):
            continue
        print("%-34s %-20s %s  V=%s L=%s hard=%s surviving=%s"
              % (k, v["label"], v["verdict"],
                 v["counts"]["distinct_valid_payloads_max_per_arm"],
                 v["counts"]["legal_values_total"],
                 v["hard_outcomes_counted_separately"], v["surviving_models"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
