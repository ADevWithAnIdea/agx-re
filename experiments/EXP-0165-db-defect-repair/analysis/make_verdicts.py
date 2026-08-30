#!/usr/bin/env python3
"""EXP-0165: re-express EXP-0161's 20 HELD-BACK field verdicts against the
REPAIRED tools/agx-isa/db.json descriptor, in the flat <mnemonic>.<field> schema
of experiments/FIELD-SWEEP-PROTOCOL.md section 5.

Only what the existing raw data actually supports is carried across.  Where the
repair moved a NAME to a different byte, the verdict that follows the name is the
one measured on THAT byte -- not the one that used to carry the name.  Where the
repair merged or split a field, the `range` says exactly which values were
exercised and which were not.

  python3 analysis/make_verdicts.py > analysis/field_verdicts.json
"""
from __future__ import print_function
import hashlib, json, os

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
DB = os.path.join(REPO, "tools", "agx-isa", "db.json")
EV = ["EXP-0161", "EXP-0165"]

INERT = ("HW-TESTED INERT over the whole exercised range: every value reproduces "
         "the unmutated result exactly. ")

V = {}

# ---------------------------------------------------------------------------
# fspecial -- three names moved bytes (DEF-0161-1). The verdict follows the BYTE.
# ---------------------------------------------------------------------------
V["fspecial.fn_hi"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="A18",
    range="byte0 bit 7: 0..1 dense in three carriers (D_FSPEC_INPLACE, "
          "D3_FSPEC_SYNTH, D2_FSPEC_LOG2) x two gated runs",
    note="POSITION UNCHANGED. HW-CONFIRMED BY COMPUTED VALUE on G17P: with all "
         "other bytes held, fn_hi=0 computes log2 and fn_hi=1 computes exp2 at "
         "fnclass 2 -- so the enum is confirmed by the value the SFU produced, "
         "not by a byte pattern.")

V["fspecial.fnclass"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="A18",
    range="byte+1 low nibble: 0..15 dense in three carriers x two gated runs",
    note="POSITION UNCHANGED. Map measured BY COMPUTED VALUE. fn_hi=1 (0xaf): "
         "class&3 = 1 -> rsqrt, 2 -> exp2, 3 -> rsqrt, 0 -> +inf for every input. "
         "fn_hi=0 (0x2f): 0 -> rint, 1 -> rsqrt, 2 -> log2, 3 -> NaN for 11 of 12 "
         "positive-finite inputs. Bit 3 is a DON'T-CARE (v and v+8 identical in "
         "all 8 pairs, three carriers). Bit 2 is NOT: live at class&3 = 0 on both "
         "datapaths (4/12 store nothing) and at class&3 = 1 on 0x2f (5/13 FAULT); "
         "inert elsewhere. This CORRECTS EXP-0161's db_defects DEF-0161-3, which "
         "generalised 'only the low two bits are live' from the 0xaf carrier "
         "alone (EXP-0165 analysis/rederive_def3_fnclass.py).")

V["fspecial.src_ext"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="M4",
    range="byte+1 HIGH nibble: 0..15 dense (all 16 values) in two carriers "
          "(D_FSPEC_INPLACE, D3_FSPEC_SYNTH) x two gated runs",
    note="NAME MOVED BY DEF-0161-1. This entry now labels byte+1's high nibble, "
         "which db.json called `dst` until EXP-0165. " + INERT +
         "All 16 values give a 16-register dump byte-identical to the baseline in "
         "both gated runs, and the result always lands in the same register, so "
         "this nibble is NOT the destination and NOT a source extension. The name "
         "is historical: a db.json field cannot be renamed without editing "
         "validation.json in the same commit. An emitter may write any value; 0 is "
         "what the compiler writes.")

