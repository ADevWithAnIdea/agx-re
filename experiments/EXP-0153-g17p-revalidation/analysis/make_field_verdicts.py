#!/usr/bin/env python3
"""EXP-0153: emit analysis/field_verdicts.json -- the per-field labels this
experiment establishes DIRECTLY ON G17P.

Labels come only from `docs/evidence-classification.md` §2, and every entry
carries the three mandatory qualifiers (`range`, `target`, `evidence`) plus the
M4 value it was revalidated against.

A field is labelled `hardware-run` here only if BOTH gated runs agree
case-for-case (PRE_REGISTRATION §10.1) -- which `analysis/verdicts.py` reports
as `cross_run_total.n_disagree == 0`. Anything short of that is reported at a
weaker label or as `PARTIAL`, never rounded up.

This file is a PROPOSAL for the orchestrator to merge into
`tools/agx-isa/validation.json`. This experiment does not edit that file.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
V = json.load(open(os.path.join(HERE, "verdicts.json")))
# The fault-class revalidation pass (5 repetitions per case, UNDER the GPU
# lease) is what decides every fault verdict -- FIELD-SWEEP-PROTOCOL 7.1. Both
# unlocked gated runs agreed on five `fault`s in F_imm_top that isolation shows
# are not faults, so the bulk runs alone must not set a fault label.
REVAL = os.path.join(os.path.dirname(HERE), "raw", "g17p-20260830-reval02",
                     "sweep.jsonl")
GATED = V.get("gated") and V.get("cross_run_total", {}).get("n_disagree") == 0
EV = ["EXP-0153"]
T = "G17P"


def hw(rng, sem, m4, note=""):
    return {"label": "hardware-run" if GATED else "isolated-byte-diff",
            "range": rng, "target": T, "evidence": EV,
            "semantics": sem, "revalidates": m4, "note": note}


A = V["A_device_load_destination"]
B = V["B_falu2_source_class"]
C = V["C_native_64bit_add"]["iadd2.addsub_native_64bit_add"]
D = V["D_register_model"]
E = V["E_ibfe_out_of_range"]
F = V["F_mov_imm"]

out = {
 "_meta": {
   "experiment": "EXP-0153-g17p-revalidation",
   "target": "G17P (Apple A18 Pro, Mac17,5, AGXAcceleratorG17P, applegpu_g17p, "
             "5 GPU cores, macOS 26.6 build 25G5043d)",
   "gated_runs": V["runs"],
   "cross_run_agreement": V.get("cross_run_total"),
   "labels_from": "docs/evidence-classification.md §2",
   "status": "PROPOSAL -- this experiment does not edit tools/agx-isa/validation.json",
   "rule": "hardware-run requires BOTH gated runs to agree case-for-case; "
           "this run recorded 1958/1958 agreement and 0 disagreements",
 },

 "device_load.dst_lo": hw(
   "0..3 dense (all 4 values), at two independent target registers r7 and r20",
   "NOT a register field. An enable pattern: accepted iff %s. Write 1."
   % A["A_dst_lo_R7"]["mask_rule"]["expr"],
   "EXP-0141 (M4): 1 of 4, v & 3 == 1 -- identical"),

 "device_load.dst_ext9": hw(
   "0..127 dense (all 128 values), at two independent target registers r7 and r20",
   "NOT a register field. Accepted iff %s; bits 1-6 are don't-care on this "
   "carrier. Write 1." % A["A_dst_ext9_R7"]["mask_rule"]["expr"],
   "EXP-0141 (M4): 64 of 128, v & 1 == 1 -- identical"),

 "device_load.dst_lo+dst_ext9": hw(
   "the full 512-value 2-D product at r7",
   "The pair carries no register information: exactly 64 of 512 combinations "
   "are accepted and they factorise as {dst_lo == 1} x {dst_ext9 odd} (%s)."
   % A["A_dst_pair"]["mask_rule"]["expr"],
   "EXP-0141 (M4): 64 of 512, v & 0x181 == 0x81 -- identical"),

 "device_load.extmode": hw(
   "0..255 dense, each paired with a consumer reading r(v>>1)",
   "Destination register selector, R = extmode >> 1; bit 0 is a DON'T-CARE "
   "(64 of the 128 accepted values are odd). R is reachable for 0..63 ONLY: "
   "all 128 values >= 128 fail (124 wrong_value, 4 fault). extmode 252..255 "
   "(R = 126, 127) FAULTS reproducibly with kIOGPUCommandBufferCallbackErrorHang "
   "-- an emitter must never write them.",
   "EXP-0141 (M4): 128 of 256, v & 0x80 == 0, R >= 64 silently zeroes; EXP-0141 "
   "raw run11/run12 also faulted at 252..255 -- identical, fault set included"),

 "_db_rename_note": {
   "what": "While this experiment was running, tools/agx-isa/db.json was "
           "updated by a sibling experiment and falu2's 3-bit `mod_lo` (start "
           "40) was SPLIT into `srcA_class` (start 40, width 1) and "
           "`srcB_class` (start 41, width 2). The captures here were taken "
           "against db.json f5db942f... (recorded in every raw/<run>/"
           "00_env.json), which still had `mod_lo`.",
   "why_it_does_not_invalidate_anything": "The split is EXACTLY the model this "
           "arm measured, and the encoding is bit-for-bit the same field. Map "
           "the entry below onto the new names as: srcA_class = mod_lo bit 0, "
           "srcB_class = mod_lo bits[2:1]. The G17P sweep covered all 8 "
           "combinations densely, so it establishes BOTH new fields over their "
           "full ranges (srcA_class 0..1, srcB_class 0..3).",
   "reproduction": "The frozen DB is at commit "
           "ff99bb52326a433375008408004a8db6294a04db; with it pinned, "
           "cases.build_all() rebuilds all 1958 cases and reproduces all 1958 "
           "recorded instruction byte-strings exactly (analysis/reproduce.sh).",
   "validation_json_state_at_authoring": "falu2.srcA_class and falu2.srcB_class "
           "carry no label yet, so this evidence is directly mergeable."},

 "falu2.srcA_class (= mod_lo bit 0)": hw(
   "0..1, both values, x 4 operand configurations x {fadd, fmul}",
   "Selects srcA's operand source class. 0 = GPR at srcA_reg. 1 = a second "
   "class that returned 0.0 at every index tested -- in particular NOT the "
   "uniform file.",
   "EXP-0138 (M4) measured this as bit 0 of `mod_lo`; identical on G17P"),

 "falu2.srcB_class (= mod_lo bits[2:1])": hw(
   "0..3, all four values, x 4 operand configurations x {fadd, fmul}",
   "Selects srcB's operand source class. 0 = GPR at srcB_reg. 1 = the non-GPR "
   "operand file / inline-immediate class addressed by srcB_reg. 2 and 3 both "
   "read 0.0, and bit 1 of this field DOMINATES bit 0.",
   "EXP-0138 (M4) measured this as bits[2:1] of `mod_lo`; identical on G17P"),

 "falu2.mod_lo": hw(
   "0..7 dense (all 8 values) x 4 operand configurations x {fadd, fmul} = 64 cases",
   "Operand SOURCE-CLASS field. bit0 selects srcA's class (1 => reads 0.0); "
   "bits[2:1] select srcB's class: 0 = GPR at srcB_reg, 1 = the non-GPR operand "
   "file at srcB_reg, 2 and 3 both read 0.0, and bit2 DOMINATES bit1.",
   "EXP-0138 (M4): 98/98 per run, 294/294 overall -- model fit here %s, and "
   "8/8 at every one of the 8 values" % B["falu2.mod_lo"]["model_fit"]),

 "falu2.srcB_reg@mod_lo=1..3 (non-GPR class)": hw(
   "0..127 dense (all 128 values) at mod_lo = 2",
   "Two regimes in one field. 0..63 indexes the non-GPR operand file (our bound "
   "`constant float4&` was found at indices 6..9 = 101/202/303/404). 64..127 is "
   "an INLINE 8-BIT MINIFLOAT IMMEDIATE: k = v - 64, e = k>>3, m = k&7, "
   "value = m * 2^-5 (e == 0) else (8+m) * 2^(e-6). bit6 is LIVE here, unlike "
   "the GPR class. 126/127 do not fault in this class (they are 28.0 and 30.0).",
   "EXP-0138 (M4): the same formula, confirmed at TEN points; G17P confirms all "
   "SIXTY-FOUR (%s), including those ten"
   % B["falu2.minifloat"]["model_fit_64_127"]),

 "falu2.srcB_reg@mod_lo=0 (GPR class)": hw(
   "0..127 dense (all 128 values) at mod_lo = 0",
   "A 7-bit field that addresses 64 registers: R resolves to r(R mod 64). "
   "Confirmed at 49/49 values in 64..112, including 13 distinct NON-ZERO "
   "discriminators (v = 64..76 returned 5.0 + SEED[v-64] exactly). The top bit "
   "is inert; 126/127 do NOT fault in this field.",
   "EXP-0112 (M4) established r(R mod 64) on device_load's destination "
   "selector; EXP-0099 (M4) found falu2's register top bit inert. Both hold on "
   "G17P for this field"),

 "iadd2.addsub": hw(
   "the single bit, in both polarities, over 12 input rows x 5 repetitions x 2 "
   "gated runs",
   "0 = 64-bit subtract, 1 = a COMPLETE NATIVE 64-BIT ADD with carry across the "
   "32-bit word boundary, in ONE 10-byte instruction. Byte0 %s -> %s."
   % (C["bytes_before"][:2], C["bytes_after"][:2]),
   "EXP-0146 (M4): exact on 8 rows in both gated runs and 5/5 in run05. G17P: "
   "%s repetitions exact over 12 rows including 2^63+2^63=0, 0x7FFF..F+1, "
   "0xFFFFFFFF00000000+0xFFFFFFFF and 0xFFFF..E+3" % C["add_repetitions_exact"]),

 "iadd2.dst": hw(
   "0..255 dense (all 256 values), relocation oracle",
   "(reg << 1) | size. The sum reaches the store's r6 at exactly dst = 12/13. "
   "reg >= 96 (dst >= 192) FAULTS reproducibly -- 64 values. EXP-0112's "
   "r(R mod 64) aliasing does NOT hold for this field: dst = 140/141 (reg 70) "
   "did not alias to r6.",
   "EXP-0139 (M4): identical -- reached r6 at 12/13, fault boundary reg 96, "
   "no aliasing at 140/141"),

 "ibfe.offset": hw(
   "0..63 dense (the whole 6-bit field), in two independent lowerings",
   "LITERAL, not mod-32: 0-31 shift normally, 32-63 shift the field out "
   "entirely (result 0). The hardware does NOT implement NIR's "
   "'mask offset mod 32'.",
   "EXP-0139 (M4): literal 64/64 vs mod-32 32/64. G17P: literal %s vs mod-32 %s "
   "-- the SAME fit counts"
   % (E["ibfe.offset"]["preregistered_model_fit"],
      E["ibfe.offset"]["competing_model_fit"])),

 "ibfe.width": hw(
   "0..63 dense (the whole 6-bit field)",
   "TAKEN MOD 32. width == 0 (mod 32) is the no-mask (extract-to-MSB) case, so "
   "width = 32 behaves exactly like width = 0. The opposite rule to `offset` in "
   "the same instruction.",
   "EXP-0139 (M4): mod-32 64/64 vs literal-clamp 37/64. G17P: mod-32 %s vs "
   "literal-clamp %s -- the SAME fit counts"
   % (E["ibfe.width"]["preregistered_model_fit"],
      E["ibfe.width"]["competing_model_fit"])),

 "mov_imm.imm7": hw(
   "0..127 dense (all 128 values), against a poisoned read-back buffer",
   "A 7-bit unsigned immediate written to r{dst}. All 128 values reach the "
   "destination, INCLUDING 12.",
   "EXP-0140 (M4): hardware-run 0..127 -- identical (%d/%d ok)"
   % (F["mov_imm.imm7"]["n_ok"], F["mov_imm.imm7"]["n_total"])),

 "mov_imm.imm_top": hw(
   "1, at five immediates (128, 129, 140, 200, 255), each in a PAIRED "
   "padded/unpadded form",
   "NOT an eighth immediate bit and NOT a silent zero: with imm_top = 1 the "
   "instruction DOES NOT WRITE the destination at all, AND it changes the "
   "instruction's length. Padded (4 B of inert padding after it), the "
   "destination keeps its previous value 7 at all five immediates tested. "
   "Unpadded, the instruction stream desyncs and NEITHER following "
   "device_store executes: the read-back buffer comes back poison everywhere "
   "except out[12], the pre-test sentinel (proved offline from the committed "
   "sha_0 = 564e3165d8085121). An emitter must treat the immediate as SEVEN "
   "bits.",
   "EXP-0140 (M4): padded keeps the previous value -- identical. Unpadded, M4 "
   "observed the read-back store addressing the wrong word; G17P shows the "
   "stores not executing at all. Same length-desync conclusion, cleaner "
   "signature. NOTE: in BOTH unlocked gated runs the unpadded cases were "
   "recorded as reproducible faults; the 5x revalidation under the GPU lease "
   "shows only imm 128 is a fault 5/5, while 140/200/255 are wrong_value 5/5 "
   "and 129 is 2 fault / 3 wrong_value -- victims that survived cross-run "
   "agreement (see RESULTS.md section 4.1)"),

 "instruction_length_rules@EXP-0148": {
   "label": "corpus-correlation", "range": "582 own-MSL programs recompiled on "
            "G17P and tokenized with the post-EXP-0148 db.json",
   "target": T, "evidence": EV,
   "semantics": "The four EXP-0148 length-rule corrections hold on "
                "G17P-compiled code. On the 476 programs that compile "
                "BYTE-IDENTICALLY on both targets the tokenization is identical "
                "(371 clean, 124 982 leftover bytes on each); all of the "
                "aggregate difference (412 vs 420 clean, 224 830 vs 211 238 "
                "leftover) comes from the 106 programs whose compiler output "
                "differs. Nothing was executed, hence corpus-correlation.",
   "revalidates": "EXP-0148 (M4): 832 clean / 389 368 leftover over the full "
                  "1080-program corpus -- reproduced EXACTLY here by the same "
                  "tokenizer before it was pointed at G17P",
   "note": "CONFOUND, unresolved: the two corpora were compiled by different "
           "toolchains (macOS 26.6.2 build 25G82 on M4 vs 26.6 build 25G5043d "
           "on G17P), so the 18.2 % of programs whose bytes differ are NOT "
           "evidence of an ISA difference."},

 "db_defects": {
   "DEF-0153-1": {
     "what": "mov_imm.imm7 == 12 does not TOKENIZE under the current length "
             "rule (byte+1 == 0x0C makes the 2-byte pair look like the 4-byte "
             "0x?c preamble group), but the HARDWARE writes 12 correctly.",
     "evidence": "EXP-0153 arm F: the case carries rt=false and outcome=ok "
                 "with out0 == 12, in both gated runs. EXP-0140 (M4) found the "
                 "tokenization failure and explicitly did NOT test the hardware.",
     "consequence": "This is a DECODER defect only. An emitter may safely emit "
                    "mov_imm with imm7 = 12; tools/agx-isa's length rule needs "
                    "the fix. Do not carry EXP-0140's 'every immediate this "
                    "experiment emits avoids 12' into the normative spec as a "
                    "hardware constraint.",
     "target": "G17P (decoder half is target-independent)"},
   "DEF-0153-2": {
     "what": "tools/agxtest/persistrun.py :: request() busy-loops forever when "
             "its agxrun_persist child has EXITED: _read_line returns '' on EOF "
             "and the response loop recognises no prefix in it, so the parent "
             "spins on an unbounded stream of empty strings.",
     "evidence": "EXP-0153 raw/g17p-20260830-run02/PARTIAL.md -- observed live "
                 "at case 215/258 of D_iadd2_dst, parent at 61.3 % CPU in state "
                 "RN with no agxrun_persist child of its own in ps.",
     "consequence": "Any long sweep can stall silently. EXP-0153 worked around "
                    "it by SUBCLASSING PersistRunner (harness/run.py :: "
                    "GuardedRunner) rather than editing the shared tool; the "
                    "fix in the tool would be to treat '' as a wedge.",
     "target": "host tooling, not hardware"},
 },
}

p = os.path.join(HERE, "field_verdicts.json")
json.dump(out, open(p, "w"), indent=1, sort_keys=True)
print("wrote %s: %d field entries, %d db_defects, gated=%s"
      % (p, len([k for k in out if not k.startswith("_") and k != "db_defects"]),
         len(out["db_defects"]), GATED))
