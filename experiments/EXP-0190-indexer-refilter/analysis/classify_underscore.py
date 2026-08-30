#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0190 step 2 -- the classification of every `_`-prefixed raw `field` name.

The table below is HAND-WRITTEN, one row per distinct name found by
`census_underscore.py`, from inspection of (a) the harness line that emits the name
and (b) the records themselves.  It is not a pattern match, and there is no default:
`main()` asserts that the table's key set equals the corpus's key set, so a name that
appears in a future capture fails this script loudly instead of falling into a silent
bucket.

Classes (PRE_REGISTRATION section 4):

  FIELD-SWEEP   the record's `value` is the value written into an encoding position and
                the group varies its `bytes`.  Routed to normal field attribution.
  SCAFFOLDING   baseline / control / detector / falsifier / calibration / latency /
                power / health probe.  Stays in `pseudo`, exactly as today.
  CONTROL-SHAPED
                structurally indistinguishable from a field sweep (per-field, per-value,
                with bytes) but the emitting experiment uses it as an INSTRUMENT CHECK,
                not as a measurement.  Treated as SCAFFOLDING (the conservative
                direction) and reported as a declared sensitivity, never folded into the
                headline.

`effect` records whether the classification can change any number at all: a name whose
groups never vary their `bytes` attributes nothing under either classification.

Usage: python3 analysis/classify_underscore.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
WORK = os.path.join(EXP, "work")