V["fspecial.src_cache"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="tokenization-only", prior_target="M4+A18",
    range="byte+2: 0..255 dense in two carriers x two gated runs",
    note="POSITION UNCHANGED. CARRIER-DEPENDENT: accepted set is "
         "(v & 0x02) == 0x02 (128 of 256) in D_FSPEC_INPLACE, where the operand "
         "comes straight from a device_load, and fully inert (256 of 256) in "
         "D3_FSPEC_SYNTH. Do not assume inert.")

V["fspecial.dst"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="M4",
    range="byte+3: 0..191 dense (192 values) in two carriers x two gated runs; "
          "192..255 exercised separately (64 values x 3 attempts) and is a "
          "do-not-emit region",
    note="NAME MOVED BY DEF-0161-1: byte+3 is the DESTINATION register, packed "
         "reg = v >> 1. Accept rule (the values that leave the result where the "
         "baseline put it) is exactly (v & 0xFE) == 0x00 -- an exhaustive search "
         "over all 256 candidate masks returns that one and no other. Destination "
         "map from the 16-register dump: 28/28 fit, 0 misfits, in BOTH gated runs "
         "(v = 0..29 -> r0..r14; v = 12/13 write r6, whose seed already equals "
         "rsqrt(seed[r0]), so the write is invisible -- a seed aliasing artefact, "
         "not a misfit). 20/20 GENERATED `r_i = rsqrt(r_j)` encodings pass. Bit 0 "
         "is HW-tested don't-care and is NOT the project-standard is32 bit (the "
         "compiler's own f32 rsqrt encodes byte+3 = 0x00). v >= 192 names r96+, "
         "outside the 96-GPR file: 45 of those 64 values gave a genuine "
         "kIOGPUCommandBufferCallbackErrorHang, 19 were only ever observed as "
         "innocent victims, and none ever worked. NEVER EMIT v >= 192. "
         "(EXP-0165 analysis/rederive_def1_fspecial.py, def1_summary.py, "
         "rederive_gen03.py.)")

V["fspecial.src_class"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="M4",
    range="byte+4: 0..255 dense in two carriers x two gated runs",
    note="POSITION UNCHANGED. Accepted set fits (v & 0x02) == 0x02, 128 of 256, "
         "identically in both carriers: exactly one live bit, and clearing it "
         "makes the instruction silently write zero.")

V["fspecial.src"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="M4",
    range="byte+5: 0..255 dense in two carriers x two gated runs",
    note="NAME MOVED BY DEF-0161-1: byte+5 is the SOURCE register, packed "
         "reg = v >> 2 (bits 0-1 don't-care). Accept rule is exactly "
         "(v & 0xFC) == 0x00, the unique separating mask over all 256 candidates. "
         "Source map from the 16-register dump: 60/60 fit, 0 misfits, in BOTH "
         "gated runs (v = 0..59 -> r0..r14), each source identified twice over -- "
         "the computed rsqrt matches that register's seed AND that register is "
         "released to zero (56/56 where src != dst). Reaches r0..r63; r15..r63 "
         "executed without fault but are unverifiable in this carrier. 20/20 "
         "GENERATED encodings pass.")

V["fspecial.fnsel"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="tokenization-only", prior_target="M4+A18",
    range="byte+6: 0..255 dense in three carriers x two gated runs",
    note="POSITION UNCHANGED. Accepted set fits (v & 0x99) == 0x90, 16 of 256, "
         "IDENTICAL in all three carriers.")

V["fspecial.precsel"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="tokenization-only", prior_target="M4+A18",
    range="byte+7: 0..255 dense in three carriers x two gated runs",
    note="POSITION UNCHANGED. (v & 0x64) == 0x40, 32 of 256, in the two natural "
         "carriers; the synthesized carrier is looser ((v & 0x60) == 0x40, bit 2 "
         "don't-care, 64 of 256). Emit the tighter rule.")

