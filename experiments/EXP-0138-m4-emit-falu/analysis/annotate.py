#!/usr/bin/env python3
"""EXP-0138 cross-run annotation (runs AFTER `verdicts.py`).

  analysis/annotate.py <gated_a> <gated_b> <extra> [<extra> ...]

`verdicts.py` implements the promotion rule frozen in `PRE_REGISTRATION.md`
section 7 and is left untouched; the `label` it produced is the deliverable
label. This script only ADDS disclosure. It never upgrades `label`.

It adds:

  * `cross_run` -- per field, whether each EXTRA run reproduces the gated
    pair's per-case outcome+value map, and on how many shared cases.
  * `label_isolated_pair` -- the label the SAME frozen script produces from
    the two ISOLATED-host runs (`run05` + `run06`) instead of the
    contended-host `run01`. Recorded for disclosure only. Where it is
    stronger than `label`, the difference is caused by run01's
    non-reproducing faults: run01 was captured against ~9 concurrent GPU
    experiments (254 faults / 41 victims) while run05 and run06 saw 15 faults
    and 0 victims. FIELD-SWEEP-PROTOCOL 7.1 says a non-reproducing fault is
    not a property of the field, so this column is the protocol's reading --
    but `label` stays conservative and the orchestrator decides.
  * `resolved_sentinel` -- for fields the frozen rule failed ONLY because
    some case tripped the integrity sentinel, the demonstrated structural
    cause (see `db_defects.sentinel_release`).
  * `db_defects` -- corrected models where the sweep showed `db.json`'s field
    ROLES or boundaries do not match the hardware (protocol section 6).
    `db.json` itself is NOT edited; the orchestrator owns it.

CLEAN-ROOM: pure analysis of this experiment's own raw JSON. No Apple binary.
"""
import json, math, sys, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent

