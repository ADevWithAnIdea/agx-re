#!/usr/bin/env python3
"""EXP-0181 Task 1 -- build analysis/instruction_labels.json.

Per weak `_instruction` label: the recommendation, the current value, the machine-gathered
evidence (from dispatch_evidence.json / dispatched_bytes_check.json / anchor_check.json /
anchor_reachability.json), a one-line reason with its citation, and the refuter.

The decision rule is PRE_REGISTRATION.md R1-R5, frozen before any per-instruction ruling.
The per-instruction rulings themselves are MINE -- they are judgements over the committed
record, not a computation -- so each carries the citation that justifies it and the
observation that would overturn it.  Nothing here edits validation.json.

Usage:  python3 analysis/make_instruction_labels.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
VAL = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "validation.json")))
DISP = json.load(open(os.path.join(HERE, "dispatch_evidence.json")))
BYTES = json.load(open(os.path.join(HERE, "dispatched_bytes_check.json")))
REACH = json.load(open(os.path.join(HERE, "anchor_reachability.json")))

HR, IBD, CC, TO = "hardware-run", "isolated-byte-diff", "corpus-correlation", "tokenization-only"

# mnemonic -> (recommended, target, evidence, range, rule, reason, refuter, caveats[])
R = {}

def add(m, lab, tgt, ev, rng, rule, reason, refuter, caveats=()):
    R[m] = dict(recommended_label=lab, recommended_target=tgt, recommended_evidence=list(ev),
                recommended_range=rng, decision_rule=rule, reason=reason, refuter=refuter,
                caveats=list(caveats))

# ---------------------------------------------------------------- R1 hardware-run
add("bf_add_dst", HR, "G17P", ["EXP-0156"],
    "native bf16 add at dst nibble 2; op-select and source-modifier proven by value; 4152 cases, 2 gated runs",
    "R1",
    "EXP-0156 scored the UNMUTATED instruction against a host-computed EXACT bf16 bit pattern on every "
    "lane in both gated runs (out = bf16(a+b), 0x40103fc0), settled the ROUNDING MODE with a "
    "pre-registered two-oracle tie probe (RNE matched, truncate failed), and proved the op-select BY "
    "VALUE (byte+2 0x1c->0x1d turns a+b into a*b, matching the MUL oracle while its paired control "
    "failed the ADD oracle) plus byte+5 bit3 = a-b. Identity and semantics are hardware facts, not "
    "corpus fits.",
    "a carrier in which byte+2 0x1c does NOT compute a+b, or a re-run in which the tie vector returns "
    "the truncate result.",
    ["`dst` accepted exactly ONE value (v == 0x21) in that carrier, so the dst-GENERALISATION this "
     "descriptor's name claims (bf_alu r1 -> r0..r15) is NOT demonstrated -- only dst nibble 2 ran.",
     "the anchor does not tokenize: DEF-0171-2 (isadb.py's low-nibble-1 length rule is gated on "
     "byte+1 in {0x02,0x04}; G17P emits 0x00). The descriptor still WINS those bytes on specificity "
     "once a length exists (EXP-0175 measured 12 match bits vs bf_alu8_var's 4).",
     "the byte+3/byte+4 value -> register map is explicitly NOT claimed (EXP-0156 section 12.3)."])

add("bf_fma_dst", HR, "G17P", ["EXP-0156", "EXP-0171"],
    "native bf16 fma at dst nibble 2; 2654 cases in 2 gated runs, plus EXP-0171's dense byte+6..+9 tail",
    "R1",
    "Same instrument as bf_add_dst: EXP-0156's unmutated bf_fma carrier reproduced the host-computed "
    "exact bf16 pattern for out = bf16(a*b+c) (0x3f803f40) on every lane in both gated runs, with the "
    "10-byte fma form separated from the 8-byte add by a pre-registered byte+2 control that broke as "
    "predicted.",
    "a run in which the bf_fma carrier's unmutated bytes do not reproduce the a*b+c oracle.",
    ["`dst` accepted one value (0x21); 44 of 256 fault. The dst generalisation is not demonstrated.",
     "anchor does not tokenize (DEF-0171-2), as for bf_add_dst."])

add("cvt_bf16", HR, "G17P", ["EXP-0162", "EXP-0144"],
    "31 semantic vectors on the unmutated instruction + dense sweeps of all six free bytes, 2 gated runs",
    "R1",
    "EXP-0162 ran 31 host-oracle SEMANTIC VECTORS on the unmutated cvt_bf16 in c_f2bf and established "
    "float32->bfloat16 round-to-nearest-EVEN by REFUTING three named alternatives (TIES_DOWN, TRUNC, "
    "RNA) with tie vectors, plus f32 denormal flush-to-zero. That is the conversion this descriptor "
    "names, measured, not correlated.",
    "a tie vector returning the TIES_DOWN or TRUNC result, or a denormal that does not flush.",
    ["EXP-0162 section 2.3: this descriptor's own match constant [32,8,1] (byte+4 == 0x01) names a "
     "value THE HARDWARE REJECTS, and the HW anchor 0101148105024000 has byte+4 == 0x05. The match is "
     "wrong and the anchor does not tokenize. Recorded, not fixed here -- EXP-0162 says the fix needs "
     "a length-rule change it does not own.",
     "`srcw`'s documented enum is wrong for this form (EXP-0162 finding 4)."])

add("cvt_f2h", HR, "M4+A18", ["EXP-0013", "EXP-0144", "EXP-0168"],
    "half(3.5)/half(65504)/half(0.1) exact on hardware; then 5 bytes dense 0..255 on M4 and byte+2 dense on G17P",
    "R1",
    "The oldest and plainest case in the set: EXP-0013 read back half(3.5), half(65504) and half(0.1) "
    "as the EXACT IEEE fp16 values from hardware -- the instruction's whole documented semantics, "
    "confirmed by value. EXP-0144 then swept five of its bytes dense 0..255 (6555 cases) and EXP-0168 "
    "re-measured byte+2 on G17P at 99.609% cross-run agreement with 221 of 256 values moving. Its "
    "anchor 110114810402 decodes back to cvt_f2h.",
    "a G17P run in which half(x) does not return the IEEE fp16 value; the fp16 claim has never been "
    "re-measured on G17P for THIS descriptor (only byte+2 was).",
    ["the `_instruction` target should read M4+A18, not the current A18 -- the numeric proof is "
     "EXP-0013 (A18) and the dense sweeps are EXP-0144 (M4) + EXP-0168 (G17P)."])

add("cvt_f2h_dst", HR, "G17P", ["EXP-0162", "EXP-0144"],
    "5 semantic vectors matching IEEE RNE fp16 exactly on the unmutated instruction at dst nibble 12, 2 gated runs",
    "R1",
    "EXP-0162's five semantic vectors match IEEE fp16 round-to-nearest-even EXACTLY on the unmutated "
    "cvt_f2h_dst, and all six of its bytes were swept dense 0..255 (1325 cases) with the outcome "
    "classes separated (86 fault, 115 silent zero). This is the same fp32->fp16 narrowing EXP-0013 "
    "validated for the byte0==0x11 sibling, executing here at a DIFFERENT destination nibble -- which "
    "is the generalisation the descriptor exists to make.",
    "a semantic vector returning a non-RNE fp16 value, or a demonstration that the c1 anchor is really "
    "the r1 form aliased.",
    ["`dst` reproduced the oracle at 1 of 16 nibbles -- expected, because the consumer reads a fixed "
     "register, but it means the destination is not shown to be CHOOSABLE.",
     "the anchor c10114810402 does not tokenize (length rule); the corpus reaches this descriptor at "
     "other byte+1/byte+2 combinations (01011c8100c2, 31053c810422, ...)."])

add("cvt_i2f", HR, "M4+A18", ["EXP-0013", "EXP-0144"],
    "float(-3)/float(1000000) exact + the signed/unsigned bit proven by splice; then 6 bytes dense 0..255 on M4",
    "R1",
    "EXP-0013 read float(-3) and float(1000000) back exactly AND proved the descriptor's own "
    "sign-flag semantics by value: splicing byte+7 0x60->0x20 converts -1 as UNSIGNED "
    "(4294967295 -> ~4.29e9) on hardware. EXP-0144 then swept all six bytes dense 0..255 (5475 cases) "
    "under revalidation. Anchor a707561802008e60 decodes back to cvt_i2f.",
    "a run in which byte+7 bit6 does not switch signed/unsigned interpretation.",
    ["byte+3 = dst<<1 and byte+5 = src<<2 come from a COMPILE-ONLY byte-diff (EXP-M4-13 R9, no GPU "
     "dispatch); the sweeps show the bytes are live but do not re-derive that map."])

add("falu3", HR, "M4+G17P", ["EXP-0138", "EXP-0154", "EXP-0160"],
    "operand slots proven on M4 over 1809+2321 cases; byte+2 operation map dense 256 x 2 seed sets on G17P",
    "R1",
    "EXP-0138 HW-VALIDATED the OPERAND-SLOT model against a host oracle over 1809+2321 cases and "
    "corrected db.json's names by measurement (byte0 high nibble is the destination, byte+1/+3/+5 the "
    "sources, byte+4 the length-selecting control that re-lengths the instruction on 192 of 256 "
    "values); EXP-0160 then mapped byte+2 densely on G17P in two seed sets. Anchor 09011e0581080200 "
    "decodes back to falu3. This is a three-source float ALU proven by moving its operands and "
    "predicting the result.",
    "an operand slot that does not carry the register the EXP-0138 map assigns it.",
    ["the srcmods bit map beyond negate-product still needs a splice (db.json's own note)."])

add("falu3_ext", HR, "M4+G17P", ["EXP-0138", "EXP-0154", "EXP-0160"],
    "same operand-slot proof as falu3 (EXP-0138 explicitly extends it) plus the G17P byte+2 map; 15122 cases",
    "R1",
    "EXP-0138's operand-slot rename is recorded as applying to falu3_ext verbatim, its own baselines "
    "reproduced their oracle 3/3, EXP-0154 ran a saturate-fma carrier and EXP-0160 mapped byte+2 "
    "densely on G17P. Anchor 09011e05820802000080 decodes back to falu3_ext at length 10.",
    "a demonstration that the 10-byte form is not the same operation as the 8-byte one.",
    ["the SATURATE that distinguishes this form from falu3 is NOT proven by value: db.json's own "
     "provenance says the extended tail is raw-captured and INFERRED. `ext` is isolated-byte-diff "
     "with a non-dense sweep. If the orchestrator wants the label to certify the saturate, this one "
     "should stay at isolated-byte-diff."])

add("hminmax", HR, "G17P", ["EXP-0156"],
    "exact fp16 max AND min oracles, the op-select bit proven by value, 2608 cases in 2 gated runs",
    "R1",
    "EXP-0156's h_max carrier reproduced the host-computed exact fp16 max(a,b) pattern (0x40003c00), "
    "and byte+4's low bit 0->1 turned max into min -- matching the host MIN oracle while FAILING the "
    "MAX oracle, exactly as pre-registered. Every modelled field was measured; the accepted sets were "
    "identical in both gated runs.",
    "a carrier in which byte+4 bit0 does not select min vs max.",
    ["`dst` accepted 1 value (0x22) and `srcB` 1 value (0xC0): no operand is shown to be choosable.",
     "NEW (EXP-0181): the HW anchor 22001c0010c0 DOES NOT TOKENIZE -- the length rule returns 10 for "
     "byte0 0x22 -- while 02.. and 12.. decode at length 6. So the descriptor decodes at only 2 of 16 "
     "destination nibbles and NOT at the one that was hardware-validated. isadb.py's owner."])

add("irotate", HR, "M4+G17P", ["EXP-0033", "EXP-0146", "EXP-0154", "EXP-0172"],
    "rotate(a,5) and rotate(a,n) read back exact; then 8736 (M4) + 5634 (G17P) + 2680 (G17P) cases",
    "R1",
    "EXP-0033 read the rotate result back exactly from hardware for both a constant and a variable "
    "amount -- the documented semantics, by value -- and the single-op immediate form was separated "
    "from the multi-op dynamic lowering by byte-diff. EXP-0146/0154 then swept it densely on both "
    "targets and EXP-0172 showed byte+2 is ASYMMETRIC over its two legal values on three arms. Anchor "
    "2701560002006c00f0150900 decodes back to irotate.",
    "a rotate amount for which the single 12-byte form does not produce rotate_left.",
    ["`operands` (40-bit) and `tail` (32-bit) are MARGINAL COVERAGE ONLY -- swept byte-wise, never "
     "jointly, and neither max nor max-1 was ever encoded, so FIELD-SWEEP-PROTOCOL 3.3's w>8 bar is "
     "not met for either.",
     "DEF-0172-1: `b2`'s modelled 8-bit width is a fiction; it has one free bit."])

add("mov_imm", HR, "M4+G17P", ["EXP-0031", "EXP-0140", "EXP-0153", "EXP-0167", "EXP-0168"],
    "0..127 dense with a host oracle; and 196,114 GENERATED instances inside 233 zero-copied programs that produced their exact host oracle",
    "R1+GENERATED",
    "The strongest case in the set and the reason the orchestrator refused to gate on these labels. "
    "EXP-0031 proved the semantics by value on hardware (splicing byte+1 0x20->0x21/0x40/0x11 changes "
    "the output to 33/64/17 -- the literal, not an SR read); EXP-0140 swept dst 16/16 against a "
    "host oracle with four 12-register aliasing scans; EXP-0128/0140 corrected the immediate to SEVEN "
    "bits by measurement against a POISONED read-back and found the imm7==12 tokenization hole; and "
    "EXP-0167 ran 196,114 assembler-GENERATED mov_imm instances inside 233 zero-copied programs whose "
    "01_results.jsonl was BYTE-IDENTICAL across two isolated gated runs. `corpus-correlation` is "
    "flatly wrong for this descriptor.",
    "a generated mov_imm that does not write its literal; none has been seen in 196,114 emissions.",
    []) 

add("mov_zext16", HR, "G17P", ["EXP-0013", "EXP-0161", "EXP-0165"],
    "byte0 = 0xN3 narrows r[N] and nothing else for N = 0..10, 11/11 fits 0 misfits in both gated runs; 11 of 16 GENERATED encodings pass a 16-register host prediction",
    "R1+GENERATED",
    "EXP-0161 (independently re-derived by EXP-0165) measured the documented semantics directly -- "
    "r[n] = r[n] & 0xFFFF, in place, on the register named by byte0's HIGH nibble -- in a synthesized "
    "carrier judged by a full 16-register dump, and GENERATED 16 encodings of which 11 pass a "
    "host-computed prediction (the 5 failures are exactly the 0xB..0xF no-op nibbles, recorded). It "
    "also REFUTED the previous operand model (byte+1 is HW-tested inert over all 256 values).",
    "a nibble in 0..10 that narrows a register other than r[N], or an r[N] narrow that also touches a "
    "second register.",
    ["one anomaly is on the record rather than smoothed: nibble 0x8 narrowed correctly in 4 of 5 "
     "observations and was a no-op once (gen03).",
     "DEF-0175-1 (open): this descriptor's match does not encode its own HW-measured byte+2 accept "
     "rule, so it claims byte+2 values the hardware rejects. Not landed -- it collides with "
     "frame_marker and needs its own experiment."])

add("n3_mov", HR, "G17P", ["EXP-0174", "EXP-0175"],
    "840 GENERATED 32-bit copies over all 240 ordered (dst != src) pairs + 1680 generated half-moves, 0 failures, 2 gated runs x 2 register plans",
    "R1+GENERATED",
    "The second end-to-end generated instruction in the corpus. EXP-0174 built every byte from the "
    "descriptor's bit geometry with ZERO bytes copied from any compiled shader, ran 840 generated "
    "32-bit register copies over ALL 240 ordered (dst, src) pairs in both instruction orders and both "
    "register plans, and scored each against a full host-computed 16-register prediction: 0 failures. "
    "Its own analysis/field_verdicts.json already records `n3_mov._instruction: hardware-run "
    "(generated)`. The descriptor defect that blocked the merge (DEF-0174-1, byte+1 modelled one bit "
    "off) was re-derived and LANDED by EXP-0175.",
    "a generated (dst, src) pair whose 16-register prediction fails.",
    ["dst is a 4-bit nibble: r0..r15 only.",
     "`frame_marker` inherited the same byte+1 correction WITHOUT its own sweep and is flagged "
     "STRUCTURAL/INFERRED in db.json -- that caveat belongs to frame_marker, not here."])

add("pack_convert", HR, "M4+A18", ["EXP-0033", "EXP-0144", "EXP-0168"],
    "pack_float_to_unorm2x16 read back exact over 4 float2 inputs; then 26,160 cases on M4 with the operand roles corrected by measurement",
    "R1",
    "EXP-0033 read pack_float_to_unorm2x16 back exactly over four float2 inputs. EXP-0144 then "
    "measured the OPERAND MODEL and corrected db.json by hardware: byte+3 is the DESTINATION (the old "
    "name `src` would have sent an emitter's result to the wrong register), the sources are byte+5 "
    "(reg<<2) and byte+6 (reg<<3), and byte+9 is the FORMAT selector (0x4x snorm2x16 / 0x8x "
    "unorm2x16 / 0xcx unorm 8-bit). A correction of that kind is only possible from execution. "
    "EXP-0168 re-measured byte+7 on G17P at 100.000% agreement.",
    "a byte+9 value whose observed packing does not match the format it is said to select.",
    ["the bulk of the evidence is M4; only byte+7 has been re-measured on G17P."])

add("psel", HR, "M4", ["EXP-0010", "EXP-0140"],
    "512/512 matched the host-computed oracle on byte+3, across 2 dispatch shapes and 2 gated runs",
    "R1",
    "EXP-0010 E3 validated the grid-predicate select's BEHAVIOUR on hardware, and EXP-0140 swept "
    "`flag`, `mode` and `sel` at 256 values x 2 dispatch shapes with byte+3 matching the "
    "host-computed oracle 512/512 -- the same immediate model it proved for `sel`. The predicate "
    "select is confirmed by value, not by co-variation.",
    "a byte+3 immediate that does not appear in the selected output.",
    ["our own MSL ternaries compile to isel10, not psel, so psel has never been reached from source; "
     "every observation is a splice into a lifted carrier.",
     "the per-operand REGISTER map still needs a splice (db.json's own note); only the immediate "
     "model is established."])

add("ret_luse", HR, "G17P", ["EXP-0035", "EXP-0156"],
    "linkmode 0..255 dense (32 accepted) and tail 254/256 (12 accepted), identical accepted sets to `ret`, 2 gated runs",
    "R1",
    "EXP-0156 tested this descriptor's ENTIRE identity claim as a pre-registered control: byte+2 "
    "0x54 -> 0x56 with expect_match=True, and it matched in both gated runs -- so ret_luse really is "
    "the HW-VALIDATED `ret` (EXP-0035) with one byte changed, at the same accepted sets for both of "
    "its fields (linkmode v&0x07==0x04, tail the same 12 values). An identity claim confirmed by a "
    "pre-registered hardware control is exactly what this label is for.",
    "a linkmode or tail value accepted by `ret` and rejected by `ret_luse`, or vice versa.",
    ["'bit17 = last-use scheduling hint' remains INFERRED: the drop-in control shows the two forms "
     "are interchangeable, not what the bit schedules.",
     "EXP-0156 records ret_luse.tail's no_store/wrong_value boundary as noisy (58.2%)."])

add("sel", HR, "M4", ["EXP-0010", "EXP-0140"],
    "byte+1/+2/+3 each dense 0..255 x 2 input vectors x 2 gated runs; byte+3's immediate model matched the host oracle",
    "R1",
    "EXP-0010 E3 validated the select on hardware (a compare-immediate splice flips the CHOSEN value "
    "with no jump). EXP-0140 then refuted db.json's own field model by measurement -- `body` is not "
    "one opaque 24-bit field but three located bytes, and byte+3 is the predicate-FALSE OPERAND whose "
    "value appears in the output (255 of 128 values >= 0x80 and 1 of 128 < 0x80 matched their "
    "host-computed oracle exactly). Anchor 16c2a0c8 decodes back to sel.",
    "a byte+3 value that does not appear as the false operand.",
    ["M4 only; not re-measured on G17P."])

add("uniform_mov", HR, "M4+G17P", ["EXP-0020", "EXP-0140", "EXP-0168"],
    "usrc 0..255 dense with a host oracle (128/128 immediate-region values exact, 8/8 mapped indices returning the bound constant); dst 16 values, 214 moved, 100.000% cross-run agreement",
    "R1",
    "EXP-0140 proved the documented semantics by value: 128 of 128 immediate-region `usrc` values "
    "matched their host-computed oracle exactly and 8 of 8 mapped uniform indices returned the BOUND "
    "MAGIC CONSTANT -- i.e. byte+1 really does select the uniform read. EXP-0168 then re-measured "
    "`dst` on G17P against a fixed 16-GPR dump and a host-known seed table (214 movements, 224 "
    "distinct byte strings, 100.000% agreement) after showing EXP-0140's earlier dst arm could not "
    "have returned any other answer.",
    "a mapped uniform index that returns something other than the bound constant.",
    ["EXP-0168 also found byte+2 (not a declared field) selects the FORM and the VALUE -- 0x02 writes "
     "0x30, 0x0b writes 0x4b, 0x08 is a 16-bit-lane merge. db.json models byte+2 as a match constant, "
     "so an emitter cannot reach those forms from the tables."])

# ---------------------------------------------------------------- R2 isolated-byte-diff
add("h_coord_hi", IBD, "G17P", ["EXP-M4-13", "EXP-0157"],
    "all six bytes swept 0..255 on 2 carriers (h3mix, h4fma), 5750 cases, 2 agreeing captures",
    "R2",
    "EXP-0157 executed it in two independent half-precision carriers and showed every byte is "
    "load-bearing on the carrier's host oracle -- `srcA` is a real source-register field (240 of 255 "
    "values return a DIFFERENT non-zero result), `opsel` accepts (v & 0xd7) == 0x06 in BOTH carriers. "
    "But no claim the descriptor makes was proven BY VALUE: the 'writes the HIGH 16-bit half' "
    "semantics was demonstrated for the sibling `h_alu_hi` (EXP-0156 H-3), not for this descriptor, "
    "and 0x26-vs-0x2e (mul vs fma) was never separated by an oracle. Ran with the predicted effect at "
    "the compiler's own operand values; that is R2, not R1.",
    "an oracle-scored probe showing 0x26 and 0x2e produce mul and fma respectively -- that would "
    "lift it to hardware-run.",
    ["db.json's own provenance says 'Field semantics INFERRED'."])

add("h_coord_hi_ext", IBD, "G17P", ["EXP-M4-13", "EXP-0157"],
    "seven fields swept on ONE carrier (h3mix, anchor +40), 3795 cases, 2 agreeing captures",
    "R2",
    "Same reasoning as h_coord_hi, one rung weaker: EXP-0157 reached it in a SINGLE carrier. Its "
    "bytes are live on that carrier's oracle (`ext` faults on 128 of 233 values, `srcC` accepts one "
    "value) and its anchor 5880269081030022 decodes back to the descriptor, but one carrier cannot "
    "separate an inert field from a carrier that cannot see it -- the EXP-0155 lesson -- and nothing "
    "about the extended 3-source form was proven by value.",
    "a second, structurally different carrier reproducing the same accepted sets.",
    ["db.json: 'Operand semantics INFERRED, NOT HW-dispatch-validated' -- superseded in part by "
     "EXP-0157's dispatch, but only in part."])

add("iter_flat", IBD, "G17P", ["EXP-0029", "EXP-0155"],
    "four fields swept 0..255 on the flat0/flat1 carriers, 3247 cases, 23/23 baselines ok, 2 gated runs",
    "R2",
    "EXP-0029 gave a real behavioural proof with a paired negative control: the [[flat]] fragment "
    "renders a CONSTANT colour (the provoking-vertex value) at all 16 pixels while the interpolated "
    "variants show a gradient, and four 6-byte 0x1f ops tokenize interp_flat to zero leftover. "
    "EXP-0155 reproduced its baselines on G17P 23/23 and showed the bytes are live against four "
    "DISTINCT authored flat values. What is missing for R1 is a per-value oracle: the sweeps score "
    "movement against the baseline, so no `sel` value was shown to fetch a PREDICTED varying.",
    "a `sel` -> varying-index map scored against a host oracle would lift it; a carrier where the "
    "flat op interpolates would refute it.",
    ["`sel` was swept 127 of 256 of the frozen value set before a hang/deadline budget stopped it.",
     "the representative arm was re-pointed by the orchestrator from flat1 to flat0 because the "
     "field was inert on flat1."])

add("rtq_state_move", IBD, "G17P", ["EXP-M4-13", "EXP-0157"],
    "dst 15 values and src 255 values on 3 ray-query carriers, 5756 cases, 2 agreeing captures",
    "R2",
    "EXP-0157 closed the acceleration-structure testbed gap and ran this instruction in three "
    "intersection-query carriers whose host oracles it reproduces exactly (k_rq_prim returns all "
    "eight authored quantities exactly). `src` behaves like a real register read in rq_cdist -- only "
    "39 of 256 values reproduce the oracle and 212 return a DIFFERENT value. But the descriptor calls "
    "itself a MOVE, and no (src -> dst) pair was chosen and predicted: `dst` reproduces the oracle at "
    "13 of 15 nibbles, which is not what a move into a named GPR should look like.",
    "a chosen (src, dst) pair whose predicted register content appears -- that is the R1 test and it "
    "has not been run.",
    ["`form` and `b3` were folded into `match` by EXP-0175 (zero free bits); only `dst` and `src` "
     "remain as fields."])

add("shift_amt_move", IBD, "G17P", ["EXP-M4-13", "EXP-0146", "EXP-0154", "EXP-0168"],
    "all four bytes dense 0..255 on M4 and G17P; after EXP-0181's narrowing, `kind` is 16 of 16 dense on both targets",
    "R2",
    "Executed on both targets in a rotate-by-variable carrier, with the accepted sets identical "
    "across gated runs, and EXP-0181's re-scoring of the NARROWED `kind` shows a clean 16-of-16 dense "
    "map (G17P accepts kind 1 and 3; M4 also accepts 0 and 2). But its role -- 'stages a shift/rotate "
    "amount' -- is INHERITED from reg_move_c0's layout, never proven, and in the only carrier that "
    "reaches it `dst` reproduces the oracle at 1 of 16 values and `src_reg` at 2 of 128. No operand "
    "is shown to be choosable, so an emitter cannot yet stage an ARBITRARY amount.",
    "a carrier in which a chosen `src_reg` supplies a predicted rotate amount.",
    ["it is a member of the reg_move_c* family, whose standing finding is that NONE of them is a "
     "general GPR-to-GPR move (EXP-0087/0090/0101/0113).",
     "the hardware also accepts byte+2 = 0x14 / 0x34 (low nibble 4), OUTSIDE this descriptor's match."])

add("sr_read_wide", IBD, "G17P", ["EXP-M4-13", "EXP-0157"],
    "six fields swept on 3 ray-query carriers, 9579 cases, 2 agreeing captures",
    "R2",
    "It executed inside carriers with exact host oracles and its bytes are load-bearing (`width` "
    "faults on 32 of 256; `sel` accepts (v & 0x87) == 0x01). But TWO of the descriptor's own "
    "documented field roles were REFUTED or unobservable by the same experiment: `sel` is "
    "'load-bearing but NOT the property selector' (16 different values return the same result), and "
    "byte+7's documented CANDIDATE-vs-COMMITTED selector 'is not observable here' (255/255 inert). "
    "`dst` is PINNED in all three carriers -- 'an emitter cannot choose the destination'. A "
    "descriptor whose two identifying claims are unconfirmed must not carry the top label.",
    "an oracle-scored probe in which `sel` selects a predicted property, or byte+7 bit7 switches "
    "candidate to committed.",
    ["`operand`, `marshal` and `phase` are HW-TESTED INERT in these carriers with their roles "
     "unknown -- the single-template-inference band, not evidence of a working field."])

add("vtx_coord_xform", IBD, "M4", ["EXP-M4-13", "EXP-0147"],
    "mode dense 256, sel dense 256, operand 40 bits swept per byte (5x256) + structured whole-field values; 3746 cases, 2 gated runs",
    "R2",
    "EXP-0147 dispatched it in a real vertex carrier and produced a clean, reproducible signature: "
    "`mode` is correct exactly when (mode & 0xf3) is in {0x22, 0xe2} (8 of 256) and 240 of 256 values "
    "SUPPRESS THE DRAW ENTIRELY, confirmed twice with a healthy device in between. That proves the "
    "instruction is load-bearing for the vertex position, which is the descriptor's headline claim. "
    "It does not establish the semantics: the operand bytes are left raw by design (clean-room "
    "rule 5, the coordinate-select sequence is not reconstructed), so no coordinate was chosen and "
    "no position predicted.",
    "a chosen operand producing a predicted clip-space position.",
    ["M4 only; never dispatched on G17P.",
     "db.json's provenance still reads 'NOT HW-dispatch-validated' -- superseded by EXP-0147 and "
     "worth correcting when the label is applied."])

# ---------------------------------------------------------------- R3/R4 keep weak
add("frag_depth_store", CC, "A18", ["EXP-0029", "EXP-0155"],
    "b3/b4/b5 dense 0..255 on G17P, 1550 cases, 2 gated runs -- but the DEPTH OUTPUT was never read back",
    "R3",
    "KEEP AS IS, and this is the clearest example of why field labels must not gate the instruction. "
    "All three of its declared fields are `hardware-run` and its baselines are ok 11/11 -- yet the "
    "one thing the descriptor claims, 'write the shader [[depth]] output to the tile depth buffer', "
    "HAS NEVER BEEN OBSERVED. db.json says so itself: 'Not individually splice-validated (agxrender "
    "has no depth attachment to read back)'. The sweeps were scored against a COLOUR probe. Fields "
    "live proves the bytes were exercised; it does not prove this is the depth store.",
    "a carrier with a readable depth attachment showing the written depth -- that is the experiment "
    "this descriptor is waiting for.",
    ["the descriptor has NO operand field for the depth value at all: only b3/b4/b5.",
     "byte0 0xd7 is shared with the 16-byte texture write; the separation is a byte-diff inference."])

add("frame_marker_compact", TO, "M4+A18", ["EXP-0036", "EXP-M4-12", "EXP-M4-13", "EXP-0172"],
    "b1 dense 0..255 on G17P, 568 cases, 152 of 256 values move the observation identically in 2 runs",
    "R4",
    "KEEP AS IS. EXP-0148 records this descriptor as one of three UNRESOLVED CONTINUATION-WORD "
    "CANDIDATES -- it may not be a standalone instruction at all -- and validate_labels.py already "
    "reports it in that informational set. EXP-0172 showed byte+1 is live (152 of 256 values move, "
    "identically in run01 and run03) and that b1 = 3 and b1 = 7 HANG the device on four of five "
    "carriers. Live bytes in an unresolved continuation word are not an instruction; its semantics "
    "remain unknown and `tokenization-only` states that correctly.",
    "EXP-0148's open splice deciding whether it is a standalone op or the continuation of the "
    "preceding one.",
    ["b1 = 0x00 is the 4-byte spill_frame_marker, a DIFFERENT instruction.",
     "b1 = 3 and b1 = 7 are a device hazard."])

add("n2_op6", CC, "M4", ["EXP-M4-13", "EXP-0146", "EXP-0157"],
    "six fields swept 0..255 across 4+ carriers on both targets, 17,539 cases",
    "R3",
    "KEEP AS IS. This descriptor is not one instruction: db.json's own committed text calls it 'a "
    "genuine catch-all bucket (write-mask helper + compact select + fcmp-mask + SFU range-reduction "
    "select)' whose 'per-sub-op value maps are mixed and needs-splice'. EXP-0157 measured a DIFFERENT "
    "accepted mask for `opsel` in each carrier instance and EXP-0146/0157 recorded `dst` as PINNED "
    "('no value other than the compiler's own reproduces the oracle'). A bucket has no semantics to "
    "confirm, so no execution can raise its instruction-level label; the fields being hardware-run "
    "says the BYTES are live in each sub-family, not that the descriptor names an operation.",
    "a decomposition into per-sub-op descriptors, each with its own confirmed semantics -- then each "
    "successor gets its own label.",
    ["EXP-0174 also records it as 'not HW-dispatch validated' for the register-move question it was "
     "considered for."])

add("sfu_marker", TO, "G16G+G17P", ["EXP-0036", "EXP-M4-12", "EXP-M4-13", "EXP-0146", "EXP-0157"],
    "both bytes dense 0..255 on M4 (512 cases, 2 gated runs) and reproduced byte-for-byte on G17P in 3 carriers",
    "R4",
    "KEEP AS IS -- and note that its two fields are `hardware-run` on BOTH targets, which is exactly "
    "the trap. EXP-0146 REFUTED the descriptor's old byte-invariance claim and EXP-0157 reproduced "
    "the mapping in three independent carriers; setting byte+0 to 0x00 flips the SIGN of fast::sin on "
    "exactly the rows needing range reduction, so at least one bit is a quadrant/sign control. But "
    "db.json states the conclusion itself: 'the exact micro-op is NOT-YET-CHARACTERIZED' (clean-room "
    "rule 5 keeps the adjacent coefficient words raw). Framing right, semantics unknown -- the "
    "definition of tokenization-only.",
    "an oracle-scored probe that names what the free bits control; then it moves in one step.",
    ["`hardware-run` on its two FIELDS is correct and should stay: the accepted sets are measured. "
     "It is the INSTRUCTION whose micro-op is uncharacterized."])

add("vary_slot", CC, "G17P", ["EXP-M4-13", "EXP-0155", "EXP-0172"],
    "sel and slot dense 0..255 across 4 carriers on G17P and M4, 7282 cases, 3 experiments",
    "R3",
    "KEEP AS IS, because the descriptor's documented semantics has been REFUTED on hardware. "
    "db.json says byte+3 is 'the varying slot (monotone, tracks the store slot)'. EXP-0172 (DEF-0172-3) "
    "measured it: `slot` is live 'only bit 2 and only on one of four carriers -- all 128 values with "
    "bit 2 set move the observation, all 128 with it clear do not, and the other seven bits, "
    "INCLUDING BITS 5-6 WHERE THE COMPILER ENCODES THE VARYING INDEX, did nothing on any carrier'. "
    "Both fields are `hardware-run` and the instruction's role is nonetheless unestablished. "
    "Promoting it would certify a slot selector that does not select.",
    "a carrier in which the varying index bits demonstrably choose the varying -- that is the open "
    "question DEF-0172-3 leaves.",
    ["EXP-0155 could not resolve vary_slot@v16_v6 at all: that occurrence does not exist."])


def main():
    weak = [m for m in VAL["coverage"]["emittable_mnemonics"]
            if (VAL["instructions"].get(m, {}).get("_instruction") or {}).get("label")
            not in ("hardware-run", "isolated-byte-diff")]
    missing = [m for m in weak if m not in R]
    extra = [m for m in R if m not in weak]
    if missing or extra:
        print("MISMATCH against the live weak set: missing=%s extra=%s" % (missing, extra),
              file=sys.stderr)
    rows = {}
    for m in sorted(weak):
        cur = VAL["instructions"][m]["_instruction"]
        rec = R[m]
        d = DISP.get(m, {})
        b = BYTES.get(m, {})
        rows[m] = {
            "current": {"label": cur.get("label"), "target": cur.get("target"),
                        "evidence": cur.get("evidence"), "range": cur.get("range")},
            "recommended": {"label": rec["recommended_label"],
                            "target": rec["recommended_target"],
                            "evidence": rec["recommended_evidence"],
                            "range": rec["recommended_range"]},
            "changes": rec["recommended_label"] != cur.get("label"),
            "becomes_emitter_grade": rec["recommended_label"] in ("hardware-run", "isolated-byte-diff"),
            "decision_rule": rec["decision_rule"],
            "reason": rec["reason"],
            "refuter": rec["refuter"],
            "caveats": rec["caveats"],
            "machine_gathered_evidence": {
                "dispatched_on_hardware": bool(d),
                "experiments": sorted(d),
                "total_raw_cases": sum(v["cases"] for v in d.values()),
                "oracle_scored_cases": sum(v["oracle_scored_cases"] for v in d.values()),
                "per_experiment": d,
                "descriptor_self_attribution": {
                    e: {"distinct_byte_strings": v["distinct_byte_strings"],
                        "decode_back_to_self": v["decode_back_to_self"]}
                    for e, v in b.items()},
                "hw_anchor_tokenizes": (REACH[m]["anchor_decodes_to"].startswith(m)
                                        if m in REACH else None),
            },
        }
    n_hr = sum(1 for r in rows.values() if r["recommended"]["label"] == HR)
    n_ibd = sum(1 for r in rows.values() if r["recommended"]["label"] == IBD)
    n_keep = len(rows) - n_hr - n_ibd
    emit = VAL["coverage"]["emittable_instructions"]
    out = {"_meta": {
        "experiment": "EXP-0181",
        "task": "DEF-0173-1 -- what SHOULD the 30 weak `_instruction` labels be, from evidence",
        "decision_rule": "PRE_REGISTRATION.md R1-R5; R5 is the load-bearing one: a descriptor gets "
                         "NO credit at instruction level from its fields being hardware-run.",
        "inputs": ["tools/agx-isa/validation.json", "tools/agx-isa/db.json",
                   "analysis/dispatch_evidence.json", "analysis/dispatched_bytes_check.json",
                   "analysis/anchor_check.json", "analysis/anchor_reachability.json",
                   "the cited experiments' RESULTS.md and raw/"],
        "n_weak": len(rows),
        "recommended_hardware_run": n_hr,
        "recommended_isolated_byte_diff": n_ibd,
        "recommended_stay_weak": n_keep,
        "all_30_were_dispatched_on_hardware": all(
            r["machine_gathered_evidence"]["dispatched_on_hardware"] for r in rows.values()),
        "gate_arithmetic": {
            "emittable_now_by_field_labels": emit,
            "if_the_gate_were_applied_with_TODAY_labels": emit - len(rows),
            "if_the_gate_were_applied_with_THESE_recommendations": emit - n_keep,
            "net_cost_of_the_gate_after_this_refresh": -n_keep,
            "note": "validation.json is NOT edited here. These are recommendations for the label "
                    "owner. The five that stay weak are frag_depth_store, frame_marker_compact, "
                    "n2_op6, sfu_marker and vary_slot.",
        },
        "not_edited": ["tools/agx-isa/validation.json", "docs/", "PROVENANCE.md"],
    }, "instructions": rows}
    p = os.path.join(HERE, "instruction_labels.json")
    json.dump(out, open(p, "w"), indent=1, sort_keys=False)
    print("wrote %s: %d rows -- %d hardware-run, %d isolated-byte-diff, %d stay weak"
          % (p, len(rows), n_hr, n_ibd, n_keep))
    print("gate: %d emittable now; %d if gated on TODAY's _instruction labels; %d with these"
          % (emit, emit - len(rows), emit - n_keep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
