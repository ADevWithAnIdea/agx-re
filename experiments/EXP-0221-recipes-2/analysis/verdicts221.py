#!/usr/bin/env python3
"""EXP-0221 six-axis field verdicts.

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 2: one label must no longer carry
four conclusions.  Every field gets an INDEPENDENT status on encoding geometry,
liveness, semantics, compiler recipe, target, and reproducibility, and a result
on one axis never implies a result on another.

This file writes `analysis/field_verdicts.json`.  It proposes NO label change:
`tools/agx-isa/validation.json` is the orchestrator's, and dashboard 4 takes
`max(stored, live)` unmeasured fields, so `device_load` and `stop` cannot move
there on this experiment's evidence alone however strong it is.  What is
produced here is the evidence a promotion would need, plus the exact reason each
field is or is not ready.

Reads only committed analysis output.  Contacts no device.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)


def main():
    cov = json.load(open(os.path.join(HERE, "coverage.json")))
    g = json.load(open(os.path.join(HERE, "gates.json")))
    out = {}
    repro_ok = (g["gate_E"]["program_hash_disagreements"] == 0
                and g["gate_E"]["bucket_disagreements"] == 0)
    for arm, d in sorted(cov.items()):
        if arm.startswith("_"):
            continue
        key = "%s.%s" % (d["instruction"], d["field"])
        dense = (d["distinct_requested_values"] == d["encodable_domain"])
        sem = d["exact"] + d["not_exact"]
        oracle_limited = not d.get("exact_is_acceptance", True)
        v = {
            "arm": arm,
            "geometry": ("geometry-mapped" if d["distinct_actual_encodings"]
                         >= d["distinct_requested_values"] else "ledger-verified"),
            "liveness": ("decided-one-carrier" if sem else "carrier-undecidable"),
            "semantics": ("semantically-mapped"
                          if (sem and d["not_exact"] == 0 and dense
                              and not oracle_limited)
                          else ("bounded-map" if sem else "unknown")),
            "exact_is_acceptance": not oracle_limited,
            "recipe": "generated-no-donor",
            "target": "G17P-direct-repeated",
            "reproducibility": ("independently-confirmed" if repro_ok
                                else "auditable"),
            "range": "%d of %d dispatched (%s); %d accepted, %d not accepted, "
                     "%d faulted or hung"
                     % (d["distinct_requested_values"], d["encodable_domain"],
                        "DENSE" if dense else "SAMPLED", d["exact"],
                        d["not_exact"], d["faults_or_hangs"]),
            "accepted_G17P": d["accepted_G17P"],
            "cross_target": {
                "m4_accepted_count": d.get("m4_accepted_count"),
                "g17p_accepted_count": d.get("g17p_accepted_count"),
                "identical": d.get("H5_cross_target_identical"),
                "accepted_on_M4_not_G17P": d.get("accepted_on_M4_not_G17P"),
                "accepted_on_G17P_not_M4": d.get("accepted_on_G17P_not_M4")},
            "evidence": ["EXP-0221"],
            "note": ("" if not oracle_limited else
                     "ORACLE-LIMITED: %d of %d cases are `unpredicted` because "
                     "this experiment's frozen host model was narrower than the "
                     "field's real behaviour.  The `accepted` count here is "
                     "ORACLE COVERAGE, not an acceptance measurement, and must "
                     "not be read as one."
                     % (d.get("unpredicted", 0), d["dispatched"])),
        }
        out[key] = v
    out["_db_defects"] = {
        "device_store.extmode": {
            "current_model": "extmode = 2*R (EXP-0090 finding_5 / EXP-0141 H10), "
                             "bit 0 live but unexplained",
            "measured_here": "extmode is a 16-BIT HALF-REGISTER INDEX.  A 32-bit "
                             "store reads the 32 bits starting at half index "
                             "`extmode`: even 2R stores r(R) exactly; odd 2R+1 "
                             "stores a word whose LOW half is r(R)'s HIGH half.  "
                             "The register index WRAPS MOD 96 -- extmode 192..255 "
                             "reproduce 0..63 byte for byte, and extmode 191 reads "
                             "r95's high half with r0's low half above it.",
            "unresolved": "the TOP half of an odd-index read follows the next "
                          "half-register for mov_imm-written registers and reads "
                          "ZERO for device_load-written ones.  Operand provenance, "
                          "not an encoding bit -- section 6's required dimension.",
            "evidence": "raw/g17p-20260831-run01 arm D3-extmode, target16 field"},
        "device_store.index_reg / device_load.index_reg": {
            "measured_here": "bit 7 is IGNORED for register selection AND for the "
                             "store's index-register release side effect: index_reg "
                             "128+k behaves as r(k) in both.  EXP-0141 recorded the "
                             "mirror for the LOAD; this experiment's own frozen "
                             "oracle did not model it, which is why 117 cases are "
                             "scored as Gate C failures rather than retro-edited.",
            "evidence": "raw/g17p-20260831-run01 arms D4-index_reg, L4-index_reg"},
        "stop.reserved": {
            "current_label": "untested",
            "measured_here": "inert over 1,178 structured values INCLUDING the six "
                             "control-flow-leader bodies EXP-0206 recorded as "
                             "faulting: on G17P in this carrier they do not fault "
                             "and the program still halts.  Inertness is measured "
                             "against a POST-STOP TRIPWIRE store, whose paired "
                             "pre-stop control fires.",
            "caveat": "1,178 of 16,777,216 is a SAMPLE, not a sweep.",
            "evidence": "raw/g17p-20260831-run01 arm S1-stop.reserved"},
        "device_store.space bit 1 (threadgroup)": {
            "measured_here": "EXP-0220's four faults are a CARRIER property: with a "
                             "static tile declared the same encodings execute; "
                             "without one they fault.  A generated threadgroup store "
                             "at store idx_off k is read back by a generated "
                             "threadgroup load at load idx_off 4k and at no other "
                             "offset.",
            "unresolved": "the round trip is not shape-independent, so this is NOT "
                          "a recipe and device_store stays generated-no-donor.",
            "evidence": "raw/g17p-20260831-{run01,run02,notg} arms T0..T4, D2-space"},
    }
    json.dump(out, open(os.path.join(HERE, "field_verdicts.json"), "w"),
              indent=1, sort_keys=True)
    for k, v in sorted(out.items()):
        if k.startswith("_"):
            continue
        print("%-28s %-20s %-20s %s" % (k, v["semantics"], v["liveness"],
                                        v["range"][:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
