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


# The exact parameter interval actually exercised, in the field's own units, with
# the carrier composition that bounds it. `docs/evidence-classification.md`: "the
# range is the claim's real scope; an implementer may not extrapolate past it."
RANGES = {
    "if_push.scope":
        "0..255 dense (all 256 values) at FOUR occurrences: three with "
        "scope_kind 0x1a (LOOP-ITERATION, the region kind EXP-0184 could not "
        "reach) and one with 0x25, across three loop shapes. LIVE at the single "
        "occurrence whose compiled value is 0x56; inert over all 256 at the "
        "three whose compiled value is 0x54.",
    "pop_reconverge.scope":
        "0..255 dense (all 256 values) at THREE occurrence classes on two "
        "carriers: loop-body pop (scope_kind 0x02, compiled 0x04), "
        "guard/outermost pop (scope_kind 0x01, compiled 0x04) and "
        "call-reconvergence pop (scope_kind 0x02, compiled 0x24 -- the OTHER "
        "documented bank, compiler-emitted). Inert in that envelope.",
    "pop_reconverge.reserved":
        "52 of 65,536 values (FIELD-SWEEP-PROTOCOL section 3 sampling for w > 8: "
        "boundaries, every single-bit value, every single-bit hole, 23 "
        "asymmetric interior samples) at three occurrences on three carriers. "
        "LIVE at the lane-divergent carrier: the LOW BYTE (bits 32..39) must be "
        "zero; the high byte is inert over the 9 high-byte values tested.",
    "call.tail":
        "0..255 dense (all 256 values) at three call sites with three DIFFERENT "
        "callee structures (leaf; non-leaf that itself calls two leaves; atomic "
        "RMW callee returning through a real ret_luse). All three share ONE "
        "read-back plan. Inert in that envelope.",
    "ret.scoreboard":
        "0..255 dense (all 256 values) at FOUR occurrences spanning the "
        "memory/execution-ORDERING dimension: nothing outstanding at the return; "
        "a load inside the callee; a store->load hazard spanning the return; a "
        "non-leaf return with a saved link. Inert in that envelope. NOT tested: "
        "any multi-invocation ordering litmus.",
    "ret_luse.linkmode":
        "0..255 dense (all 256 values) at THREE occurrences: a REAL "
        "compiler-emitted `8f 12 56 00`, a synthesized leaf return, and a "
        "synthesized NON-LEAF return. Accepted set is `v & 3 == 2` (64 of 256) at "
        "all three; bit 4 (0x10) separates two distinct valid payloads at the "
        "non-leaf occurrence only.",
    "stop.reserved":
        "73 of 16,777,216 values (protocol section 3 sampling for w > 8) at the "
        "FINAL stop of three structurally different carriers. Inert in that "
        "envelope, with a termination-dimension positive control that FIRES "
        "(byte 0 -> 0x0f or 0x8f faults; six other byte-0 values are harmless).",
    "stop.reserved@synth_mid":
        "73 of 16,777,216 values at a CONSTRUCTED mid-program stop on two "
        "carriers (built over the optional 4-byte frame marker). The program "
        "terminates there in 292 of 292 cases; the 24-bit body is inert in that "
        "envelope.",
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
            "range": RANGES.get(key),
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
                "cross_run_agreement_per_arm": f.get("agreement_per_arm"),
                "agreement_pair_per_arm": f.get("agreement_pair_per_arm"),
                "V_per_arm": f.get("V_per_arm"),
                "L_per_arm": f.get("L_per_arm"),
                "moved_per_arm": f.get("moved_per_arm"),
                "hard_per_arm": f.get("hard_per_arm"),
                "foreign_cascade_window_cases_rescored_as_measurement_failure":
                    f.get("foreign_cascade_window_cases"),
            },
            "hard_outcomes_counted_separately": f["hard_total"],
            "semantic_models": f["semantic_models"],
            "surviving_models": surviving,
            "arms_promoted": f["arms_promoted"],
            "arms_inert": f["arms_inert"],
            "arms_unresolved": f["arms_unresolved"],
            "note": "",
        }

    # FIELD-SWEEP-PROTOCOL section 6: "If a sweep shows the modelled boundaries do
    # not match the hardware -- a `field` that is really two, a live byte db.json
    # does not expose -- that is a first-class result. Record the corrected model
    # under `db_defects`. Do NOT edit db.json; the orchestrator owns it."
    out["db_defects"] = {
        "MISSING-DESCRIPTOR-non-leaf-epilogue": {
            "what": "The 6-byte word `ef 02 54 00 00 50` has NO descriptor in the "
                    "pinned db.json. It is emitted by our own compiler at the end "
                    "of EVERY non-leaf callee, immediately before the non-leaf "
                    "return `8f 12 54 00`, in four independent regions "
                    "(c_mid, d_mid, d_out, s_big).",
            "consequence": "A linear tokenizer walk dies at that word, so the ONLY "
                           "occurrences in this corpus carrying `ret.linkmode == "
                           "0x12` are invisible to it. That is exactly the value "
                           "the leaf-only carriers of the WITHDRAWN "
                           "`ret_luse.linkmode` measurement could never reach: the "
                           "db gap and the evidence gap are the same gap.",
            "evidence": "raw/prefreeze/census.json (`gaps`), "
                        "harness/locate206.py::walk_resync",
            "recommendation": "add a descriptor; until then any experiment locating "
                              "instructions by linear walk silently loses every "
                              "non-leaf epilogue and the return that follows it",
        },
        "pop_reconverge.reserved-is-two-fields": {
            "what": "db.json models bits 32..47 as ONE 16-bit `reserved` field of "
                    "type `mod`. The sweep separates them: byte+4 (bits 32..39) is "
                    "LOAD-BEARING and byte+5 (bits 40..47) is inert over the tested "
                    "set.",
            "measured": "at cf_ifnl+184 every sampled value whose LOW BYTE is zero "
                        "is correct and every value with a non-zero low byte gives "
                        "a different, deterministic payload -- a clean separation "
                        "with no exceptions in the sampled set",
            "evidence": "analysis/report_tables.py, "
                        "raw/g17p_20260830_run03/sweep.jsonl",
            "recommendation": "split into `reserved_lo` (byte+4, must be 0 on the "
                              "tested envelope) and `reserved_hi` (byte+5, inert "
                              "over 8 tested values); the name `reserved` is wrong "
                              "for the low byte",
        },
        "ret.linkmode-accepted-set": {
            "what": "EXP-0156 recorded the accepted set of `ret`/`ret_luse` byte+1 "
                    "as `v & 7 == 4`. On G17P it is `v & 3 == 2` (64 of 256).",
            "measured": "identical accepted sets at four independent occurrences "
                        "(cl_atomic real ret_luse, cl_leaf leaf ret, cl_chain "
                        "non-leaf ret, and the ret.linkmode control at cl_chain), "
                        "and the compiler itself emits 0x02 and 0x12 -- both of "
                        "which have `v & 7 == 2`, so the old rule is refuted by our "
                        "own compiled bytes before any sweep",
            "evidence": "raw/g17p_20260830_run03 and run04 sweep.jsonl",
            "recommendation": "record the accepted set as `v & 3 == 2` and bit 4 "
                              "(0x10) as the non-leaf restore-link flag; the enum "
                              "{2 leaf, 18 nonleaf_restore_link, 4/5 cf_merge} is "
                              "wrong about 4 and 5, which FAULT here",
        },
        "stop-final-word-is-executed": {
            "what": "db.json says the `stop` word is `NOT a strictly-enforced "
                    "terminator` and that `corrupting any of it is a no-op` "
                    "(EXP-0003/EXP-0010). Bounded here: the 24-bit BODY is inert "
                    "over 73 sampled values on three carriers, but replacing "
                    "BYTE 0 with a control-flow leader (0x0f or 0x8f) FAULTS "
                    "reproducibly on all three carriers and in both runs, while "
                    "0x00/0x01/0x0c/0x0d/0x2e/0xff are harmless.",
            "consequence": "the final word IS fetched and executed; most opcodes "
                           "with an all-zero body happen to be harmless, and a "
                           "branch/return leader is not. And a MID-PROGRAM `stop` "
                           "genuinely terminates: synthesized over the optional "
                           "4-byte frame marker it leaves the sentinel written and "
                           "all 32 value words still POISON.",
            "evidence": "CTRL:byte0@* and stop.reserved@synth_mid@* arms",
            "recommendation": "keep `emit 0x000000` as the driver rule, but drop "
                              "`corrupting any of it is a no-op` -- it is only true "
                              "for the byte values previously tried",
        },
        "call.b6-bit1-not-universally-required": {
            "what": "EXP-0179 arm S concluded `call.b6` bit 1 is load-bearing and "
                    "`must be set`, giving an encodable range of 128. Our own "
                    "compiler emits b6 = 0x54 (bit 1 CLEAR) for both calls inside "
                    "the non-leaf callee `c_mid`, and 0x56 (bit 1 SET) for the call "
                    "in `_agc.main`.",
            "measured": "the b6 control accepts values with bit 1 clear at "
                        "cl_leaf (0x04, 0x08, 0x24 are all correct) and is "
                        "COMPLETELY inert over all 16 sampled values at cl_atomic",
            "evidence": "raw/prefreeze/census.json; CTRL:b6@* arms",
            "recommendation": "the `bit 1 must be set` rule is carrier-dependent, "
                              "not universal; re-scope it before an emitter relies "
                              "on it",
        },
    }

    p = os.path.join(HERE, "field_verdicts.json")
    with open(p, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("wrote %s" % p)
    for k, v in sorted(out.items()):
        if k.startswith("_") or k == "db_defects":
            continue
        print("%-34s %-20s %s  V=%s L=%s hard=%s surviving=%s"
              % (k, v["label"], v["verdict"],
                 v["counts"]["distinct_valid_payloads_max_per_arm"],
                 v["counts"]["legal_values_total"],
                 v["hard_outcomes_counted_separately"], v["surviving_models"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
