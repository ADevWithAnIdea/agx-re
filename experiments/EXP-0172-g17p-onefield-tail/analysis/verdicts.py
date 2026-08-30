#!/usr/bin/env python3
"""verdicts.py -- EXP-0172: two gated runs -> analysis/field_verdicts.json.

    python3 analysis/verdicts.py

Recomputes EVERYTHING from raw/, never from a run manifest, so a verdict cannot
inherit a bookkeeping error.  Implements the gate frozen in PRE_REGISTRATION.md
sec.6 and nothing else:

  * an arm counts only if its DETECTION PROFILE, recomputed from raw, showed a
    status-OK, SAME-MNEMONIC control that moved the observation;
  * >=99% per-value cross-run agreement on the outcome partition AND
    movement >= 2 x the disagreement count;
  * a never-moving field is INERT-ROBUST only if the carriers differ in the
    dimension the field controls (DIMENSION below, authored explicitly so a
    reviewer can disagree with a named claim rather than an implicit one);
  * labels: LIVE -> hardware-run, INERT-ROBUST -> single-template-inference
    (rule 8), STILL-UNDERPOWERED -> untested, DECLINED -> unchanged.

Every row carries machine-readable coverage: `values_dispatched`,
`distinct_bytes` (counted from DISTINCT `bytes` strings in raw, never from the
dispatched-value count), `encodable_range` (the values whose patched bytes
re-decode as the SAME mnemonic -- DEF-0170-1), and `start`/`width` re-read from
the PINNED db.json so a stale DB is a loud merge failure, not a silent
mis-attribution.

CLEAN-ROOM: pure analysis of our own captures.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
sys.path.insert(0, os.path.join(EXP, "work", "frozen"))
import arms as ARMSPEC              # noqa: E402
import carriers as CA               # noqa: E402
import isadb                        # noqa: E402

RUNS = ["g17p_20260830_run01", "g17p_20260830_run02"]
AGREE_MIN = 0.99

# Outcomes that are NOT a property of the encoding and therefore cannot be
# compared across runs.  This is not a loosening of the frozen gate: it is
# FIELD-SWEEP-PROTOCOL sec.7's own definition --
# "kIOGPUCommandBufferCallbackErrorInnocentVictim means 'discarded, victim of
# another context's error/recovery' -- a sibling's reset, not a property of your
# encoding. Segregate those" -- and PRE_REGISTRATION.md sec.5.8, which froze
# "InnocentVictim retried and segregated as `foreign`" before any run.  Comparing
# a `foreign` against anything is a category error, so these values are excluded
# from the comparison POPULATION and counted separately.  Both agreement figures
# (raw and valid-population) are reported on every row.
NOT_A_PROPERTY = {"foreign", "unreproduced"}

# Does the carrier set differ in the dimension the field controls (rule 2)?
# Authored, not inferred: each entry states the dimension and whether it was
# actually spanned, so an inert verdict rests on a named claim.
DIMENSION = {
 "falu2i.imm_flag": dict(
   dimension="operand/immediate WIDTH (the hypothesis: bit 0 of the srcB operand "
             "byte is the size bit in the two sibling overloads -- falu2.srcB_size "
             "'1:b32 0:b16', falu2_uni.usrc '(ureg<<1)|size32')",
   spanned=True,
   spanned_how="15 occurrences over 2 structurally different carriers spanning the "
               "immediate VALUE domain (4 distinct exponents, mantissa 0 and !=0), "
               "both SIGNS, fadd/fmul/fma, and both operand provenances "
               "(ALU/SR-seeded vs load-sourced mods==0xC0)",
   not_spanned="the WIDTH itself: every falu2i the compiler emits has "
               "srcA_size==1 (b32). A b16 falu2i was never produced by any of the "
               "24 carriers, so the null does NOT cover the b16 form. Stated so "
               "the negative is not over-read."),
 "get_sr.form": dict(
   dimension="special-register DATAPATH WIDTH (db.json: 'a datapath/width modifier, "
             "set for the position-in-grid SR family, that does not change the SR select')",
   spanned=True,
   spanned_how="srwide reads ONLY the multi-component uint3 SR family; srnarrow "
               "reads ONLY scalar SRs; and after the smoke02 correction the arm "
               "list spans the field's OWN baseline values, 4 arms at form=0 and "
               "4 at form=1, so both flip directions are tested",
   not_spanned=""),
 "tex_sample.coord": dict(
   dimension="which register supplies the texture COORDINATE",
   spanned=True,
   spanned_how="texread is derivative-free integer read(uint2) only; texmix reaches "
               "the same descriptor through explicit-LOD sample, gather and read in "
               "one program. Both are LOD- and derivative-free, unlike EXP-0155's "
               "filtered arms",
   not_spanned="implicit-LOD filtered sampling, deliberately: that is the "
               "configuration whose per-value outcome did not reproduce in EXP-0155."),
 "vary_slot.slot": dict(
   dimension="which varying SLOT the following vary_store writes",
   spanned=True,
   spanned_how="vmany forces 16 scalar varyings (slots past 7); vhalf uses half and "
               "vector widths; vflat is flat/no-perspective; vsrc sources varyings "
               "from memory rather than one class. Baseline slot values 0x00/0x20/0x40 "
               "are present across the arms",
   not_spanned=""),
 "tex_deriv.dstsrc": dict(
   dimension="the packed destination and source REGISTERS of the quad-difference op",
   spanned=True,
   spanned_how="the authored deriv carrier emits 9 occurrences with 9 DISTINCT "
               "dstsrc values across both axis codes (0x92 dfdx / 0x90 dfdy) and the "
               "fwidth abs+add form; 4 arms chosen to span distinct baselines",
   not_spanned=""),
 "imageblock_store.src": dict(
   dimension="which register supplies the STORED value",
   spanned=True,
   spanned_how="ibsamp at 1 sample and ibms4 at 4 samples with resolve -- the only "
               "two carriers of the 24 that emit imageblock_store at all (ibhalf and "
               "ibmrt compile to frag_color_store instead, recorded in arms.MISSING)",
   not_spanned="explicit multi-field imageblock<T> layouts: those do not compile "
               "(EXP-0155 reported imageblock_load NOT ATTEMPTED for the same reason)."),
 "irotate.b2": dict(
   dimension="unknown; the byte is 7/8 pinned by the descriptor's own match",
   spanned=False,
   spanned_how="3 carriers differing in source last-use and operand width",
   not_spanned="THE FIELD ITSELF. match pins bit16=0 and bits18..23=0x15, leaving "
               "bit 17 free: TWO legal values (byte+2 in {0x54, 0x56}) out of 256 "
               "dispatched. This is DEF-0170-1: an 8-bit 'field' that is mostly part "
               "of the match."),
 "simd_ballot.cache": dict(
   dimension="source LAST-USE / cache hint (db.json's vocabulary for a byte in this "
             "role: falu_acc, RT-1a-FIX)",
   spanned=True,
   spanned_how="deadsrc is a NEW carrier in which every operand is loaded, used ONCE "
               "and dead immediately after -- the dimension in which EXP-0163's four "
               "carriers (sball/scache/sdiv/stype) were all identical, i.e. one "
               "carrier under rule 2, because every one of them reuses its sources",
   not_spanned=""),
 "simd_shuffle.cache": dict(
   dimension="source LAST-USE / cache hint",
   spanned=True,
   spanned_how="same as simd_ballot.cache, plus stype's mode-0x06 rotate/fill form "
               "and the 16/64-bit operand widths",
   not_spanned="SEVEN OF THE EIGHT BITS OF THE BYTE. db.json models byte+2 of "
               "simd_shuffle as a SINGLE bit (`cache` at bit 17); byte+2 is 0x54 in "
               "every occurrence and the other 7 bits are unmodelled. This null "
               "covers TWO VALUES OF ONE BIT, not the byte (EXP-0163 db_defects)."),
 "frame_marker_compact.b1": dict(
   dimension="unknown; the payload of the 2-byte marker `60 <b1>`",
   spanned=True,
   spanned_how="5 arms over 5 carriers and BOTH stages -- threadgroup-atomic and "
               "rotate compute kernels plus vertex stages of vhalf/vsrc",
   not_spanned="b1 == 0x00 is the 4-byte spill_frame_marker, a DIFFERENT "
               "instruction; it is dispatched and recorded but excluded from "
               "encodable_range."),
 "n4_cf_word.b3": dict(
   dimension="unknown; the 4th byte of the compact control word `04 01 00 <b3>`",
   spanned=True,
   spanned_how="3 carriers with nested data-dependent divergence, reconvergence "
               "points and threadgroup barriers",
   not_spanned="IRRELEVANT: no arm has detection power (see the verdict)."),
 "ret.scoreboard": dict(
   dimension="execution / scoreboard-WAIT ordering",
   spanned=False,
   spanned_how="1 carrier",
   not_spanned="THE ORDERING ITSELF. This harness reads back after command-buffer "
               "completion, which flushes, so it cannot observe ordering. Promotion "
               "was DECLINED IN ADVANCE in the pre-registration for exactly this "
               "reason; the sweep is recorded, not promoted."),
}

DECLINE_PROMOTION = {"ret.scoreboard"}


def load(run):
    p = os.path.join(EXP, "raw", run, "sweep.jsonl")
    if not os.path.exists(p):
        return None
    out = []
    with open(p) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass                      # a torn last line, if killed
    return out


def main():
    runs = {r: load(r) for r in RUNS}
    runs = {k: v for k, v in runs.items() if v}
    if not runs:
        sys.exit("no run data")

    # width/start from the PINNED db.json
    geom = {}
    for ins in isadb.DB:
        for fl in ins.get("fields", []):
            geom[f"{ins['mnemonic']}.{fl['name']}"] = (fl["start"], fl["width"])

    armof = {a["id"]: a for a in ARMSPEC.ARMS}

    # ---- detection power, recomputed from raw ----------------------------
    power = collections.defaultdict(dict)      # arm -> run -> {...}
    for run, recs in runs.items():
        for r in recs:
            if r["field"] != "_detect":
                continue
            aid = r["carrier"]
            note = r["note"]
            fn = note.split("detection profile: ")[1].split("=")[0]
            redec = note.split("redecodes_as=")[1].strip()
            e = power[aid].setdefault(run, {"strict": [], "any": [], "fault_only": [],
                                            "steps": 0})
            e["steps"] += 1
            moved = r["outcome"] == "moved"
            okstat = r["observed"].get("status") == "OK"
            same = (redec == armof.get(aid, {}).get("mnemonic"))
            if moved and okstat and same:
                e["strict"].append(f"{fn}={r['value']:#x}")
            if moved:
                e["any"].append(f"{fn}={r['value']:#x}")
            if moved and not okstat:
                e["fault_only"].append(f"{fn}={r['value']:#x}/"
                                       f"{r['observed'].get('os_class','')}")

    # ---- per-arm, per-run sweep tables -----------------------------------
    sweep = collections.defaultdict(lambda: collections.defaultdict(dict))
    byte_of = collections.defaultdict(lambda: collections.defaultdict(dict))
    redec_bad = collections.defaultdict(set)
    for run, recs in runs.items():
        for r in recs:
            f = r["field"]
            if f.startswith("_"):
                continue
            aid = r["carrier"]
            key = (aid, f)
            v = r["value"]
            if v < 0:
                continue
            sweep[key][run][v] = r["outcome"]
            byte_of[key][run][v] = r["bytes"]
            if "re-decodes as" in (r.get("note") or ""):
                redec_bad[key].add(v)

    fields = collections.defaultdict(list)
    for (aid, f), _ in sweep.items():
        a = armof.get(aid)
        if a:
            fields[f"{a['mnemonic']}.{f}"].append((aid, f))

    out = {}
    for fkey, arm_keys in sorted(fields.items()):
        mnem, fname = fkey.rsplit(".", 1)
        start, width = geom.get(fkey, (None, None))
        dim = DIMENSION.get(fkey, {})
        per_arm = {}
        tot_move = tot_dis = tot_cmp = 0
        powered = []
        all_bytes = set()
        enc_all = set()
        vals_all = set()
        for aid, f in sorted(arm_keys):
            a = armof[aid]
            tabs = sweep[(aid, f)]
            swept_runs = sorted(tabs)
            pw = {run: bool(power.get(aid, {}).get(run, {}).get("strict"))
                  for run in swept_runs}
            # An arm counts only if it has strict detection power in EVERY run in
            # which it was swept, AND it was swept in both gated runs.
            strict_ok = bool(swept_runs) and all(pw.values()) and len(swept_runs) > 1
            two_run = len(tabs) > 1
            common = (set.intersection(*[set(t) for t in tabs.values()])
                      if two_run else set())
            foreign = sorted(v for v in common
                             if any(tabs[r][v] in NOT_A_PROPERTY for r in tabs))
            valid = common - set(foreign)
            agree = sum(1 for v in valid if len({tabs[r][v] for r in tabs}) == 1)
            dis = len(valid) - agree
            raw_agree = sum(1 for v in common
                            if len({tabs[r][v] for r in tabs}) == 1)
            moved_vals = sorted(v for v in valid
                                if all(tabs[r][v] == "wrong_value" for r in tabs))
            fault_vals = sorted(v for v in common
                                if all(tabs[r][v] in ("fault", "hang") for r in tabs))
            hang_region = sorted(v for v in common
                                 if any(tabs[r][v] in ("fault", "hang")
                                        for r in tabs))
            bset = set()
            for run in tabs:
                bset |= set(byte_of[(aid, f)][run].values())
            vals = set()
            for run in tabs:
                vals |= set(tabs[run])
            enc = sorted(v for v in vals if v not in redec_bad[(aid, f)])
            all_bytes |= bset
            enc_all |= set(enc)
            vals_all |= vals
            # Is the moved set exactly one bit of the field?  A structured
            # partition is far stronger evidence than a movement count.
            bit_rule = None
            if moved_vals and len(vals) > 2:
                for b in range(width or 0):
                    on = {v for v in valid if v & (1 << b)}
                    off = valid - on
                    if on and set(moved_vals) == on and not (set(moved_vals) & off):
                        bit_rule = (f"exactly the values with bit {b} set move "
                                    f"({len(on)} of {len(valid)}); every value with "
                                    f"bit {b} clear leaves the observation unchanged")
                        break
            per_arm[aid] = {
                "carrier": a["carrier"], "stage": a["stage"], "occ": a["occ"],
                "runs_swept": swept_runs,
                "baseline_instruction_hex": a["expect_hex"],
                "baseline_decode": a["census_fields"],
                "foreign_excluded_from_comparison": len(foreign),
                "cross_run_agreement_raw_incl_foreign":
                    round(raw_agree / len(common), 5) if common else None,
                "hang_region_values": hang_region[:20],
                "single_bit_rule": bit_rule,
                "tier": a["tier"], "baseline_field_value": a["census_fields"].get(f),
                "tokenized": a["tokenized"],
                "detection_power_strict": pw,
                "counts_toward_verdict": strict_ok,
                "values_dispatched": len(vals),
                "values_compared_across_runs": len(valid),
                "cross_run_agreement": round(agree / len(valid), 5) if valid else None,
                "disagreements": dis,
                "moved_both_runs": len(moved_vals),
                "moved_values": moved_vals[:40],
                "faulted_both_runs": len(fault_vals),
                "fault_values": fault_vals[:40],
                "distinct_bytes": len(bset),
                "encodable_range_n": len(enc),
                "encodable_values": enc[:40],
                "moved_inside_encodable_n": len(set(moved_vals) & set(enc)),
                "moved_inside_encodable": sorted(set(moved_vals) & set(enc))[:40],
                "why_this_carrier": a["why"][:400],
            }
            if strict_ok:
                powered.append(aid)
                tot_move += len(moved_vals)
                tot_dis += dis
                tot_cmp += len(valid)

        agreement = (1.0 - tot_dis / tot_cmp) if tot_cmp else None
        moved_enc = sum(per_arm[a]["moved_inside_encodable_n"] for a in powered)
        gate = {
            "runs": sorted(runs),
            "arms_total": len(arm_keys),
            "arms_with_detection_power": len(powered),
            "values_compared": tot_cmp,
            "cross_run_agreement": round(agreement, 5) if agreement is not None else None,
            "agreement_gate_0.99": bool(agreement is not None and agreement >= AGREE_MIN),
            "movement_both_runs": tot_move,
            "movement_inside_encodable_range": moved_enc,
            "disagreements": tot_dis,
            "movement_ge_2x_disagreement": bool(tot_move >= 2 * tot_dis and tot_move > 0),
            "dimension_spanned": bool(dim.get("spanned")),
            "arms_swept_in_one_run_only": sorted(
                a for a, _ in arm_keys if len(per_arm[a]["runs_swept"]) < 2),
            "foreign_excluded_total": sum(
                per_arm[a]["foreign_excluded_from_comparison"] for a, _ in arm_keys),
        }
        gate["exact_rules"] = sorted(
            {per_arm[a]["single_bit_rule"] for a in powered
             if per_arm[a]["single_bit_rule"]})

        if fkey in DECLINE_PROMOTION:
            bucket, label = "DECLINED", "corpus-correlation"
        elif not powered:
            bucket, label = "STILL-UNDERPOWERED", "untested"
        elif not gate["agreement_gate_0.99"]:
            bucket, label = "STILL-UNDERPOWERED", "untested"
        elif moved_enc > 0 and gate["movement_ge_2x_disagreement"]:
            bucket, label = "LIVE", "hardware-run"
        elif tot_move == 0:
            if gate["dimension_spanned"]:
                bucket, label = "INERT-ROBUST", "single-template-inference"
            else:
                bucket, label = "STILL-UNDERPOWERED", "untested"
        else:
            bucket, label = "STILL-UNDERPOWERED", "untested"

        out[fkey] = {
            "label": label,
            "bucket": bucket,
            "target": "G17P (Apple A18 Pro, applegpu_g17p)",
            "evidence": ["EXP-0172"],
            "tier": min(armof[a]["tier"] for a, _ in arm_keys),
            "start": start,
            "width": width,
            "values_dispatched": max((per_arm[a]["values_dispatched"]
                                      for a, _ in arm_keys), default=0),
            "values_dispatched_union_over_arms": len(vals_all),
            "distinct_bytes": len(all_bytes),
            "encodable_range": len(enc_all),
            "encodable_range_note":
                "values whose patched bytes RE-DECODE as the same mnemonic in "
                "context; the rest are dispatched and recorded but are a different "
                "instruction (DEF-0170-1)",
            "range": (f"0..{(1 << width) - 1} dense (all {1 << width} values)"
                      if width and width <= 8 else
                      f"boundaries + powers of two + 16 interior samples of {width} bits"),
            "gate": gate,
            "rule2_dimension": dim,
            "arms": per_arm,
        }

    doc = {
        "_meta": {
            "experiment": "EXP-0172",
            "question": "the one-field-away tail of the emitter worklist: can an "
                        "emitter choose these fields' values and get documented "
                        "hardware behaviour?",
            "runs": sorted(runs),
            "target": "G17P (Apple A18 Pro, applegpu_g17p)",
            "pinned_db_sha256_recorded_in": "CAPTURE_CONTRACT.json",
            "gate": "PRE_REGISTRATION.md sec.6, applied by this script and nothing else",
            "label_policy": {
                "LIVE": "hardware-run -- the encodable range executed and the "
                        "value->behaviour partition reproduced across two runs",
                "INERT-ROBUST": "single-template-inference, NOT hardware-run (rule 8): "
                                "emitter-grade asserts the implementer may CHOOSE the "
                                "value, and 'emit what the compiler emitted' is a "
                                "captured-template dependency. The MEASUREMENT is not "
                                "downgraded, only the claim about what an emitter may do.",
                "STILL-UNDERPOWERED": "untested (protocol sec.5: do not round up)",
                "DECLINED": "label unchanged; the reason is recorded",
            },
            "forbidden_evidence_not_used": [
                "roundtrip_test.py / rt_ok -- a round trip is not an emitter gate",
                "tokenization", "captured-template replay", "corpus census alone",
            ],
            "declined_without_device_time": CA.DECLINED,
            "arms_missing_from_the_frozen_list": ARMSPEC.MISSING,
        },
    }
    doc.update(out)
    p = os.path.join(EXP, "analysis", "field_verdicts.json")
    json.dump(doc, open(p, "w"), indent=1, sort_keys=True)

    print(f"{'field':34s} {'bucket':20s} {'label':28s} agree  moved/enc  arms  vals/bytes/enc")
    for k, v in sorted(out.items()):
        g = v["gate"]
        print(f"{k:34s} {v['bucket']:20s} {v['label']:28s} "
              f"{str(g['cross_run_agreement']):7s} "
              f"{g['movement_both_runs']:4d}/{g['movement_inside_encodable_range']:<4d} "
              f"{g['arms_with_detection_power']}/{g['arms_total']:<3d} "
              f"{v['values_dispatched']}/{v['distinct_bytes']}/{v['encodable_range']}")
    print("\nwrote", p)


if __name__ == "__main__":
    main()