V["fspecial.roundmode"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="A18",
    range="byte+8: 0..255 dense in three carriers x two gated runs",
    note="POSITION UNCHANGED. DEF-0161-4, re-derived in EXP-0165 with an explicit "
         "math.isnan test rather than a tolerance compare: on the rsqrt (0xaf) and "
         "log2 (0x2f) datapaths byte+8 has exactly ONE live bit -- bit 0 -- and "
         "setting it returns NaN in ALL 12 output lanes for EVERY input. 128/128 "
         "odd values all-NaN and 128/128 even values bit-matching the baseline, in "
         "two carriers x two gated runs, with no exceptions. **DO NOT EMIT bit 0.** "
         "The 0/2/4/6 round-mode enum is a claim about the DIRECT ROUND family "
         "only; on these two datapaths 2/4/6 are indistinguishable from 0, and the "
         "round-family arm (D4_FSPEC_FLOOR) was built but never run.")

V["fspecial.sched_flag"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="tokenization-only", prior_target="M4+A18",
    range="byte+9: 0..255 dense in two carriers x two gated runs",
    note="POSITION UNCHANGED. " + INERT + "All 256 values accepted in both "
         "carriers. Role UNKNOWN -- any value is safe, but do not synthesize a "
         "meaning for it.")

# ---------------------------------------------------------------------------
# fspecial_est -- descriptor UNCHANGED by this repair; verdicts pass through
# verbatim from EXP-0161 (this experiment re-derived none of them).
# ---------------------------------------------------------------------------
V["fspecial_est.dst"] = dict(
    label="hardware-run", target="G17P", evidence=["EXP-0161"],
    prior_label="hardware-run", prior_target="G17P",
    range="E2_FSPEC_EST_RCP: 0..15 (16 values, dense) / E_FSPEC_EST: 0..15 "
          "(16 values, dense)",
    note="PASSED THROUGH from EXP-0161 unchanged; the fspecial_est descriptor is "
         "untouched by the EXP-0165 repair and EXP-0165 did not re-derive it.")

V["fspecial_est.b4"] = dict(
    label="isolated-byte-diff", target="G17P", evidence=["EXP-0161"],
    prior_label="tokenization-only", prior_target="M4+A18",
    range="E2_FSPEC_EST_RCP: 0..252 (66 values) / E_FSPEC_EST: 0..255 "
          "(256 values, dense)",
    note="PASSED THROUGH from EXP-0161 unchanged. E2_FSPEC_EST_RCP: accepted set "
         "fits (v & 0x03) == 0x00 (62 of 66 values) | E_FSPEC_EST: accepted set "
         "fits (v & 0x03) == 0x00 (64 of 256 values).")

V["fspecial_est.b5"] = dict(
    label="hardware-run", target="G17P", evidence=["EXP-0161"],
    prior_label="tokenization-only", prior_target="M4+A18",
    range="E2_FSPEC_EST_RCP: 0..253 (203 values) / E_FSPEC_EST: 0..255 "
          "(256 values, dense)",
    note="PASSED THROUGH from EXP-0161 unchanged. Accepted set fits "
         "(v & 0xE0) == 0xC0 in both carriers (24 of 203 / 32 of 256).")

V["fspecial_est.srcA"] = dict(
    label="untested", target="G17P", evidence=["EXP-0161"],
    prior_label="isolated-byte-diff", prior_target="G17P",
    range="E2_FSPEC_EST_RCP: 0..255 (251 values) / E_FSPEC_EST: 0..255 (256 values)",
    note="PASSED THROUGH from EXP-0161 unchanged, INCLUDING ITS DELIBERATE "
         "NON-PROMOTION. Inert over all 256 values in BOTH carriers -- but both are "
         "PRECISE (Newton-Raphson) reciprocal lowerings and NR converges from a "
         "wrong seed, so the two carriers share the confound and are one "
         "observation, not two. WARNING TO THE MERGER: this is WEAKER than the "
         "recorded label and work/merge_verdicts.py will refuse it without "
         "--allow-downgrade. That refusal is correct -- decide it by hand.")