DB_DEFECTS = {
  "falu2.mod_lo": {
    "db_model": "a 3-bit modifier named `mod_lo` with no semantics",
    "hardware_model": (
      "an OPERAND-SOURCE-CLASS field, split. bit0 selects srcA's source class; "
      "bits[2:1] select srcB's source class: 0=GPR (srcB_reg), 1=the "
      "non-GPR operand file addressed by srcB_reg, 2 and 3 both read as 0.0. "
      "bit2 DOMINATES bit1 (mod_lo=6 reads 0.0, not the uniform value that "
      "mod_lo=2 reads at the same index)."),
    "evidence": "EXP-0138 falu2.mod_lo, 98 cases, run01/run05/run06",
    "impact": "the field is emitter-relevant, not a spare modifier"},
  "falu2.srcB_reg_bit6_in_uniform_mode": {
    "db_model": "srcB_reg is a 7-bit register index; EXP-0099/EXP-0112 established "
                "bit6 as effectively inert in GPR mode (r(R mod 64) aliasing)",
    "hardware_model": (
      "with mod_lo bits[2:1]==1 the SAME field is NOT a register index and bit6 "
      "is LIVE: srcB_reg in 0..63 indexes the uniform register file, srcB_reg in "
      "64..127 supplies an INLINE 8-bit MINIFLOAT IMMEDIATE with k = srcB_reg-64, "
      "e = k>>3, m = k&7, value = m*2^-5 for e==0 else (8+m)*2^(e-6). "
      "HW-confirmed at k = 0,2,3,31,32,48,56,61,62,63 -> "
      "0, 0.0625, 0.09375, 1.875, 2.0, 8.0, 16.0, 26.0, 28.0, 30.0. "
      "Indices 126/127 do NOT fault in this mode (they are immediates 28.0/30.0), "
      "unlike the GPR mode where EXP-0112 recorded a fault."),
    "evidence": "EXP-0138 falu2.mod_lo uniform-index map, 33 cases",
    "impact": "falu2 can take a float immediate operand directly; an emitter that "
              "treats srcB_reg as a plain register in this mode emits the wrong operand"},
  "sentinel_release": {
    "db_model": "n/a -- a property of this experiment's MODE-A measurement",
    "hardware_model": (
      "reading a GPR as a 32-bit source operand through falu3/falu3_ext byte+1 or "
      "byte+5, or through falu_acc byte+1/byte+3, ZEROES that register afterwards "
      "(release-on-read). Directly observed: falu3.dst=23 -> w0=85.0=26*3+7 (the "
      "operand read r11=26.0 CORRECTLY) while w4, the later read-back of r11, "
      "returned 0.0, with the poison still intact in every untouched word. The "
      "case is a valid measurement whose sentinel was destroyed BY the field "
      "working, exactly like the `sentinel_by_design` carve-out verdicts.py "
      "already declares for `dst` fields."),
    "evidence": "EXP-0138 falu3.dst v=23/151, falu3.srcC v=22/23, falu_acc.srcA/srcB",
    "impact": "falu3 / falu3_ext / falu_acc source descriptors are held at `untested` "
              "by the frozen rule for 2-4 cases each that are explained, not broken. "
              "Reported, NOT promoted -- the orchestrator decides."},
  "falu3_family_field_names": {
    "db_model": "byte+1 = `dst`, byte+3 = `srcA`, byte+4 = `srcB`, byte+5 = `srcC`",
    "hardware_model": (
      "H-FALU3-LAYOUT CONFIRMED: byte0's high nibble is the DESTINATION "
      "(dst_lo sweep, 14/16 exact, the 2 misses being r11/r15 which are this "
      "experiment's own sentinel/index registers); byte+1 is the FIRST SOURCE "
      "descriptor (228/256 exact, every miss explained below); byte+3 is the "
      "SECOND SOURCE (228/256, same pattern); byte+5 is the THIRD SOURCE "
      "(252/256); byte+4 is a CONTROL byte whose low 2 bits are the 0x09-group "
      "LENGTH selector (192/256 re-length the instruction). The 28 `dst`/`srcA` "
      "misses are exactly the descriptor values with bit0 CLEAR over the seeded "
      "registers: bit0 is the operand SIZE bit (1 = 32-bit, 0 = 16-bit), and a "
      "16-bit read of an f32-seeded register returns 0.0. That CONFIRMS "
      "(reg<<1)|is32 rather than refuting it. byte+5's bit0 does NOT behave as a "
      "size bit (srcC v=22 and v=23 both read r11=26.0)."),
    "evidence": "EXP-0138 G_falu3 / G_falu3_ext, 1809 + 2321 cases",
    "impact": "db.json's field NAMES for falu3/falu3_ext are misleading; an emitter "
              "following them would put the destination in a source slot"},
  "fspecial.src_bit7": {
    "db_model": "byte+3 `src`, an ordinary operand byte",
    "hardware_model": (
      "values 192..255 (bit7 set) FAULT the command buffer or HANG the GPU. "
      "run01 (contended host): 60 reproducible `fault`s across 192..255. "
      "run05 (isolated host): values 192, 193, 194 each HUNG the GPU three times "
      "in a row under a 12 s watchdog, which is why the fspecial arm was stopped "
      "per FIELD-SWEEP-PROTOCOL section 8. Only values 2 and 3 produce the "
      "correct rsqrt(4)=0.5; 188 other values silently return 0.0; values 6 and 7 "
      "leave the poison intact (the store never ran)."),
    "evidence": "EXP-0138 fspecial.src, run01 256/256 + run05 195/256",
    "impact": "SAFETY: an emitter must never set byte+3 bit7 of fspecial. The whole "
              "fspecial family stays PARTIAL / untested -- one gated run only."},
}



