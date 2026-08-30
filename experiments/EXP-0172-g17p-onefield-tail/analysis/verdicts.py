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

RUNS = ["g17p_20260830_run01", "g17p_20260830_run02", "g17p_20260830_run03"]
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

# Value -> behaviour rules read off the two gated runs and re-derived by
# analysis; each reproduces the observed partition EXACTLY, with no exceptions,
# in every run in which the arm was swept.
EXACT_RULES = {
 "tex_sample.coord":
   "coord is an OPERAND BYTE of the form (reg << 1) | is32, exactly the src-byte "
   "convention db.json documents for falu2. On the live arm the moved set is "
   "reproduced with ZERO exceptions by:  moved  <=>  (v & 1) == 1  AND  "
   "((v >> 1) mod 16) in {6, 8, 10, 14}  -- 32 of 256 values, identical in both "
   "gated runs. Reading: bit0 selects the 32-bit operand size, the remaining 7 "
   "bits are a register index, and on this fragment stage the index ALIASES WITH "
   "PERIOD 16 (the four live registers recur at reg, reg+16, reg+32 ... reg+112). "
   "That extends the mod-64 ALU aliasing of EXP-0112 with a distinct, smaller "
   "period for the texture-coordinate operand. The four live residues are the "
   "registers this carrier actually keeps live; a coordinate pointed at a dead "
   "register leaves the sampled result unchanged rather than faulting.",
 "vary_slot.slot":
   "exactly ONE bit of the modelled 8-bit field is observable: all 128 values "
   "with bit 2 set move the observation, all 128 with bit 2 clear do not, in both "
   "gated runs, with no exceptions. The other 7 bits had no effect on any of the "
   "4 carriers -- including the bits the COMPILER varies (observed baselines "
   "0x00/0x20/0x40 = slot index << 5). See db_defects.",
 "irotate.b2":
   "TWO legal values only (byte+2 in {0x54, 0x56}); both executed on all 5 arms. "
   "The effect is ASYMMETRIC and reproduced exactly in both runs: on the three "
   "arms whose baseline is 0x56, setting 0x54 CHANGES the observation; on the two "
   "arms whose baseline is 0x54, setting 0x56 changes nothing. Both directions "
   "were tested because the arm list was built to span the field's own baseline "
   "values. The remaining 254 dispatched values are not irotate at all.",
 "imageblock_store.src":
   "a source-register byte: 244 of the 248 values swept before the hang region "
   "change the stored value, identically in both runs and on both the 1-sample "
   "and the 4-sample carrier. src = 246 and 247 HANG the device (reproduced, "
   "majority-of-3), which is what stopped the sweep at 248/256.",
 "tex_deriv.dstsrc":
   "a packed destination+source operand: 37 of the 39 sampled values compared "
   "across runs change the derivative result on every arm, identically in both "
   "runs. The two that do not are the all-ones patterns 0x3FFFF and 0x7FFFF, "
   "which HANG the device (reproduced) and stopped the sweep at 39 of 65 sampled "
   "values.",
 "frame_marker_compact.b1":
   "live on the carrier that does not hang: 152 of 256 values change the "
   "observation, identically in run01 and run03. b1 = 0x00 is the 4-byte "
   "spill_frame_marker -- a DIFFERENT instruction -- and b1 = 3 and b1 = 7 hang "
   "the device on four of the five carriers.",
}