V["fspecial_est.subop"] = dict(
    label="untested", target="G17P", evidence=["EXP-0161"],
    prior_label="hardware-run", prior_target="M4",
    range="E2_FSPEC_EST_RCP: 0..255 (199 values) / E_FSPEC_EST: 0..255 (256 values)",
    note="PASSED THROUGH from EXP-0161 unchanged, INCLUDING ITS DELIBERATE "
         "NON-PROMOTION and the same NR confound: every value of the byte still "
         "yields the correct refined result because the Newton-Raphson iteration "
         "corrects the seed. The prior M4 `hardware-run` label (EXP-0138, dense "
         "0..255) stands untouched. WARNING TO THE MERGER: weaker than the recorded "
         "label; merge_verdicts.py will refuse it without --allow-downgrade.")

# ---------------------------------------------------------------------------
# mov_zext16 -- DEF-0161-2 moved the register into byte0 and merged byte+1.
# ---------------------------------------------------------------------------
V["mov_zext16.src_reg"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="M4",
    range="byte0 HIGH nibble: all 16 values exercised, as the complete 0..255 "
          "byte0 raw-byte probe in B_ZEXT_SYNTH (run01 + run02, judged by the full "
          "16-register architectural dump), plus 16 GENERATED encodings "
          "(gen01/gen02/gen03)",
    note="NAME RE-POINTED BY DEF-0161-2: this entry now labels byte0's HIGH "
         "NIBBLE, the ONE register the instruction uses as both source and "
         "destination (r[n] = r[n] & 0xFFFF). db.json modelled that nibble as part "
         "of a fixed match (byte0 == 0x13) until EXP-0165. Measured: byte0 = 0xN3 "
         "narrows r[N] AND NOTHING ELSE for N = 0..10 -- 11/11 fits, 0 misfits, in "
         "both gated runs -- and N = 0xB..0xF execute as a NO-OP (no register "
         "changes at all), confirmed 4 independent times each. No byte0 whose LOW "
         "nibble is not 3 ever performs the narrow (all 16 low-nibble buckets "
         "checked). GENERATED: 11 of 16 `r[n] = r[n] & 0xFFFF` encodings pass a "
         "host-computed 16-register prediction; the 5 failures are exactly the "
         "no-op nibbles. ONE ANOMALY, recorded not smoothed: nibble 0x8 narrowed "
         "correctly in 4 of 5 observations and was a no-op once (gen03). "
         "The INERTNESS evidence that used to sit under this name (byte+1 bits "
         "0-6) has moved to `mov_zext16.src_flag`, which now covers all of byte+1. "
         "(EXP-0165 analysis/rederive_def2_zext.py.)")

V["mov_zext16.src_flag"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="M4",
    range="byte+1, now the WHOLE byte (8 bits). Exercised: bits 0-6 dense 0..127 "
          "with bit 7 = 0 (128 values), plus bit 7 dense 0..1 with bits 0-6 = 0 "
          "(2 values) -- 129 of the 256 byte values, in TWO independent register "
          "forms (B_ZEXT_SYNTH r1 and B2_ZEXT_SYNTH_R5 r5) x two gated runs each. "
          "The 127 combinations with bit 7 = 1 AND bits 0-6 != 0 were NOT "
          "exercised.",
    note="FIELD MERGED BY DEF-0161-2: the old `src_reg` (bits 0-6) and `src_flag` "
         "(bit 7) are one inert byte, and db.json's name budget (a new field name "
         "hard-fails validate_labels.py without a validation.json edit) forced the "
         "merge onto this name. " + INERT + "In every one of the 129 exercised "
         "values, in all four gated sweeps, the 16-register dump is identical to "
         "the baseline -- in a carrier where the instruction is demonstrably live "
         "(its byte0 := 0x00 falsifier fires as `wrong_value`) and where fifteen "
         "device_loads and a sentinel store separate the source from the "
         "instruction, so ALU forwarding cannot explain it. This CLOSES EXP-0146's "
         "open question as '(a) byte+1 is not a source-register selector'. It is "
         "also NOT a flag; the name is historical. EXP-0146's own carrier is dead: "
         "its byte0 := 0x00 falsifier scores `ok` there.")

