#!/usr/bin/env python3
"""emit_verdicts.py -- EXP-0163: the deliverable, in FIELD-SWEEP-PROTOCOL sec.5 shape.

    python3 analysis/emit_verdicts.py            # after verdicts.py and rules.py

Merges analysis/field_verdicts.json (buckets, per-arm tables, detection power)
with analysis/bit_rules.json (exact per-bit liveness and equivalence classes)
into analysis/field_verdicts_flat.json:

  * a FLAT dict keyed "<mnemonic>.<field>", each value carrying `label`,
    `target`, `evidence`, `range`, `note` -- plus this experiment's additions:
    `bucket`, the exact `rule` and `live_bits`, the arm/carrier that carried the
    verdict, `cross_run_agreement`, and `emitter_guidance`;
  * `_meta` with the runs compared and the label policy;
  * `db_defects`, per FIELD-SWEEP-PROTOCOL sec.6.

LABEL POLICY (stated so a reviewer can disagree with it explicitly):
  LIVE               -> `hardware-run`.  The full 2^w range executed on real
                        hardware; the value->behaviour partition is exact and
                        reproduced across runs.  An emitter can choose the
                        value and get documented behaviour, which is what
                        emitter-grade means.
  INERT-ROBUST       -> `single-template-inference`.  NOT `hardware-run`.
                        `hardware-run` is one of the two labels
                        validate_labels.py counts as EMITTER-GRADE, and
                        emitter-grade asserts that an implementer can CHOOSE the
                        field's value.  For these eleven our own
                        `emitter_guidance` says the opposite -- emit the
                        COMPILER-OBSERVED value -- which is a dependency on
                        Apple's template and is exactly what Definition-of-Done
                        rule 1 forbids ("value generated, not merely decoded
                        from a captured template").  A negative result must not
                        be able to inflate the emittable count.
                        `single-template-inference` states the emitter's real
                        position: we know the value that works because the
                        compiler used it, we have hardware evidence the field is
                        inert across a stated envelope, and we cannot say what
                        it controls.
                        THE MEASUREMENT IS NOT DOWNGRADED, only the claim about
                        what an emitter may do with it: the full strength of the
                        negative lives in `note`, `range`, `inert_arms`
                        (including `proven_live_controls`) and
                        `hardware_evidence` below.
  STILL-UNDERPOWERED -> `untested`.  FIELD-SWEEP-PROTOCOL sec.5: "if a sweep is
                        inconclusive ... do not round up."  The cases are in
                        raw/ and are described, but the field is NOT promoted.
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import arms as AR   # noqa: E402

V = json.load(open(os.path.join(HERE, "field_verdicts.json")))
R = json.load(open(os.path.join(HERE, "bit_rules.json")))
runs = V["runs"]
armspec = {a["id"]: a for a in AR.ARMS}

LABEL = {"LIVE": "hardware-run",
         # NOT hardware-run: see LABEL POLICY in the module docstring.
         # hardware-run is emitter-grade to validate_labels.py, and these eleven
         # tell the emitter to reuse the compiler's value, which is a captured-
         # template dependency.
         "INERT-ROBUST": "single-template-inference",
         "STILL-UNDERPOWERED": "untested"}

# Semantics established BY THIS EXPERIMENT, written only where the observation
# supports them.  Anything not here stays "unknown".
SEMANTICS = {
 "iter_at.loc":
   "bit1 selects the interpolation LOCATION the setup computes: 0 = centroid, "
   "1 = per-sample.  bit0 and bits 2..7 are don't-cares (0x81 behaves exactly "
   "as 0x01, 0x83 exactly as 0x03).  Two equivalence classes of exactly 128 "
   "values each.  Observable ONLY at rasterSampleCount > 1: the identical "
   "program at 1 sample gives 0/256 (carrier `cent1`), because centroid, "
   "sample point and pixel centre are then the same point.  This REFINES "
   "db.json's enum {1: centroid, 3: sample} to a single-bit selector and tells "
   "an emitter which bits are free.",
 "vary_store.hint6":
   "bit4 (0x10) alone determines whether the varying store WORKS: with bit4 set, "
   "all four fragment output channels read back 0.0 on every live arm -- the "
   "whole varying block is lost, not just this one component -- while the "
   "compiler-chosen values (0x48..0x4d across our carriers) have it clear.  "
   "Exactly 128 of 256 values move, on 7 arms across 5 carriers; two "
   "equivalence classes on five of them.  db.json types this byte `mod` with no "
   "semantics; it is not a free hint.",
 "tex_coord_setup.idx":
   "on the byte+4 == 0x42 form (vertex attribute / varying DESTINATION-address "
   "setup) bit7 alone is live: with bit7 clear the ONE varying this occurrence "
   "addresses reads back 0.0 while the other three are untouched, so the byte "
   "selects that store's destination and its top bit must be set for our slot.  "
   "This is the form db.json says carries `idx = dst<<2`; on the byte+4 == 0x00 "
   "float-classify form idx was inert over all 256 values, which is consistent "
   "with the same note.",
 "tex_coord_setup.b8":
   "bit3 alone (plus bit4 on two arms) is live, with the same signature as "
   "idx bit7: setting it zeroes exactly the one varying this occurrence "
   "addresses.  Only on the byte+4 == 0x42 form; inert over all 256 values on "
   "the 0x00 form.",
 "tex_coord_setup.b5":
   "live on BOTH forms.  On the 0x42 destination-address form the classes are: "
   "bit0 set -> the addressed varying reads 0.0; bits 2..5 (b6) clear and bit3 "
   "set -> the varying's VALUE shifts slightly (6.08333 -> 6.0918 / 6.10946), "
   "i.e. a small address/offset perturbation rather than a kill.  4-5 "
   "equivalence classes; 200-240 of 256 values move.",
 "tex_coord_setup.b6":
   "bits 2,3,4,5 are live and must ALL be clear for the store to work: exactly "
   "16 of 256 values (those with (v & 0x3c) == 0) reproduce the baseline; the "
   "other 240 zero the addressed varying.  Two equivalence classes on every "
   "live arm.",
 "simd_shuffle.rsv9":
   "NOT reserved.  On the mode-0x06 rotate / shuffle-and-fill form (which no "
   "EXP-0155 arm emitted) bits 1, 2, 6 and 7 are live: bits 6 and 7 CHANGE THE "
   "RESULT VALUE of the shuffle-and-fill (result word 31 -> 116 -> 256 across "
   "the four combinations, with bit2 giving a further distinct value), while "
   "bit1 suppresses the stores that follow the op.  240-248 of 256 values move; "
   "8-10 equivalence classes.  Inert on the mode-0x00/0x04/0x05 forms.",
}
GUIDE = {
 "iter_at.loc":
   "set bit1 = 0 for centroid, 1 for per-sample; the other seven bits are free "
   "(observed inert over all 256 values on five 4-sample arms).",
 "vary_store.hint6":
   "bit4 MUST be clear or the varying block is lost; emit the compiler-observed "
   "0x48..0x4d pattern and do not set bit4.",
 "tex_coord_setup.idx":
   "on the byte+4 == 0x42 form this is a real destination selector -- do not "
   "treat it as padding; bit7 must match the slot.  On the 0x00 form it was "
   "inert over the full range.",
 "tex_coord_setup.b6":
   "bits 2..5 must be clear on the 0x42 form; only (v & 0x3c) == 0 works.",
 "simd_shuffle.rsv9":
   "on the mode-0x06 rotate/fill form this is an OPERAND, not padding: emit the "
   "compiler-observed value unless you intend to change the fill result.",
}


def rules_for(mn, fn):
    out = {}
    for k, per in R.items():
        arm, f = k.split("|")
        if f != fn or not arm.startswith(mn + "@"):
            continue
        out[arm] = per
    return out


flat = {}
for key, v in sorted(V["fields"].items()):
    mn, fn = key.split(".", 1)
    rr = rules_for(mn, fn)
    bucket = v["bucket"]
    live = v["live_arms"]
    # exact rule, only where it is identical across every run of a live arm
    rule_rows = {}
    for a in live:
        per = rr.get(a)
        if not per:
            continue
        rs = list(per.values())
        agree = len({(tuple(r["moved"]), tuple(r["live_bits"])) for r in rs}) == 1
        rule_rows[a] = {
            "carrier": armspec[a]["carrier"], "stage": armspec[a]["stage"],
            "occ": armspec[a]["occ"],
            "baseline_value": armspec[a]["census_fields"].get(fn),
            "rule": rs[0]["rule"], "live_bits": rs[0]["live_bits"],
            "n_moved_per_run": {rn: per[rn]["n_moved"] for rn in per},
            "n_equivalence_classes": rs[0]["n_equiv_classes"],
            "equivalence_class_sizes": rs[0]["equiv_class_sizes"],
            "cross_run_identical": agree,
        }
    live_bit_union = sorted({b for r in rule_rows.values() for b in r["live_bits"]})
    inert_arm_n = {}
    for a in v["inert_arms"]:
        # For an INERT verdict the load-bearing datum is not just "n values
        # swept" but "and this arm was PROVEN able to see a change" -- so the
        # controls that proved it are carried here, per arm, by name.
        dpa = V["detection_power"].get(a, {})
        ctrls = sorted({c for per in dpa.values()
                        for c in per.get("strict_live_controls", [])})
        inert_arm_n[a] = {
            "carrier": armspec[a]["carrier"], "stage": armspec[a]["stage"],
            "occ": armspec[a]["occ"],
            "baseline_value": armspec[a]["census_fields"].get(fn),
            "values_swept_per_run": {rn: v["arms"][a]["per_run"][rn]["n"] for rn in runs},
            "moved_per_run": {rn: v["arms"][a]["per_run"][rn]["moved"] for rn in runs},
            "faults_per_run": {rn: v["arms"][a]["per_run"][rn]["n_faults"] for rn in runs},
            "n_proven_live_controls_same_instruction": len(ctrls),
            "proven_live_controls": ctrls[:12],
        }
    widths = {"simd_shuffle.cache": 1}
    w = widths.get(key, 8)
    rng = (f"0..{(1 << w) - 1} dense (all {1 << w} values)"
           + (f" x {len(v['inert_arms']) + len(live)} arms" if (v['inert_arms'] or live) else ""))
    if bucket == "LIVE":
        note = ("LIVE: moved the observation on " + str(len(live)) + " arm(s) across "
                + ", ".join(sorted({armspec[a]['carrier'] for a in live}))
                + ". Inert on " + (", ".join(v["inert_carriers"]) or "no other carrier")
                + " -- i.e. the EXP-0155 null was CARRIER-LIMITED, not a property "
                  "of the silicon.")
    elif bucket == "INERT-ROBUST":
        note = ("INERT-ROBUST over the stated envelope: every value executed on "
                + str(len(v["inert_arms"])) + " arms across "
                + str(len(v["inert_carriers"])) + " structurally different carriers ("
                + ", ".join(v["inert_carriers"])
                + "), each of which PASSED the strict detection profile, and none "
                  "moved any observed surface. This bounds the field; it does NOT "
                  "establish that it is a don't-care outside this envelope. "
                  "LABEL NOTE: carried as `single-template-inference`, NOT "
                  "`hardware-run`, even though the hardware evidence is a full "
                  "dense sweep -- because `hardware-run` is emitter-grade and an "
                  "emitter here must reuse the compiler-observed value, which is "
                  "a captured-template dependency. The measurement is not "
                  "downgraded; see `hardware_evidence`.")
    else:
        note = ("STILL-UNDERPOWERED: swept densely on "
                + str(len(v["inert_arms"]) + len(live)) + " arms but only "
                + str(len(v["inert_carriers"])) + " distinct carrier(s) with proven "
                  "detection power (the pre-registered bar is 3), so NOT promoted. "
                  "Reported as unreached, not as inert.")
    flat[key] = {
        "label": LABEL[bucket],
        "target": "G17P",
        "evidence": ["EXP-0163"],
        "range": rng,
        "note": note,
        "bucket": bucket,
        "semantics": SEMANTICS.get(key, "unknown -- this experiment establishes "
                                        "presence or absence of an observable "
                                        "effect, not the field's meaning"),
        "emitter_guidance": GUIDE.get(
            key,
            ("emit the compiler-observed value for your configuration; no other "
             "value had an observable effect in the tested envelope"
             if bucket == "INERT-ROBUST" else
             "see `exact_rules`; the live bits are the only ones observed to matter"
             if bucket == "LIVE" else
             "do not rely on this field; not established")),
        "hardware_evidence": {
            # What was actually executed on G17P, independent of the LABEL.  For
            # INERT-ROBUST fields the label is deliberately weaker than this;
            # this block is where the strength of the negative is recorded.
            "method": "dense splice-and-execute sweep on real hardware",
            "values_executed_per_arm": (1 << w),
            "arms_swept": len(v["inert_arms"]) + len(live),
            "arms_with_proven_detection_power": len(v["inert_arms"]) + len(live)
                                                - len(v["underpowered_arms"]),
            "distinct_carriers": sorted(set(v["inert_carriers"])
                                        | {armspec[a]["carrier"] for a in live}),
            "total_hardware_observations": sum(
                v["arms"][a]["per_run"][rn]["n"]
                for a in list(v["inert_arms"]) + list(live) for rn in runs),
            "codex_ladder_equivalent": "HW-VALIDATED (the observation); the "
                                       "field LABEL is set by what an emitter "
                                       "may do with it, not by observation "
                                       "strength",
        },
        "live_bits": live_bit_union,
        "exact_rules": rule_rows,
        "inert_arms": inert_arm_n,
        "inert_carriers": v["inert_carriers"],
        "underpowered_arms": v["underpowered_arms"],
        "cross_run_agreement": (all(r["cross_run_identical"] for r in rule_rows.values())
                                if rule_rows else True),
        "runs": runs,
    }

flat["_meta"] = {
 "experiment": "EXP-0163", "target": "G17P (Apple A18 Pro, applegpu_g17p)",
 "runs": runs,
 "question": ("whether the 22 fields EXP-0155 never observed to move are "
              "don't-cares or were merely unexercised"),
 "label_policy": __doc__.split("LABEL POLICY")[1].strip(),
 "detection_gate": ("a field's verdict counts only arms whose detection profile "
                    "showed a status-OK, same-mnemonic control moving the "
                    "observation; recomputed from raw, not from the run manifest"),
 "arms_without_detection_power": sorted(
     a for a, per in V["detection_power"].items()
     if not all(x.get("detect_ok_strict") for x in per.values())),
}

flat["secondary_byte_probes"] = {
 "op57_vertex.byte2": {
   "status": "COVERED",
   "note": ("EXP-0155's vertex 0x57 byte-probe sweeps byte+2 of the 8-byte "
            "vertex form, i.e. bit range [16:24] -- exactly `vary_store.hint2`, "
            "which is one of this experiment's 20 fields. See that entry."),
   "verdict_via": "vary_store.hint2",
 },
 "op57_fragment.byte2": {
   "status": "NOT COVERED BY EXP-0163",
   "note": ("the fragment 0x57 form is the 6-byte kill / target-mask op and NO "
            "carrier in this experiment emits it: none of the 26 uses "
            "discard_fragment() or writes [[sample_mask]], and a byte scan of "
            "every fragment program here finds no 0x57 opcode byte (the only "
            "0x57 bytes in the carrier set are operand bytes inside sdiv's "
            "compute-stage device_stores). EXP-0155's verdict stands unchanged "
            "and unimproved."),
   "what_a_successor_needs": "a discard_fragment() / [[sample_mask]] carrier",
 },
}

flat["db_defects"] = {
 "frag_color_store.byte+1 == 0x86 is not decoded": {
   "what": ("db.json matches frag_color_store on byte+1 == 0x06 exactly and "
            "imageblock_store on 0x16.  Carrier `texcube` (four texture samples "
            "then a float4 return into an RGBA32Float attachment) emits "
            "`e7 86 54 00 00 00 01 2e 00 00 00 00 07 02` -- byte-for-byte a "
            "single-RT colour store in its first twelve bytes (store_mode 0x54, "
            "mask 0x01, fmt 0x2e = RGBA32Float) but with byte+1 = 0x86.  "
            "db.json falls through and decodes it as a 14-byte COMPUTE "
            "device_store, which is impossible: that fragment program has no "
            "writable device buffer, and the op is preceded by the ordinary "
            "0x87 frag_tile_setup store bracket."),
   "why_it_matters": ("every frag_color_store occurrence census -- EXP-0155's "
                      "and this one's -- silently omits the 0x86 form, so any "
                      "claim of the shape 'frag_color_store always has X' is "
                      "unquantified over it."),
   "structure": ("0x16 = 0x06|0x10 is already documented as the first-store-"
                 "after-tile-setup marker; 0x86 = 0x06|0x80 is a THIRD variant "
                 "bit in the same byte, role unknown."),
   "evidence": "raw/prefreeze/census_run3.json -> texcube.stages.fragment",
   "status": "REPORTED, NOT SWEPT -- outside this experiment's frozen arm list",
 },
 "simd_shuffle.byte+2 is only 1 bit wide in db.json": {
   "what": ("db.json models byte+2 of simd_shuffle as a single `cache` bit at "
            "bit 17 (byte+2 bit 1).  Every observed occurrence has byte+2 == "
            "0x54, and the other seven bits of that byte are UNMODELLED."),
   "why_it_matters": ("this experiment's INERT-ROBUST verdict for "
                      "`simd_shuffle.cache` therefore covers exactly ONE BIT and "
                      "two values, not the byte.  It must not be read as "
                      "'byte+2 of simd_shuffle is inert'."),
   "evidence": "tools/agx-isa/db.json simd_shuffle.fields; raw/g17p_*/sweep.jsonl",
   "status": "MODELLING GAP, stated so the negative is not over-read",
 },
 "simd_shuffle rotate-form length: CHECKED, NO DEFECT FOUND": {
   "what": ("the mode-0x06 rotate/fill occurrences in carrier `stype` sit 12 "
            "bytes apart (offsets 332, 344, 356, 368), which looked like a "
            "10-vs-12 length defect.  It is not: db.json decodes 10 bytes of "
            "simd_shuffle and then a 2-byte `n2_compact2` (`0200`), and the "
            "stream stays consistent.  Recorded because a reviewer will see the "
            "same 12-byte spacing."),
   "open_question": ("whether that trailing `0200` is a separate op or the tail "
                     "of a 12-byte rotate form is NOT settled by spacing alone; "
                     "byte+9 (`rsv9`) is proven live by this experiment, so "
                     "byte+10/+11 are worth a splice."),
   "evidence": "raw/prefreeze/census_run3.json -> stype.stages.compute",
   "status": "NO DEFECT; open question recorded",
 },
}

out = os.path.join(HERE, "field_verdicts_flat.json")
json.dump(flat, open(out, "w"), indent=1, sort_keys=True)
n = collections.Counter(v["bucket"] for k, v in flat.items()
                        if isinstance(v, dict) and "bucket" in v)
print("wrote", out, dict(n))