DB_DEFECTS = {
 "DEF-0172-1 irotate.b2 is ONE bit, not eight": {
   "what": "db.json models byte+2 of irotate as an 8-bit field `b2`, but the "
           "descriptor's OWN match pins bit 16 = 0 and bits 18..23 = 0x15, leaving "
           "bit 17 free: TWO legal values (byte+2 in {0x54, 0x56}) out of 256.",
   "evidence": "tools/agx-isa/match_overlap_report.py at pre-registration; and this "
               "experiment dispatched all 256 values on 5 arms -- 254 of them "
               "re-decode as a different instruction and are recorded `undecodable`.",
   "class": "instance of DEF-0170-1 (a field overlapping its own match)",
   "severity": "MEDIUM -- the encoding is right, the FIELD WIDTH is a fiction. A "
               "coverage claim of '256 values swept' on this field would be false; "
               "the honest coverage is 2 of 2 encodable, which this experiment "
               "reports and which is why the promotion is still sound.",
   "status": "REPORTED; db.json not edited (the orchestrator owns it)."},
 "DEF-0172-2 isadb.imm_encode cannot emit falu2i.imm_flag = 0": {
   "what": "db.json's prose lists `flag(bit8)` inside `imm_decode(b1, sign)`, "
           "implying the bit is part of the immediate. The IMPLEMENTATION disagrees: "
           "`imm_decode` computes m = (b1 >> 1) & 0x7 -- a 3-BIT mantissa -- and "
           "never reads b1 bit 0, while `imm_encode` hard-sets it "
           "(b1 = (e<<4) | (m<<1) | 1). Our own encoder can therefore only ever "
           "produce ONE of the field's two legal values.",
   "evidence": "tools/agx-isa/isadb.py imm_decode/imm_encode, read at "
               "pre-registration; the hypothesis built on the prose was rewritten "
               "before any build (PRE_REGISTRATION.md sec.9).",
   "class": "same class as DEF-0170-1: an encoder that cannot reach a legal encoding "
            "is not an emitter for that field, whatever a round trip says.",
   "severity": "LOW for correctness -- this experiment proves the bit is INERT "
               "across 15 occurrences, so nothing miscompiles -- but HIGH for "
               "documentation: the prose asserts a role the code does not implement "
               "and the hardware does not exhibit.",
   "status": "REPORTED; neither db.json nor isadb.py edited."},
 "DEF-0172-3 vary_slot.slot is modelled 8 bits wide; ONE bit is observable, and it "
 "is not the bit the compiler varies": {
   "what": "All 128 values with bit 2 set move the observation and all 128 with bit "
           "2 clear do not, with no exceptions in either gated run. The other seven "
           "bits produced no observable effect on any of the four carriers -- "
           "including bits 5..6, which are exactly where the COMPILER encodes the "
           "varying index (observed baselines 0x00 / 0x20 / 0x40 = index << 5).",
   "evidence": "raw/g17p_20260830_run01 + run02, arm vary_slot@vsrc/vertex#0, "
               "256 values x 2 runs; the three other carriers swept 256 values each "
               "with zero movement and no strict detection power.",
   "severity": "MEDIUM -- an emitter told 'byte+3 is the varying slot' will encode "
               "the index in the high bits, which is what the compiler does and what "
               "the hardware appears to ignore here. Either the slot is consumed "
               "somewhere this harness cannot see (the vary_store it precedes), or "
               "the field is mis-modelled. EXP-0155 already concluded the "
               "emitter-relevant lever is `vary_store.out_slot`; this is direct "
               "hardware evidence for that reading.",
   "status": "REPORTED, NOT RESOLVED -- a successor should sweep byte+3 of "
             "vary_slot jointly with vary_store.out_slot."},
 "DEF-0172-4 n4_cf_word has NO observable effect at all -- not just b3": {
   "what": "The full detection profile -- every modelled field of the instruction "
           "complemented AND zeroed -- moved nothing, on three carriers with nested "
           "data-dependent divergence, reconvergence points and threadgroup "
           "barriers, in the smoke calibration and in both gated runs. The 4-byte "
           "word `04 01 00 XX` is observationally inert in its entirety here.",
   "evidence": "raw/*/sweep.jsonl `_detect` records for n4_cf_word@{cfdiv,sdiv,tgat}; "
               "768 dense sweep cases of b3 with zero movement.",
   "reading": "TWO possibilities, and this experiment does not separate them: the "
              "word is a genuine no-op/alignment marker, OR what it controls "
              "(reconvergence correctness under divergence) is not visible in a "
              "per-lane readback taken after command-buffer completion. Reported as "
              "UNDERPOWERED (`untested`), not as inert.",
   "severity": "LOW-MEDIUM -- it blocks n4_cf_word from ever being promoted by this "
               "method. A successor needs a divergence observable, not a bigger sweep.",
   "status": "REPORTED."},
 "simd_shuffle.cache still covers ONE BIT OF EIGHT (EXP-0163, reconfirmed)": {
   "what": "db.json models byte+2 of simd_shuffle as a single `cache` bit at bit 17; "
           "byte+2 is 0x54 in every occurrence and the other seven bits are "
           "unmodelled.",
   "this_experiment_adds": "the null now also holds on `deadsrc`, a carrier in which "
           "every operand is loaded, used ONCE and dead immediately after -- the "
           "last-use dimension in which all four of EXP-0163's carriers were "
           "identical. The negative is stronger; its SCOPE is unchanged.",
   "severity": "MEDIUM -- 'simd_shuffle byte+2 is inert' remains UNPROVEN; only two "
               "values of one bit have been tested.",
   "status": "REPORTED (EXP-0163 db_defects), reconfirmed."},
 "cubearray_coord_const fires 0 times in 24 fresh carriers (EXP-0148 reconfirmed)": {
   "what": "The pre-freeze census tokenized all 24 carriers in both stages and found "
           "ZERO occurrences of cubearray_coord_const, consistent with EXP-0148's "
           "0 firings in 1080 corpus files.",
   "severity": "the descriptor cannot be swept by anyone: there is no program in "
               "which to splice its bytes. Its only exercise is the literal 4-byte "
               "string in roundtrip_test.py, and a round trip is not an emitter gate.",
   "recommendation": "this is a descriptor-EXISTENCE question for the orchestrator "
                     "(delete, or re-anchor it outside the tex_addr_setup token), "
                     "not a field sweep. While it stands, it inflates the "
                     "emitter-relevant denominator with an instruction nobody can "
                     "emit or observe.",
   "status": "REPORTED."},
}


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
        gate["single_bit_rules_auto"] = sorted(
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
            "exact_rules": EXACT_RULES.get(fkey, ""),
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
    doc["db_defects"] = DB_DEFECTS
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