V["mov_zext16.subform"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="M4",
    range="byte+2: 0..255 dense in B2_ZEXT_SYNTH_R5 (256 values) and B_ZEXT_SYNTH "
          "(221 of 256 cleanly observed), x two gated runs each",
    note="POSITION UNCHANGED. Accepted set fits (v & 0xC7) == 0x00, exactly 8 of "
         "256, IDENTICALLY in both register forms. NOT folded into `match`: doing "
         "so was measured (EXP-0165 work/cand2) and it steals 70 firings from "
         "`frame_marker`, whose 8-bit byte0 match would lose the specificity "
         "tie-break.")

V["mov_zext16.extend"] = dict(
    label="hardware-run", target="G17P", evidence=EV,
    prior_label="corpus-correlation", prior_target="M4",
    range="byte+3 bits 3-7 (the field was narrowed from 8 bits to 5): all 32 "
          "values of the surviving 5 bits exercised, as part of the dense 0..255 "
          "byte+3 sweep in both register forms x two gated runs; all 32 accepted",
    note="FIELD NARROWED BY DEF-0161-2. The dense byte+3 sweep accepts exactly the "
         "32 values with (v & 0x07) == 0x01 and no others, so byte+3's LOW 3 BITS "
         "are the zero-extend companion discriminator and are now part of `match`; "
         "the remaining 5 bits are HW-tested free. The old 8-bit `extend` verdict "
         "is not translated across unchanged -- 3 of its 8 bits became match bits.")

# ---------------------------------------------------------------------------
# EXP-0160 / EXP-0157 repairs (second db.json write).  Only names whose BYTE
# changed, or that did not exist before, need a re-expressed verdict; fields that
# merely gained a `note` keep the row already in validation.json.
# ---------------------------------------------------------------------------
EV60 = ["EXP-0160", "EXP-0165"]

V["imad.srcB"] = dict(
    label="hardware-run", target="G17P", evidence=["EXP-0154"] + EV60,
    prior_label="hardware-run", prior_target="G17P",
    range="byte+6: 0..255 dense (256 values, EXP-0154), plus an 11-point x "
          "12-point 2-D probe against byte+7 in TWO independent seed sets "
          "(EXP-0160)",
    note="NAME MOVED BY DEF-0160-6: this entry now labels byte+6, which EXP-0154 "
         "swept under the name `srcC_lo` and labelled from its ok-set alone "
         "without identifying a role. The role is now identified: byte+6 is a "
         "MULTIPLICAND REGISTER SELECTOR, reg = v >> 3; bit 0 = 1 makes that "
         "source read 0; bits 1 and 2 are inert. EXP-0154's ok-set {0x0, 0x2, "
         "0x4, 0x6} is exactly the four values naming r0. Re-derived in EXP-0165 "
         "by solving r0 = m*(seed[a]*seed[b]) + A with BOTH multiplicands free "
         "and requiring one solution to satisfy both seed sets: byte+6 = 0x10 "
         "pins r2 UNIQUELY, and 0x00/0x02/0x04 -> r0, 0x08 -> r1, 0x20 -> r4, "
         "0x40 -> r8 all contain the predicted register (10 of 11 probed values; "
         "the eleventh, 0xFF -> r31, lies outside the 16 seeded registers and is "
         "unmeasurable). **db.json modelled NO first multiplicand at all before "
         "this.**")