# name -> (class, emitter citation, reason)
TABLE = {
    # ---------------- FIELD-SWEEP -----------------------------------------
    "__dst_nibble": ("FIELD-SWEEP",
        "EXP-0180/harness/casematrix.py:284-287 dstnib_cases() + :335 field='__'+fname",
        "16-value sweep of byte0's high nibble on half_alu_ext8, value=n, one record per "
        "value, pre-registered hypothesis H0/DEF-0180-1 'destination GPR = byte0 bits 4..7'. "
        "This is the instance EXP-0189 found by hand."),
    "__len_b2": ("FIELD-SWEEP",
        "EXP-0180/harness/casematrix.py:274-278 len_cases() + :327 field='__'+rec[0]",
        "256-value sweep of byte+2 at six fixed byte+4 settings; value=b2 is the byte "
        "written. Observable is marker-chain survival (hardware instruction length), which "
        "is a real readback, but it is a LENGTH oracle, not a semantic one -- flagged on "
        "any field it restores."),
    "__len_b4": ("FIELD-SWEEP",
        "EXP-0180/harness/casematrix.py:268-273 len_cases() + :327",
        "256-value sweep of byte+4 at two fixed byte+2 settings; same length oracle as "
        "__len_b2."),
    "__raw_b0": ("FIELD-SWEEP",
        "EXP-0161/harness/cases.py:419-425 field='__raw_b%d' % bi",
        "raw whole-byte sweep at byte index 0, value=v is the byte written, `byte_index` "
        "recorded on every case. Byte-level by construction; collect_raw's bit-exact path "
        "resolves it to whichever db fields the varying bits land in."),
    "__raw_b2": ("FIELD-SWEEP",
        "EXP-0161/harness/cases.py:419-425",
        "same generator as __raw_b0 at byte index 2."),
    "__lut2d": ("FIELD-SWEEP",
        "EXP-0154/harness/casematrix.py:210 field='__lut2d', value=(ob<<8)|(la<<4)|lb",
        "2-D sweep of ilogic op_base x lut_a_sel x lut_b; the value is the packed tuple of "
        "the three encoding positions written. EXP-0154's own verdicts.py:450 reads these "
        "records as the ILOGIC measurement."),
    "__2d_desc_lo": ("FIELD-SWEEP",
        "EXP-0160/harness/casematrix.py:171 emit(field='__2d_desc_lo', value=(d<<8)|x)",
        "2-D sweep, 12 srcC_desc points x 11 srcC_lo points on imad; EXP-0160's verdicts.py:788 "
        "cites it as the evidence for the srcC split."),
    "__2d_desc_mul": ("FIELD-SWEEP",
        "EXP-0160/harness/casematrix.py:175 emit(field='__2d_desc_mul', value=(d<<8)|x)",
        "2-D sweep, 12 srcC_desc points x 8 mulsel points on imad; cited by "
        "EXP-0160/analysis/verdicts.py:808."),
    "_byte0_hi": ("FIELD-SWEEP",
        "EXP-0138/harness/families.py:506 caseB('half_alu','_byte0_hi', v, ...)",
        "16-value sweep of half_alu byte0's high nibble with a host oracle and a "
        "pre-registered expectation (v==1 matches the anchor). Named with an underscore "
        "only because db.json models byte0 as a fixed match constant -- the same shape as "
        "__dst_nibble, one instruction earlier."),
    "_match_b1": ("FIELD-SWEEP",
        "EXP-0138/harness/families.py:481-487 caseB('copysign','_match_b%d' % bi, v, ...)",
        "256-value sweep of copysign byte+1, value=v is the byte written. Declared a "
        "FALSIFIER/structure probe, but it is a dense value sweep of an encoding position; "
        "db models those bits as match constants, so it credits no db field."),
    "_match_b2": ("FIELD-SWEEP",
        "EXP-0138/harness/families.py:481-487",
        "same generator at byte+2."),
    "_b1_match": ("FIELD-SWEEP",
        "EXP-0184 raw record note: 'db.json models byte+1 as a FIXED MATCH CONSTANT "
        "(0xc2); EXP-0138 (M4) measured it LIVE. Detection-power control AND the G17P "
        "half of a db defect.'",
        "256 distinct values of copysign byte+1 over 5 groups. The note calls it a "
        "detection-power control AND a db-defect measurement; it is a dense value sweep "
        "either way. Credits no db field (match bits)."),
    "_b2_match": ("FIELD-SWEEP",
        "EXP-0184 / EXP-0187 raw record note: 'modelled as a fixed match constant; swept "
        "for the G17P record'",
        "256 distinct values of byte+2 over 12 groups; dense value sweep of an encoding "
        "position. Credits no db field."),
    "_b3_match": ("FIELD-SWEEP",
        "EXP-0187 raw record note: 'fixed match constant in the pinned db; swept as a "
        "WHOLE-WORD liveness probe, never as a field'",
        "16 distinct values of n4_rt_word byte+3 over 10 groups. The note disclaims FIELD "
        "status, and it is right that db exposes no field there -- so including it credits "
        "nothing, but it is a value sweep and is classified as one."),

    # ---------------- CONTROL-SHAPED (reported, still discarded) ----------
    "_detect": ("CONTROL-SHAPED",
        "EXP-0163/run.py:437-462 and EXP-0172/run.py:475 -- the DETECTION PROFILE loop",
        "for every db field of the anchor's descriptor it writes two values (the "
        "complement of the current value, and 0) and records whether the observation "
        "changed; outcome is 'moved'/'inert'. Structurally a per-field 2-value hardware "
        "sweep with bytes and observations -- 265 of 271 groups vary their bytes and they "
        "land in real db fields. But both experiments consume it ONLY as "
        "`arms_with_proven_detection_power`, i.e. as the instrument check that licences "
        "their inert verdicts, and two values chosen to maximise the chance of a change is "
        "not the dense sweep FIELD-SWEEP-PROTOCOL section 3 requires. Held out of the "
        "headline; reported as a declared sensitivity."),

    # ---------------- SCAFFOLDING -----------------------------------------
    "_ANCHOR_VERDICT": ("SCAFFOLDING",
        "EXP-0157/harness/run.py:503 field='_ANCHOR_VERDICT', value=int(bool(live))",
        "the VALUE is a boolean verdict ('LIVE iff L1 or L2 moved the output off "
        "baseline'), not a value written into the encoding. 50 of 94 groups nevertheless "
        "vary their bytes -- because one group spans several ANCHORS -- so the structural "
        "test alone would have promoted a pure bookkeeping record. This is the clearest "
        "reason the classification must be by intent as well as by structure."),
    "_L1_opcode_group": ("SCAFFOLDING",
        "EXP-0157/harness/cases.py:127 {'field':'_L1_opcode_group','value':ibytes[0]^0x01}",
        "rung 1 of the two-rung liveness ladder: ONE fixed mutation (byte0 xor 1) per "
        "anchor, used only to decide whether the anchor is live. Not a sweep; the 45/83 "
        "groups that 'vary' do so across anchors."),
    "_L2_erase": ("SCAFFOLDING",
        "EXP-0157/harness/cases.py:131 {'field':'_L2_erase','value':0}",
        "rung 2 of the same ladder -- zero the instruction and see whether anything moves. "
        "Single value, no group varies its bytes."),
    "_live_control": ("SCAFFOLDING",
        "EXP-0155/run.py:505 and EXP-0143/run.py:412, field='_live_control', value=-1",
        "the ladder-rung liveness control; value is the sentinel -1, and the record carries "
        "the rung description in `note`. 89 of 162 groups vary bytes across RUNGS, not "
        "across values of one position."),
    "_detect_summary": ("SCAFFOLDING",
        "EXP-0163/run.py:472, EXP-0172/run.py:489, value=-1, bytes=''",
        "one per arm; carries the detection-power summary JSON in `note`. No bytes."),
    "_baseline": ("SCAFFOLDING",
        "EXP-0163/run.py:425 and ~20 sibling harnesses",
        "the unmutated anchor. 0 of 706 groups vary their bytes, by definition."),
    "__baseline": ("SCAFFOLDING", "EXP-0161/harness/cases.py",
        "the unmutated anchor; 0 of 32 groups vary."),
    "_baseline_recheck": ("SCAFFOLDING", "EXP-0155, EXP-0163 run.py",
        "the anchor re-run mid-sweep to detect drift; 0 of 370 groups vary."),
    "_baseline_final": ("SCAFFOLDING", "EXP-0163, EXP-0172 run.py",
        "the anchor re-run at the end of a run; 0 of 454 groups vary."),
    "_baseline_health": ("SCAFFOLDING", "EXP-0141, EXP-0153 run.py",
        "periodic health check of the persistent runner; no bytes recorded."),
    "_baseline_check": ("SCAFFOLDING", "EXP-0146 run.py", "anchor recheck; 0 of 12 vary."),
    "_baseline_fwd": ("SCAFFOLDING", "EXP-0141 harness", "anchor for the forwarding arm."),
    "_smoke_baseline": ("SCAFFOLDING", "EXP-0169 harness", "smoke-run anchor."),
    "_smoke_calib": ("SCAFFOLDING", "EXP-0169 harness", "smoke-run calibration."),
    "_smoke_store_shape": ("SCAFFOLDING", "EXP-0169 harness",
        "smoke-run check of the store shape."),
    "_cascade_check": ("SCAFFOLDING", "EXP-0155, EXP-0172 run.py",
        "DEF-0178-1 guard: re-run after a watchdog timeout to detect a manufactured hang "
        "cascade. An instrument, not a measurement."),
    "_calibprobe": ("SCAFFOLDING", "EXP-0169 harness", "runner calibration; no bytes."),
    "_latency_E1": ("SCAFFOLDING", "EXP-0169 harness", "latency probe; no bytes."),
    "_latency_E2": ("SCAFFOLDING", "EXP-0169 harness", "latency probe; no bytes."),
    "_litmus_power": ("SCAFFOLDING", "EXP-0147/harness/run.py",
        "detection-power litmus; 0 of 20 groups vary."),
    "_sensitivity": ("SCAFFOLDING", "EXP-0147/harness/run.py:631 record('_sensitivity',...)",
        "single-byte sensitivity control; 0 of 20 groups vary."),
    "_identity_splice": ("SCAFFOLDING", "EXP-0147/harness/run.py:626",
        "splice the anchor back onto itself -- the null mutation; 0 of 20 groups vary."),
    "_poscontrol": ("SCAFFOLDING", "EXP-0139/harness/casematrix.py:135, value=-1",
        "positive control, value sentinel -1; 0 of 28 groups vary."),
    "_liveness_src_alt": ("SCAFFOLDING", "EXP-0147/harness/run.py",
        "liveness control on an alternate source; 0 of 14 groups vary."),
    "_liveness_dst_alt": ("SCAFFOLDING", "EXP-0147/harness/run.py",
        "liveness control on an alternate destination; 0 of 8 groups vary."),
    "_liveness_spatial": ("SCAFFOLDING", "EXP-0147/harness/run.py",
        "spatial liveness control; 0 of 6 groups vary."),
    "_liveness_vp_alt": ("SCAFFOLDING", "EXP-0147/harness/run.py",
        "viewport liveness control; 0 of 2 groups vary."),
    "_natural": ("SCAFFOLDING", "EXP-0156/harness/cases.py:371 (arm 'mask_op.liveness')",
        "the natural, unspliced encoding of the liveness arm; single value, 0 of 3 vary."),
    "_rounding": ("SCAFFOLDING", "EXP-0156/harness/cases.py",
        "rounding-mode control case; 0 of 3 groups vary."),
    "_byte0": ("SCAFFOLDING", "EXP-0168/harness/casematrix.py:812 add(role='falsifier',...)",
        "the pre-registered-to-fail byte0 falsifier (0x55); one value per arm, 0 of 66 "
        "groups vary."),
    "_byte2_56": ("SCAFFOLDING", "EXP-0156/harness/cases.py:198 (arm 'ret_luse.control')",
        "single fixed control value (0x56) on the ret_luse control arm; 0 of 4 vary."),
    "_byte1_11": ("SCAFFOLDING", "EXP-0156/harness/cases.py (arm 'atdev_rmw.control')",
        "single fixed control value (0x11); records carry no bytes at all."),
    "_ERASE4": ("SCAFFOLDING", "EXP-0157 (generated name; reachprobe.py:37 documents it)",
        "zero-erase reachability probe over a 4-byte window; no varying group."),
    "_ERASE16": ("SCAFFOLDING", "EXP-0157", "zero-erase probe, 16-byte window."),
    "_ERASE64": ("SCAFFOLDING", "EXP-0157", "zero-erase probe, 64-byte window."),
    "_ERASE256": ("SCAFFOLDING", "EXP-0157", "zero-erase probe, 256-byte window."),
    "_ZERO4": ("SCAFFOLDING", "EXP-0157", "zeroed 4-byte control; single record."),
    "_INERT4": ("SCAFFOLDING", "EXP-0157", "inert 4-byte control; single record."),
    "_start": ("SCAFFOLDING", "EXP-0157", "run-start marker; single record, no bytes."),
    "_falsifier_oracle": ("SCAFFOLDING", "EXP-0153 harness",
        "pre-registered-to-fail oracle check; 0 of 18 groups vary."),
    "_falsifier_dst00": ("SCAFFOLDING", "EXP-0141, EXP-0153 harness",
        "pre-registered-to-fail dst=0 case; 0 of 9 vary."),
    "_falsifier_extmode0": ("SCAFFOLDING", "EXP-0141, EXP-0153 harness",
        "pre-registered-to-fail extmode=0 case; 0 of 6 vary."),
    "_falsifier_op_and": ("SCAFFOLDING", "EXP-0141 harness", "falsifier; 0 of 4 vary."),
    "_falsifier_op_bit": ("SCAFFOLDING", "EXP-0141 harness", "falsifier; 0 of 2 vary."),
    "_falsifier_ldformat0": ("SCAFFOLDING", "EXP-0141 harness", "falsifier; 0 of 2 vary."),
    "_falsifier_barrier_off": ("SCAFFOLDING", "EXP-0141 harness", "falsifier; 0 of 2 vary."),
    "_falsifier_fwd_am54": ("SCAFFOLDING", "EXP-0141 harness", "falsifier; 0 of 3 vary."),
    "_refuter_modlo2_unbound": ("SCAFFOLDING", "EXP-0153 harness",
        "pre-registered refuter; 0 of 3 groups vary."),
    "__falsifier_byte0": ("SCAFFOLDING", "EXP-0169, EXP-0154 casematrix",
        "pre-registered-to-fail byte0 mutation; 0 of 185 groups vary."),
    "__falsifier_b2": ("SCAFFOLDING", "EXP-0161 cases.py", "falsifier; 0 of 4 vary."),
    "__falsifier_F1_opsel_hadd": ("SCAFFOLDING",
        "EXP-0180/harness/casematrix.py:230-247 falsifiers()",
        "pre-registered-to-fail: opsel -> hadd MUST change an fma result. Instrument check; "
        "0 of 24 groups vary."),
    "__falsifier_F2_srcA_zerolane": ("SCAFFOLDING", "EXP-0180/harness/casematrix.py:230-247",
        "pre-registered-to-fail: srcA -> the one lane that is 0.0 must move; 0 of 24 vary."),
    "__falsifier_F3_dstnib_r7": ("SCAFFOLDING", "EXP-0180/harness/casematrix.py:230-247",
        "pre-registered-to-fail: byte0 high nibble -> 7 must move the write to r7. Same "
        "encoding position as __dst_nibble but a single fixed value used as an instrument "
        "check; 0 of 24 groups vary."),
    "__falsifier_F4_zero_point": ("SCAFFOLDING", "EXP-0180/harness/casematrix.py:262",
        "the marker chain with no instruction in front of it -- the LEN instrument's zero "
        "point; 0 of 3 groups vary."),
    "__power_sr_sel": ("SCAFFOLDING", "EXP-0178/harness/run.py:808 record('power_probe',...)",
        "detection-power probe; 0 of 7 groups vary."),
    "__power_b7": ("SCAFFOLDING", "EXP-0178/harness/run.py:808", "power probe; 0 of 4 vary."),
    "__power_fmt": ("SCAFFOLDING", "EXP-0178/harness/run.py:808", "power probe; 0 of 4 vary."),
    "__sens_byte0_bit2": ("SCAFFOLDING", "EXP-0178/harness/run.py:829 record('sensitivity',...)",
        "sensitivity control; 0 of 7 groups vary."),
    "__sens_byte1": ("SCAFFOLDING", "EXP-0178/harness/run.py:832", "sensitivity control."),
    "__split_at0_r6": ("SCAFFOLDING", "EXP-0160/harness/casematrix.py:160 emit(value=77)",
        "single fixed-value structural split probe; 0 of 2 groups vary."),
    "__split_at0and2": ("SCAFFOLDING", "EXP-0160/harness/casematrix.py:162", "as above."),
    "__split_at2_r6": ("SCAFFOLDING", "EXP-0160/harness/casematrix.py:156", "as above."),
    "__split_at2_r7": ("SCAFFOLDING", "EXP-0160/harness/casematrix.py:158", "as above."),
}
# every `__ladder_L_*` name: EXP-0169/casematrix.py:461, EXP-0178/run.py:792,
# EXP-0180/casematrix.py:349 -- `field="__ladder_" + nm, value=v`.
for _n in ("dst", "opsel", "srcA", "srcA_reg", "srcA_size", "srcB_size",
           "srcB_desc_samelen", "src", "src_reg", "form", "sr_sel", "rt", "b5",
           "ext_b5", "ext_b9", "extmode", "idx_off", "known_move"):
    TABLE["__ladder_L_" + _n] = ("SCAFFOLDING",
        "EXP-0169/harness/casematrix.py:461, EXP-0178/harness/run.py:792, "
        "EXP-0180/harness/casematrix.py:349 -- field='__ladder_' + nm",
        "a rung of the pre-registered LIVENESS LADDER: one mutation per rung, run to prove "
        "the arm can see a change at all before any inert verdict is allowed. The value is "
        "an encoding value, but the rung is an instrument check, not a sweep -- and NO "
        "ladder group varies its bytes, so the classification cannot change any number.")