# ---------------------------------------------------------------------------
# Derived value->behaviour models for the fields an emitter needs FIRST. Each
# is a rule fitted to this experiment's own observations and then re-checked
# against every case of that field's sweep (see `analysis/model_check.py`).
# ---------------------------------------------------------------------------
SEM_MODEL = {
 "falu2.mod_lo":
   "OPERAND-SOURCE-CLASS field. bit0=0 -> srcA reads GPR[srcA_reg]; bit0=1 -> srcA "
   "reads a second source class that returned 0.0 at every index tested "
   "(srcA_reg in {0,6}) and is NOT the uniform file. bits[2:1]=0 -> srcB reads "
   "GPR[srcB_reg]; =1 -> srcB reads the non-GPR operand file at srcB_reg (indices "
   "0..63 = uniform registers, 64..127 = inline minifloat immediate); =2 and =3 "
   "both read 0.0, and bit2 DOMINATES bit1. Model reproduces 98/98 observed cases "
   "exactly in all three runs.",
 "falu2.srcB_reg (in mod_lo bits[2:1]==1 mode)":
   "0..63 = uniform-register index (the bound `constant float4&` appeared at "
   "6..9); 64..127 = inline minifloat immediate, k=v-64, e=k>>3, m=k&7, "
   "value = m*2^-5 (e==0) else (8+m)*2^(e-6).",
 "copysign.operands":
   "byte+3 is INERT: all 256 values return the same result. The method's "
   "sensitivity on this exact output path is witnessed by the pre-registered "
   "falsifier arm on byte+1, where 240/256 values silently zero, 8 return -5.0 "
   "and 8 return +5.0. So the inertness is a hardware fact, not a dead path.",
 "half_alu.dst":
   "byte+1 is the FIRST SOURCE descriptor, not the destination (H-HALF-LAYOUT). "
   "252/256 values return the same result because only 0x04/0x02/0x05 are live "
   "operands in the MODE-B carrier; the live values track the carrier's memory "
   "operands exactly.",
 "half_alu.opflags":
   "bits19..23. Values 0..7 behave as the anchor; 8..29 change the result "
   "(release-source semantics, cf. EXP-0086/0099 on falu2); 10..31 silently "
   "zero. Dense over all 32 values.",
 "falu_acc.op":
   "byte0 low bit: 0 = fadd_acc (5+3=8.0), 1 = fmul_acc (5*3=15.0). Both "
   "executed and matched the host oracle.",
 "fspecial.src":
   "byte+3. Only 2 and 3 produce the correct rsqrt(4)=0.5; 188 values silently "
   "return 0.0; 6 and 7 leave the poison intact (no store at all); 192..255 "
   "(bit7 set) FAULT or HANG. SAFETY-CRITICAL: never emit bit7.",
}

# Fields whose sweep produced ONE result for every value. For a `dst` field
# that IS the positive result (the read-back follows the register the field
# names, so a constant answer proves the field steers the write). For the
# others the pre-registration section 7 caveat applies, so each records the
# witness that the output path was live and the method sensitive.
INERT_WITNESS = {
 "copysign.operands": "copysign byte+1 falsifier arm (240 silent zeros / 8 sign flips)",
 "falu2_uni.srcA_size": "same carrier: falu2_uni.usrc and .srcA_reg both change the result",
 "falu2i.imm_flag": "same carrier: falu2i.mods produces four distinct results",
 "falu3_srcmod12.srcB_imm": "same sweep: falu3_srcmod12.srcA_reg/.opsel change the result",
 "falu_srcmod12b.mod_hi": "same sweep: falu_srcmod12b.srcA_reg changes the result",
 "falu_srcmod12b.mod_lo": "same sweep: falu_srcmod12b.srcA_reg changes the result. NOTE: "
                          "falu2's mod_lo IS live; this family's is not, at the operands tested",
 "falu_srcmod12b.srcB_imm": "same sweep: falu_srcmod12b.srcA_reg changes the result",
 "falu_srcmod12b.srcB_neg": "same sweep: falu_srcmod12b.srcA_reg changes the result. NOTE: "
                            "falu2's srcB_neg negates; this family's did not, at the operands tested",
 "fspecial_est.subop": "same carrier: fspecial_est.b4/.b5 change the result",
 "half_alu_ext8.b7_lo": "same carrier: half_alu_ext8.dst/.opflags change the result",
 "half_alu_ext8.b7_mid": "same carrier: half_alu_ext8.dst/.opflags change the result",
}


def load(p):
    return [json.loads(l) for l in open(Path(p) / "sweep.jsonl")]