V["imad.srcC_lo"] = dict(
    label="hardware-run", target="G17P", evidence=["EXP-0154"],
    prior_label="hardware-run", prior_target="G17P",
    range="byte+5: 0..255 dense (256 values, EXP-0154)",
    note="NAME MOVED BY DEF-0160-6: this entry now labels byte+5, which EXP-0154 "
         "swept under the name `srcB`. The label is unchanged and the sweep is "
         "unchanged -- only which byte the name points at. **ROLE UNRESOLVED**: "
         "in the EXP-0160 anchor byte+5 = 0x08 while the second multiplicand is "
         "demonstrably r2, which the project-standard (reg<<1)|size packing would "
         "read as r4, so either the packing here is reg<<2 or the second "
         "multiplicand is selected elsewhere. It is NOT the low half of an "
         "immediate addend -- there is no immediate addend (DEF-0160-3). Do not "
         "emit a register number here.")

V["iminmax.srcA"] = dict(
    label="hardware-run", target="G17P", evidence=["EXP-0154"] + EV60,
    prior_label="hardware-run", prior_target="G17P",
    range="byte+1: 0..255 dense (256 values, EXP-0154, swept under the name "
          "`dst_full`)",
    note="NAME MOVED BY DEF-0160-2 (a 3-cycle over byte+1/+3/+5). byte+1 is the "
         "FIRST source descriptor, (reg<<1)|size -- the falu2 slot layout. "
         "Identified in EXP-0165 from EXP-0160's anchor `02 01 1e 05 07 00`, "
         "which computes imin(r0, r2) -> r0 in BOTH seed sets (10 and 7) with "
         "byte+1 = 0x01 naming r0. The dense sweep behind the label is EXP-0154's "
         "byte+1 sweep; the ROLE is EXP-0160/EXP-0165.")

V["iminmax.srcB"] = dict(
    label="hardware-run", target="G17P", evidence=["EXP-0154"] + EV60,
    prior_label="hardware-run", prior_target="G17P",
    range="byte+3: 0..255 dense (256 values, EXP-0154, swept under the name "
          "`srcA`)",
    note="NAME MOVED BY DEF-0160-2. byte+3 is the SECOND source descriptor, "
         "(reg<<1)|size. Identified by a RELEASED-REGISTER observation: at the "
         "anchor value 0x05 the register it names (r2) comes back zeroed in both "
         "seed sets, which is release-on-read and identifies it as an operand. "
         "**WARNING TO THE MERGER: validation.json's existing `iminmax.srcB` row "
         "carries EXP-0160's byte+5 sweep. That evidence now belongs to "
         "`iminmax.dst_full`; this row replaces it.**")

V["iminmax.dst_full"] = dict(
    label="hardware-run", target="G17P", evidence=EV60,
    prior_label="hardware-run", prior_target="G17P",
    range="byte+5: 0..255 dense (all 256 values), each under TWO independent seed "
          "sets x two gated runs",
    note="NAME MOVED BY DEF-0160-2: this entry now labels byte+5, which EXP-0160 "
         "swept under the name `srcB`. **It is NOT a register selector**: bits 3, "
         "5, 6 and 7 are INERT (0 of 512 flip-pairs differ each, re-measured in "
         "EXP-0165) and no value->register model fits (reg = v>>1 and reg = v>>2 "
         "each explain only 32 of 256 cases). Its live bits are 0, 1, 2 and 4 and "
         "its anchor value 0xc0 is falu2's standard `mods` default, so it is the "
         "SOURCE-CLASS / MODIFIER byte. The name `dst_full` is historical and "
         "wrong; a db.json field cannot be renamed without editing validation.json "
         "in the same commit.")

