#!/usr/bin/env python3
"""EXP-0221 generated-recipe records -- the artifact dashboard 4 reads.

`tools/agx-isa/promotion_check.py:recipes()` globs every experiment's
`analysis/generated_recipe.json` in sorted order, so a record written here
REPLACES EXP-0220's for the same mnemonic.  That makes writing one an act with
consequences, and the rule this file follows is the one the process demands:

    `n_unmeasured` is the number of COMPILER-SELECTED OPERAND CLASSES OR
    CONTEXTS this generated recipe does NOT cover -- EXP-0220's own definition,
    kept verbatim so the two records mean the same thing -- and it is set from
    what this experiment MEASURED, never from what would look better.

Concretely: `device_store` KEEPS its threadgroup gap and therefore keeps
`generated-no-donor`, because the pilot did not yield a shape-independent
threadgroup recipe (PRE_REGISTRATION section 6.5).  What this experiment closed
is narrower and is recorded as closed: `extmode >= 128`, and nine fields that
were SAMPLED are now swept densely.

Reads only committed raw and the frozen inputs.  Contacts no device.  Changes no
label, no db.json, no doc.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
RUN01 = "g17p-20260831-run01"
RUN02 = "g17p-20260831-run02"


def load(run):
    p = os.path.join(EXP, "raw", run, "sweep.jsonl")
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def main():
    A, B = load(RUN01), load(RUN02)
    cov = json.load(open(os.path.join(HERE, "coverage.json")))
    gates = json.load(open(os.path.join(HERE, "gates.json")))
    census = json.load(open(os.path.join(HERE, "census.json")))
    cen01 = census["runs"][RUN01]

    def fields_for(instr):
        rows = []
        for arm, d in sorted(cov.items()):
            if arm.startswith("_") or d.get("instruction") != instr:
                continue
            rows.append({
                "name": d["field"], "encodable_domain": d["encodable_domain"],
                "dispatched": d["dispatched"],
                "distinct_requested_values": d["distinct_requested_values"],
                "distinct_decoded_from_actual_bytes": d["distinct_actual_encodings"],
                "accepted_on_G17P": d["exact"],
                "not_accepted_on_G17P": d["not_exact"],
                "faults_or_hangs": d["faults_or_hangs"],
                "untested": d["untested"],
                "cross_target_identical_to_M4": d.get("H5_cross_target_identical"),
                "ledger_disagreements": 0,
                "provenance": "RULE or FREE -- never COPIED, never CARRIER",
            })
        return rows

    gapS = [
        "THREADGROUP address space (`space` bit 1).  NOT CLOSED.  With a static "
        "tile declared the encodings no longer fault and a round trip is "
        "reproducible in one program shape, and the store-offset/load-offset law "
        "(load_idx_off == 4 * store_idx_off) held in every pre-registered case -- "
        "but the round trip is NOT shape-independent (a single load with the "
        "identical descriptor does not read it back, and a 3,336-case "
        "single-reader sweep in the disclosed pilot returned zero), so an "
        "implementer cannot emit a threadgroup store from this recipe.  THIS IS "
        "STILL THE ONE GAP THAT KEEPS THE VERDICT AT generated-no-donor.",
        "seven index_reg values (96,97,100,111,112,120,127) fault reproducibly; "
        "they are dispatched in the named hazard arm and pre-registered `corrupt`.",
    ]
    gapL = [
        "the THREADGROUP address space for LOADS, for the same reason as the "
        "store: measured, not emittable from a rule.",
    ]
    gapT = [
        "`stop.reserved` is SAMPLED, not swept: 1,178 structured values of "
        "16,777,216 (all 24 single-bit values and their complements, body byte 0 "
        "dense twice, bytes 1 and 2 dense, and a 128-value deterministic sample).",
    ]

    recs = []
    for mnem, gaps, why in (
        ("device_store", gapS,
         "819-case predecessor extended: every 8-bit descriptor field now swept "
         "DENSELY on G17P against a pre-registered accepted set, extmode 0..255 "
         "against a pre-registered two-part model, and the threadgroup class "
         "characterised but NOT closed"),
        ("device_load", gapL,
         "the four fields with no emitter-grade label plus ld_format, index_reg, "
         "space, elem_size, base_slot, dst_lo, dst_ext9 and ldform_hi11 all swept "
         "densely with a host oracle"),
        ("stop", gapT,
         "the 24-bit body swept over a structured 1,178-value sample against a "
         "POST-STOP TRIPWIRE, with the paired pre-stop control proving the "
         "tripwire fires")):
        prov = cen01["field_emissions_by_provenance"].get(mnem, {})
        recs.append({
            "mnemonic": mnem,
            "experiment": "EXP-0221",
            "target": "G17P (Apple A18 Pro), direct.  Nothing ran on the M4.",
            "in_generated_corpus": True,
            "in_emittable_set": False,
            "can_generate_from_documented_rules_alone": not gaps,
            "donor_fields": {},
            "n_unmeasured": len(gaps),
            "coverage_gaps": gaps,
            "verdict": "CANONICAL-RECIPE-PROVEN" if not gaps
                       else "GENERATED-NO-DONOR",
            "why": why,
            "fields": fields_for(mnem),
            "n_fields": len(fields_for(mnem)),
            "field_emissions_by_provenance_per_run": prov,
            "generator_assemble_calls":
                cen01["assemble_calls_per_mnemonic"].get(mnem, 0),
            "runs": [RUN01, RUN02],
            "raw": ["raw/%s/sweep.jsonl" % RUN01, "raw/%s/sweep.jsonl" % RUN02],
            "gate_A_instruction_rows": gates["gate_A"]["instructions"],
            "gate_A_ledger_disagreements": gates["gate_A"]["hard_disagreements"],
            "gate_D_copied_fields": gates["gate_D"]["copied_fields"],
            "gate_D_carrier_fields": gates["gate_D"]["carrier_fields"],
            "gate_E_program_hash_disagreements":
                gates["gate_E"]["program_hash_disagreements"],
            "gate_E_full_output_digest_disagreements":
                gates["gate_E"]["full_output_digest_disagreements"],
            "gated_cases": sum(1 for c in A if c["predicted_bucket"] != "measure"),
            "gated_cases_passed": sum(1 for c in A if c.get("bucket_ok") is True),
            "gated_cases_failed": sum(1 for c in A if c.get("bucket_ok") is False),
            "semantic_checks": sum(c.get("sem_checked", 0) for c in A),
        })
    doc = {"_meta": {
        "experiment": "EXP-0221-recipes-2",
        "question": "can the three classes EXP-0220 named -- the threadgroup "
                    "address space, device_load's four unlabelled fields, and "
                    "stop's 24-bit body -- be GENERATED and predicted on G17P "
                    "with zero donor fields",
        "n_unmeasured_MEANS": "the number of COMPILER-SELECTED OPERAND CLASSES OR "
                              "CONTEXTS this generated recipe does NOT cover; "
                              "EXP-0220's definition, kept verbatim.  It is NOT a "
                              "field-label count: RE_EXPERIMENT_PROCESS_CORRECTIONS "
                              "section 2 says field labels alone are not an "
                              "emittability proof.",
        "scope": "records ONLY for the three mnemonics this experiment generated "
                 "and gated.  No other mnemonic's record is touched and no label "
                 "anywhere is changed.",
        "supersedes_note": "these records replace EXP-0220's for the same three "
                           "mnemonics in promotion_check.recipes() (sorted glob "
                           "order).  device_store and device_load KEEP the same "
                           "verdict; `stop` moves DOWN from EXP-0173's stored "
                           "n_unmeasured = 0 to 1, because its 24-bit body is "
                           "sampled at 1,178 of 16,777,216 values and a stored 0 "
                           "asserted a completeness nobody measured.",
        "census": {"program_hash_mismatches":
                   len(cen01["program_hash_mismatches"]),
                   "total_COPIED": cen01["total_COPIED"],
                   "total_CARRIER": cen01["total_CARRIER"],
                   "note": "REBUILT from the frozen authored inputs and asserted "
                           "byte-identical to the programs recorded in raw before "
                           "any provenance tag was counted"},
        "target": "G17P (Apple A18 Pro), direct."},
        "instructions": recs}
    json.dump(doc, open(os.path.join(HERE, "generated_recipe.json"), "w"),
              indent=1, sort_keys=True)
    for r in recs:
        print("%-14s %-22s n_unmeasured=%d donors=%d fields=%d"
              % (r["mnemonic"], r["verdict"], r["n_unmeasured"],
                 len(r["donor_fields"]), r["n_fields"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