def eq(a, b):
    if a is None or b is None:
        return a is b
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b or abs(a - b) <= 1e-6 * max(1.0, abs(b))
    return a == b


def obsval(r):
    o = r["observed"]
    return o.get("w0", o.get("o0"))


def main():
    ga, gb = sys.argv[1], sys.argv[2]
    extras = sys.argv[3:]
    V = json.load(open(HERE / "field_verdicts.json"))
    A = {r["i"]: r for r in load(ga)}
    B = {r["i"]: r for r in load(gb)}
    gated = sorted(set(A) & set(B))
    key = {i: "%s.%s" % (A[i]["instr"], A[i]["field"]) for i in gated}
    ex = {Path(e).name: {r["i"]: r for r in load(e)} for e in extras}

    per = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for i in gated:
        k = key[i]
        for name, recs in ex.items():
            r = recs.get(i)
            if r is None:
                continue
            per[k][name][1] += 1
            if r["outcome"] == A[i]["outcome"] and eq(obsval(r), obsval(A[i])):
                per[k][name][0] += 1

    iso_path = EXP / "work" / "fv_run05_run06.json"
    ISO = json.load(open(iso_path)) if iso_path.exists() else {}

    n_disagree = collections.Counter()
    upgrades = []
    EMIT = {"hardware-run", "isolated-byte-diff"}
    for k, v in V.items():
        if k.startswith("_"):
            continue
        cr = {}
        for name, (agree, n) in sorted(per.get(k, {}).items()):
            cr[name] = {"cases_shared": n, "cases_agreeing": agree,
                        "identical": agree == n}
            if agree != n:
                n_disagree[name] += 1
        if cr:
            v["cross_run"] = cr
        iso = ISO.get(k)
        if iso:
            v["label_isolated_pair"] = iso["label"]
            if iso["label"] in EMIT and v["label"] not in EMIT:
                upgrades.append(k)
                v["note"] = (v["note"] + "; " if v["note"] else "") + \
                    ("HELD BACK BY run01 ONLY: the two ISOLATED-host runs "
                     "(run05+run06) give `%s` for this field. run01 was captured "
                     "against ~9 concurrent GPU experiments (254 faults / 41 "
                     "victims vs 15 / 0). Not promoted here." % iso["label"])
        if "failed the integrity sentinel" in v.get("note", ""):
            v["resolved_sentinel"] = "db_defects.sentinel_release"
        if k in SEM_MODEL:
            v["semantics_model"] = SEM_MODEL[k]
        if v["label"] in EMIT and not v["live"]:
            if k.split(".")[-1] in ("dst", "dst_lo"):
                v["inert_note"] = ("one result for every value IS the positive result here: "
                                   "the read-back follows the register this field names, so a "
                                   "constant answer proves the field steers the write")
            else:
                v["inert_note"] = ("no value changed the result. PRE_REGISTRATION section 7 "
                                   "caveat applied -- sensitivity witness on the same output "
                                   "path: " + INERT_WITNESS.get(k, "NONE RECORDED"))

    V["db_defects"] = DB_DEFECTS
    for kk, vv in SEM_MODEL.items():
        if kk not in V:
            V.setdefault("_derived_models", {})[kk] = vv
    V["_meta"]["cross_run_extra_runs"] = list(ex)
    V["_meta"]["fields_with_extra_run_disagreement"] = dict(n_disagree)
    V["_meta"]["fields_held_back_by_run01_only"] = sorted(upgrades)
    V["_meta"]["emit_unsafe_regardless_of_labels"] = ["falu_srcmod12b", "half_alu_fma12"]
    (HERE / "field_verdicts.json").write_text(json.dumps(V, indent=1))
    print(json.dumps({"gated_cases": len(gated),
                      "extra_runs": {k: len(v) for k, v in ex.items()},
                      "fields_with_extra_run_disagreement": dict(n_disagree),
                      "fields_held_back_by_run01_only": sorted(upgrades)}, indent=1))


if __name__ == "__main__":
    main()