FIELD_SWEEP = frozenset(n for n, (c, _, _) in TABLE.items() if c == "FIELD-SWEEP")


def main():
    census = json.load(open(os.path.join(WORK, "underscore_census.json")))["names"]
    missing = sorted(set(census) - set(TABLE))
    extra = sorted(set(TABLE) - set(census))
    if missing:
        print("FAIL: %d name(s) in the corpus are not classified: %s"
              % (len(missing), missing), file=sys.stderr)
        return 2
    if extra:
        print("NOTE: %d classified name(s) no longer in the corpus: %s" % (len(extra), extra))
    out = {}
    for n, v in sorted(census.items()):
        cls, emitter, reason = TABLE[n]
        effect = ("can-change-attribution" if v["n_groups_bytes_vary"] > 0 else
                  "no-effect (no group varies its bytes)")
        out[n] = {
            "classification": cls,
            "reason": reason,
            "emitter": emitter,
            "effect_of_classification": effect,
            "n_records": v["n_records"],
            "experiments": v["experiments"],
            "instr_labels": v["instr_labels"],
            "n_runs": v["n_runs"],
            "n_distinct_values": v["n_distinct_values"],
            "n_groups": v["n_groups"],
            "n_groups_bytes_vary": v["n_groups_bytes_vary"],
            "db_fields_the_varying_bits_hit": v["db_fields_hit"],
            "outcomes": v["outcomes"],
            "example_group": v["example_group"],
            "files_sample": v["files_sample"],
        }
    counts = {}
    for v in out.values():
        counts[v["classification"]] = counts.get(v["classification"], 0) + 1
    doc = {"_meta": {
        "experiment": "EXP-0190-indexer-refilter",
        "rule": "PRE_REGISTRATION.md section 4; hand-classified, one row per distinct name, "
                "no default bucket",
        "n_names": len(out),
        "n_records": sum(v["n_records"] for v in out.values()),
        "counts": counts,
        "field_sweep_names": sorted(FIELD_SWEEP),
        "control_shaped_names": sorted(n for n, v in out.items()
                                       if v["classification"] == "CONTROL-SHAPED"),
        "n_names_whose_classification_can_change_anything": sum(
            1 for v in out.values() if v["n_groups_bytes_vary"] > 0),
    }, "names": out}
    json.dump(doc, open(os.path.join(HERE, "underscore_fields.json"), "w"),
              indent=1, sort_keys=True)
    print("classified %d names (%d records): %s"
          % (len(out), doc["_meta"]["n_records"], counts))
    print("names whose classification can change attribution at all: %d"
          % doc["_meta"]["n_names_whose_classification_can_change_anything"])
    for n in sorted(out):
        if out[n]["n_groups_bytes_vary"]:
            print("  %-22s %-14s vary %d/%d  hits=%s"
                  % (n, out[n]["classification"], out[n]["n_groups_bytes_vary"],
                     out[n]["n_groups"],
                     ",".join(list(out[n]["db_fields_the_varying_bits_hit"])[:3]) or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