V["sfu_marker.b0_hi"] = dict(
    label="hardware-run", target="G16G+G17P", evidence=["EXP-0146", "EXP-0157",
                                                        "EXP-0165"],
    prior_label="untested", prior_target="M4+A18",
    range="byte+0 bits 3-7, exercised as the dense 0..255 byte+0 sweep: 512 cases "
          "over two gated runs on M4/G16G (EXP-0146) and reproduced "
          "byte-for-byte on G17P in THREE independent carriers (EXP-0157: "
          "fast::sin, fast::cos, sin+cos+tan)",
    note="NEW FIELD, added to db.json by EXP-0165. The descriptor previously "
         "claimed a byte-INVARIANT token with ZERO fields, so no evidence about "
         "it could be recorded at all. Measured: byte+0 accepts only "
         "(v & 0xF7) == 0x06 (2 of 256) -- 62 values return a WRONG value and 192 "
         "silently zero -- so within this 5-bit field only its bit 0 (byte bit 3) "
         "is free and bits 4-7 of the byte must be 0. Setting byte+0 to 0x00 "
         "FLIPS THE SIGN of fast::sin on exactly the rows whose argument requires "
         "range reduction (|x| > pi/2), leaving the small-argument rows correct: "
         "at least one live bit is a quadrant/sign control.")

V["sfu_marker.b1_hi"] = dict(
    label="hardware-run", target="G16G+G17P", evidence=["EXP-0146", "EXP-0157",
                                                        "EXP-0165"],
    prior_label="untested", prior_target="M4+A18",
    range="byte+1 bits 2-7, exercised as the dense 0..255 byte+1 sweep: 512 cases "
          "over two gated runs on M4/G16G (EXP-0146), reproduced on G17P in three "
          "independent carriers (EXP-0157)",
    note="NEW FIELD, added to db.json by EXP-0165. byte+1 accepts only "
         "(v & 0x13) == 0x02 (32 of 256), so bits 2, 3, 5, 6 and 7 of the byte "
         "are free and bit 4 (this field's bit 2) must be 0. Both bytes of this "
         "'byte-invariant marker' are load-bearing.")

# ---------------------------------------------------------------------------
doc = {"_meta": {
    "experiment": "EXP-0165-db-defect-repair",
    "target": "G17P",
    "db_sha256": hashlib.sha256(open(DB, "rb").read()).hexdigest(),
    "note": "The 20 verdicts EXP-0161 held back, RE-EXPRESSED against the db.json "
            "repaired by EXP-0165. No new hardware was run: every number here comes "
            "from EXP-0161's immutable raw/ trees, re-derived by the scripts in "
            "EXP-0165/analysis/. Three fspecial names now label DIFFERENT BYTES "
            "(DEF-0161-1) and two mov_zext16 fields were re-pointed / merged / "
            "narrowed (DEF-0161-2) -- read each `note` before merging. "
            "fspecial_est.srcA and .subop are deliberate NON-promotions carried "
            "through verbatim and will trip merge_verdicts.py's downgrade guard; "
            "that refusal is correct and needs a human decision.",
    "second_write": "EXP-0165 made a SECOND db.json write for the EXP-0160 and "
                    "EXP-0157 defects. imad.srcB/.srcC_lo and iminmax.srcA/.srcB/"
                    ".dst_full are NAME->BYTE re-points of rows already in "
                    "validation.json: merging these entries is REQUIRED or those "
                    "rows describe the wrong byte. sfu_marker.b0_hi/.b1_hi are NEW "
                    "fields; until they are merged, validate_labels.py exits 1 with "
                    "exactly those two `MISSING label` errors and nothing else "
                    "(analysis/revert_sfu_marker_fields.py backs the two fields out "
                    "if you want it green first).",
    "not_relabelled": "n3_mov.dst / .srcA_reg / .srcA_uni are NOT relabelled here. "
                      "The hardware evidence bears on them (they are the same "
                      "compact 4-byte family), but under the repaired match the "
                      "tested encodings decode as `mov_zext16`, so a hardware label "
                      "on n3_mov's fields would not be supported by an encoding "
                      "that descriptor actually claims. Their db.json semantics "
                      "were updated; their labels were not.",
}}
doc.update(V)
print(json.dumps(doc, indent=1, sort_keys=True))
