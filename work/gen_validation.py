#!/usr/bin/env python3
"""DOC-02: generate tools/agx-isa/validation.json — a per-field evidence label for
every instruction/field in tools/agx-isa/db.json, applying docs/evidence-classification.md.

Labelling conventions used here (also restated in validation.json's `_conventions`):
  * `untested` is the default. Every field with no committed experiment that exercised it
    stays `untested` with `evidence: []`. Positional knowledge alone is NOT a label.
  * `evidence` ids are directory names under `experiments/` — this includes the RT-* red-team
    splice-and-observe experiments (A18 Pro), which are committed experiments with raw evidence.
  * `tokenization-only` is used for fields whose ONLY established role is consuming bytes so
    the instruction length/framing round-trips. Its evidence is the census/round-trip
    experiments that established that descriptor's framing.
  * A field that WAS exercised on hardware but whose semantics remain unexplained is
    `untested` (semantics not established) with the observation recorded in `note`.
"""
import json, hashlib, sys, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "tools/agx-isa/db.json")
OUT = os.path.join(REPO, "tools/agx-isa/validation.json")

HR, IBD, CC, TOK, STI, API, HP, UT = (
    "hardware-run", "isolated-byte-diff", "corpus-correlation", "tokenization-only",
    "single-template-inference", "api-accept-reject", "host-private", "untested")

CENSUS = ["EXP-0036", "EXP-M4-12", "EXP-M4-13"]   # framing / round-trip corpus work
CENSUS_T = "M4+A18"


def F(label, rng, target, ev, note=None):
    d = {"label": label, "range": rng, "target": target, "evidence": list(ev)}
    if note:
        d["note"] = note
    return d


def U(note=None):
    return F(UT, "none", "M4", [], note)


def TOKF(note=None, ev=None, target=CENSUS_T):
    return F(TOK, "framing only (round-trips; no value semantics established)", target,
             ev or CENSUS, note)


# ---------------------------------------------------------------------------
# Per-instruction specs.
#   "_default": applied to every field not named explicitly.
#   "_instruction": the whole-instruction label.
# ---------------------------------------------------------------------------
S = {}

# --- float ALU core -------------------------------------------------------
ALIAS_NOTE = ("Register field is 6 bits load-bearing: R in [64,112] silently aliases to "
              "r(R mod 64); R in {126,127} FAULTS the command buffer (EXP-0112).")
TOPBIT_NOTE = ("RETRACTED as a register-index bit AND as a retention flag. HW-tested INERT for "
               "both addressing and retention in six families; role UNKNOWN. Never synthesize a "
               "meaning for it (EXP-0099/0105/0113/0119).")

S["falu2"] = {
    "_instruction": F(HR, "fadd/fmul executed in hand-built and generated programs (161 cases, "
                          "100 random DAGs)", "M4+A18", ["EXP-0005", "EXP-0006", "EXP-0090", "EXP-0112"]),
    "dst": F(HR, "r0..r13 of the 16 encodable nibble values, dense, including physical-register "
                 "REUSE (44/100 generated DAGs required it; up to 13 simultaneously live)",
             "M4", ["EXP-0112", "EXP-0090"]),
    "srcA_size": F(IBD, "0,1", "A18", ["EXP-0006"],
                   "16-bit reads the LOW halfword of the 32-bit register (HW-confirmed)."),
    "srcA_reg": F(HR, "0..63 dense (15-point sweep with poison-register controls); 64..112 alias "
                      "r(R mod 64); 126,127 -> CMDBUF_ERROR", "M4",
                  ["EXP-0112", "EXP-0099", "EXP-0105", "EXP-0119"], ALIAS_NOTE),
    "srcB_size": F(IBD, "0,1", "A18", ["EXP-0006"]),
    "srcB_reg": F(HR, "0..63 dense; 64..112 alias r(R mod 64); 126,127 -> CMDBUF_ERROR", "M4",
                  ["EXP-0112", "EXP-0099", "EXP-0119"], ALIAS_NOTE),
    "opsel": F(HR, "3-bit field swept via a 256-value byte+2 sweep: 4=fadd and 5=fmul validated "
                   "on all 8 don't-care combinations; 0b111 -> contained GPU hang", "A18",
               ["EXP-0005", "EXP-0006"],
               "Instruction bit 17 is part of THIS field, not a free cache bit (EXP-0086 splice)."),
    "opflags": F(HR, "each of bits 19..23 individually at {0,1}: 19=release srcA, 20=release srcB, "
                     "21=destination publication, 22/23=silent corrupt-to-zero", "M4",
                 ["EXP-0086", "EXP-0089", "EXP-0099", "EXP-0105", "EXP-0119"],
                 "DISAGREEMENT, UNRESOLVED: EXP-0090 finding_1 established that a both-real "
                 "falu2 REQUIRES opflags=3 (bit0+bit1) and that opflags=1 is a SILENT ZERO of the "
                 "srcB read, falsified over 4 independent kernels. EXP-0112 then swept all 4 raw "
                 "values in TWO shapes - including a byte-for-byte re-creation of EXP-0090's own "
                 "falsifying construction - on a DIFFERENT carrier file and got the correct sum in "
                 "all 8 runs, i.e. opflags had NO observable effect there. The release contract "
                 "itself is separately established under two-run gates by EXP-0086/0089/0099/0119 "
                 "across six families; the carrier dependence is not root-caused. Safe policy: "
                 "emit opflags=3 for a both-real falu2 (correct under BOTH observations)."),
    "ctrl": F(HR, "all 7 bits individually at {0,1}: bits0/1 are the 0x09-group instruction-LENGTH "
                  "selector (and therefore corrupt when flipped in place), bits2/3/4 inert, "
                  "bits5/6 silent corruptors", "M4", ["EXP-0105", "EXP-0113", "EXP-0119"],
              "EXP-0105 reported bits0/1 as 'general corruptors'; EXP-0119 identified them as the "
              "length selector. Compatible, but the length reading is the load-bearing one."),
    "srcB_imm": F(IBD, "0,1", "A18", ["EXP-0006", "EXP-0020", "RT-1a-FIX"],
                  "bit39=1 switches srcB to the minifloat immediate (falu2i) or, when bit15=0, "
                  "to a uniform-register source (falu2_uni)."),
    "mod_lo": U("Instruction bits 40-42. Never exercised in isolation by any committed experiment."),
    "srcB_neg": F(IBD, "0,1 (byte+5 0xc0 -> 0xc8 on a real add: 5+3 becomes 5-3)", "M4",
                  ["EXP-M4-10"]),
    "mod_hi": F(HR, "bit44 at {0,1} (silent corrupt-to-zero, crossed against reg field 3 and 67); "
                    "bits45-47 at all 8 values (no observable effect)", "M4",
                ["EXP-0105", "EXP-0099"],
                "EXP-0099 H4 REFUTED the 'consumer route' hypothesis for bits45-47."),
    "srcA_reg_top": F(HR, "{0,1} crossed against reg-field values {3,67} and against opflags "
                          "bit19 in {0,1}; reproduced in falu2i, falu2_ext (both slots), "
                          "falu3_srcmod12 (both slots) and under 15-deep register pressure",
                      "M4", ["EXP-0099", "EXP-0105", "EXP-0113", "EXP-0119"], TOPBIT_NOTE),
    "srcB_reg_top": F(HR, "{0,1} crossed against reg-field values {3,67} and against opflags "
                          "bit20 in {0,1}", "M4", ["EXP-0099", "EXP-0119"], TOPBIT_NOTE),
}

S["falu2i"] = {
    "_instruction": F(HR, "fadd/fmul with a packed minifloat immediate, executed in hand-built and "
                          "generated programs", "M4+A18", ["EXP-0006", "EXP-0090", "EXP-0101", "EXP-0112"]),
    "dst": F(HR, "r0..r13 of 16 encodable, dense, with reuse", "M4", ["EXP-0112", "EXP-0090"]),
    "imm_flag": F(STI, "1 only (every observed and every constructed encoding); 0 never tested",
                  "M4+A18", ["EXP-0006"]),
    "imm_mant": F(HR, "0..7 exhaustive across the 16 spliced constants and the generated "
                      "boundary-weighted immediate pool", "M4+A18", ["EXP-0006", "EXP-0090", "EXP-0112"]),
    "imm_exp": F(HR, "8..15 (the valid minifloat domain, values +-{1/32..30} incl. both extremes); "
                     "exp<8 is NOT an immediate - it is the falu2_uni uniform-source overload",
                 "M4+A18", ["EXP-0006", "EXP-0090", "EXP-0112", "RT-1a-FIX"],
                 "imm_decode() must be guarded to exp>=8; the unguarded form silently invents a "
                 "tiny value for what is really a uniform read."),
    "imm_sign": F(HR, "0,1 (+-30.0 max/min and +-1.0/+-0.5 constructed and executed)", "M4",
                  ["EXP-0090", "EXP-0112"]),
    "opsel": F(IBD, "4 (fadd) and 5 (fmul) of 8 encodable, both constructed and executed", "M4",
               ["EXP-0090", "EXP-0112"]),
    "opflags": F(HR, "bit20 at {0,1} (source release, load-bearing); bits21-23 NOT tested in this "
                     "form", "M4", ["EXP-0119", "EXP-0090", "EXP-0086"],
                 "In falu2i, imm_sign occupies bit19, so the single source-release flag sits at "
                 "bit20 - a DIFFERENT absolute position from falu2's bit19 for the same role."),
    "srcA_size": F(IBD, "0,1", "A18", ["EXP-0006"]),
    "srcA_reg": F(HR, "0..63 dense; value 67 reads r3 (mod-64 alias); 64..112 alias; 126,127 fault",
                  "M4", ["EXP-0105", "EXP-0112"], ALIAS_NOTE),
    "ctrl_lo": TOKF("Low 2 bits are the 0x09-group instruction-length selector (EXP-0119). The "
                    "remaining 5 bits have no established semantics in this form.",
                    ev=["EXP-0119"] + CENSUS),
    "mods": F(IBD, "0x00 and 0xC0 only, of 256 encodable", "M4", ["EXP-0101", "EXP-0112"],
              "0xC0 (bits 6+7 together, neither alone) is REQUIRED when the modified operand is "
              "load-sourced; 0x00 makes the load operand read as a silent zero."),
    "srcA_reg_top": F(HR, "{0,1} crossed against reg-field values {3,67}", "M4",
                      ["EXP-0105", "EXP-0119"], TOPBIT_NOTE),
}

S["falu2_uni"] = {
    "_default": U("Field position inherited from the HW-validated falu2 layout; not "
                  "independently exercised in the uniform-source form."),
    "_instruction": F(IBD, "one uniform bound and read back at 3 runtime values (7, 55, 1000)",
                      "A18", ["EXP-0020", "RT-1a-FIX"]),
    "usrc": F(STI, "index 0 only - sweeping the index surfaces only the single bound uniform, so "
                   "no distinct second index was ever read", "A18", ["EXP-0020"],
              "7-bit index implies <=128 uniform registers; the actual count is NOT established. "
              "Uniform allocation is on-demand (Dynamic Caching)."),
    "uni_mode": F(IBD, "0,1 (toggling makes the operand read the GPR, i.e. 0)", "A18",
                  ["EXP-0020", "RT-1a-FIX"]),
}

S["falu3"] = {
    "_default": U(),
    "_instruction": F(CC, "fma emitted by our own MSL and tokenized; no synthesized falu3 was "
                          "executed", "M4+A18", CENSUS),
    "srcmods": F(CC, "0xc0 default vs 0xc8 (negate the a*b product) - own-MSL byte-diff only",
                 "M4", ["EXP-M4-13"],
                 "Located by compile-only byte-diff; the remaining srcmods bits are unmapped."),
    "ctrl": TOKF(),
}

S["falu2_ext"] = {
    "_default": U(),
    "_instruction": F(HR, "8-byte saturate form executed; saturate bit spliced off and on",
                      "M4", ["EXP-M4-10", "EXP-0119"]),
    "srcA_reg": F(HR, "value {3,67} addressing cross-check (67 reads r3); full range NOT swept in "
                      "this form", "M4", ["EXP-0119"], ALIAS_NOTE),
    "srcB_reg": F(HR, "value {3,67} addressing cross-check (67 reads r3)", "M4", ["EXP-0119"],
                  ALIAS_NOTE),
    "opflags": F(HR, "all 5 bits individually at {0,1}: bit19 = release srcA (matches falu2 "
                     "exactly), bits20/21 no later-read effect, bits22/23 collapse the "
                     "instruction's OWN result to 0.0 (unexplained)", "M4", ["EXP-0119"],
                 "The bits22/23 own-result collapse is OBSERVED and UNINTERPRETED."),
    "ext_tail": F(IBD, "byte+7 0x82 vs 0x80 (saturate on/off) of 65536 encodable", "M4",
                  ["EXP-M4-10"],
                  "byte+7 bit1 = output clamp to [0,1]; native modifier, not a lowered min/max. "
                  "The rest of the 16-bit tail is unmapped."),
    "srcB_neg": F(CC, "0x00 vs 0x08 in own-compiled saturate(a-b)", "M4", ["EXP-M4-13"]),
    "srcB_imm": TOKF(),
    "ctrl": TOKF(),
}

S["falu3_ext"] = {
    "_default": U(),
    "_instruction": F(CC, "10-byte extended fma located by the EXP-M4-10 length rule and "
                          "own-MSL corpus; no synthesized instance executed", "M4", ["EXP-M4-10"]),
    "ext": TOKF("32-bit saturate/source-modifier tail; length = 6+2*(byte+4 & 3)."),
}

S["funary"] = {
    "_default": U(),
    "_instruction": F(CC, "fmov/fabs/fneg located by own-MSL byte-diff", "A18", ["EXP-0013"]),
    "mod": F(CC, "0x00 mov, 0x02 fabs, 0x0a fneg (3 of 256 observed); bit1=abs-enable, "
                 "bit3=negate, 0x08 alone acts as mov", "A18", ["EXP-0013"],
             "Own-shader byte-diff; no synthesized value was executed."),
    "b1": TOKF(), "srcmod": TOKF(), "ext": TOKF(),
}

# --- integer ALU ----------------------------------------------------------
S["iadd2"] = {
    "_default": U(),
    "_instruction": F(HR, "device_load -> iadd2 -> device_store anchor executed with independently "
                          "varied addend", "M4+A18", ["EXP-0007", "EXP-0090", "EXP-0112"]),
    "addsub": F(IBD, "0,1 (splicing a real add's byte0 0x9f -> 0x1f turns 10+20 into 10-20 = -10)",
                "A18", ["RT-1a-FIX", "EXP-0007"],
                "Polarity CORRECTED here: 0x9f = ADD, 0x1f = SUBTRACT. The earlier `srcA_neg` "
                "framing was inverted."),
    "srcB_imm": F(HR, "K = 0,1,2,63,64,65,100,127,128,129,200,255 - the full effective 0..127 "
                      "range plus the exact mod-128 wraparound at K=128", "M4", ["EXP-0112"],
                  "The byte holds (K<<1); K=128 therefore behaves identically to K=0."),
    "srcB_imm_hi": F(CC, "set only at K=255 in own-compiled code; never independently synthesized",
                     "M4", ["EXP-M4-13"]),
    "dst": F(CC, "(reg<<1)|size located by own-MSL byte-diff; NOT independently synthesized - "
                 "EXP-0112 held dst fixed on the one verbatim anchor", "M4", ["EXP-M4-13", "EXP-0020"],
             "iadd2 register-mode (both operands GPR, independently chosen registers/dst) is an "
             "explicit open item - see EXP-0112 section 4."),
    "srcA": F(CC, "located by own-MSL byte-diff only", "M4", ["EXP-M4-13"]),
    "srcB_reg_hi": F(CC, "srcB register number is scattered across b1/b5/b6; located by byte-diff",
                     "M4", ["EXP-M4-13"]),
    "srcB_ext": F(CC, "part of the scattered srcB register number", "M4", ["EXP-M4-13"]),
    "opc_tail": F(CC, "reg-srcB tail a8 17 05 vs imm-srcB tail 88 15 04 (2 observed patterns)",
                  "M4", ["EXP-M4-13"]),
    "opc_tail2": F(CC, "reg-srcB tail a8 17 05 vs imm-srcB tail 88 15 04", "M4", ["EXP-M4-13"]),
    "lenbit": TOKF("byte+1 bit0 selects 10-byte 2-src vs 12-byte 3-src for the 0x9f/0x1f/0xa7 groups.",
                   ev=["EXP-0007"] + CENSUS, target="A18"),
    "b2_bit0": TOKF(), "store_en": TOKF(), "b2_fmt": TOKF(), "opmode": TOKF(),
}

S["imad"] = {
    "_default": U(),
    "_instruction": F(CC, "imul/imad located by own-MSL byte-diff; behaviourally exercised via "
                          "compiler-emitted code only", "M4+A18", ["EXP-0007", "EXP-M4-13"]),
    "dst": F(CC, "(reg<<1)|size proven by an own-MSL r6/r4/r2 dst sweep (compile-only)", "M4",
             ["EXP-M4-13"]),
    "srcC_desc": F(CC, "0x00 no addend, 0x40 register addend, (K<<3) immediate addend for "
                       "K=1,5,7,255 (own-MSL byte-diff)", "M4", ["EXP-M4-13"]),
    "mulsel": F(CC, "0xd0 low-32 vs 0xe0 high-32 (mulhi); own-MSL byte-diff", "M4", ["EXP-M4-13"]),
    "b10": F(CC, "0x0a -> 0x1e for signed mulhi; own-MSL byte-diff", "M4", ["EXP-M4-13"]),
    "lenbit": TOKF(ev=["EXP-0007"] + CENSUS, target="A18"),
    "b0bit7": TOKF(), "b1hi": TOKF(), "b2_bit0": TOKF(), "store_en": TOKF(), "b2_fmt": TOKF(),
    "opmode": TOKF(), "srcB": TOKF(), "srcC_lo": TOKF(), "b9": TOKF(), "b11": TOKF(),
}

IMINMAX_NOTE = ("PROVENANCE FLAG: splicing a real, in-range register field of this family produced "
                "ZERO effect (EXP-0105) and EXP-0113 found this family's spliced results "
                "NONDETERMINISTIC across runs (4/46 cases). Operand mapping is UNVALIDATED.")
S["iminmax"] = {
    "_default": U(IMINMAX_NOTE),
    "_instruction": F(IBD, "byte0 dst-nibble splice 0x02 -> 0x12 / 0x42 redirected the result and "
                           "ran STATUS OK", "M4", ["EXP-M4-13"]),
    "dst": F(IBD, "r0, r1, r4 (3 of 16) - splicing byte0's high nibble moved the result to a "
                  "different register so the unchanged store read zeros", "M4", ["EXP-M4-13"]),
    "sel": F(CC, "0=fmax 1=fmin 4=umax 5=umin 6=imax 7=imin (6 of 8) located by own-MSL byte-diff",
             "M4+A18", ["EXP-0007", "EXP-M4-13"]),
    "srcA": U(IMINMAX_NOTE), "srcB": U(IMINMAX_NOTE), "dst_full": U(IMINMAX_NOTE),
    "fmt": U(IMINMAX_NOTE), "selhi": U(IMINMAX_NOTE),
}

S["hminmax"] = {
    "_default": U(),
    "_instruction": F(CC, "half min/max located by own-MSL byte-diff (byte+2==0x1c sibling of "
                          "iminmax)", "M4", ["EXP-M4-13"]),
    "sel": F(CC, "0=hmax 1=hmin (2 of 8) observed", "M4", ["EXP-M4-13"]),
}

for m in ("isel_reg", "isel_reg8", "isel8", "isel10", "isel10_c"):
    S[m] = {"_default": U("Field position adopted from the isel10 layout, located by own-MSL "
                          "corpus; no operand of this family was independently synthesized."),
            "_instruction": F(CC, "register-operand compare-select forms located and tokenized "
                                  "over the own-MSL corpus", "M4", ["EXP-M4-13"]),
            "cc": F(CC, "condition-code byte shares the icmpsel byte+6 map (float/uint/sint x "
                        "lt/gt) by structure; per-value map located by own-MSL byte-diff",
                    "M4+A18", ["EXP-0013", "EXP-M4-13"])}
S["isel10"]["_instruction"] = F(IBD, "the EXP-0090 loop+if/else->select control-flow skeleton was "
                                     "re-executed with 12 data-driven parameterizations", "M4",
                                ["EXP-0090", "EXP-0112"])

S["n2_op6"] = {
    "_default": U("n2_op6 is an acknowledged catch-all bucket (write-mask helper + compact select "
                  "+ fcmp-mask + SFU range-reduction select); per-sub-op value maps are mixed."),
    "_instruction": F(CC, "family located and tokenized over an own-MSL corpus (n=1747)", "M4",
                      ["EXP-M4-13"]),
    "dst": F(CC, "byte0 high nibble proven a destination register by an own-MSL r0..r15 reg-sweep "
                 "(compile-only)", "M4", ["EXP-M4-13"]),
}

S["iunary"] = {
    "_default": U(),
    "_instruction": F(HR, "popcount executed and its sub-op selector spliced", "A18",
                      ["EXP-M4-14", "EXP-0033"]),
    "opsel": F(HR, "byte+2 swept: only 0x54/0x55 break the stored result, every other value "
                   "computes; 0x56 = the integer-unary/format-convert datapath", "A18",
               ["EXP-M4-14"],
               "Loose byte0==0x27 catch-all: popcount is the HW-validated member, but the corpus "
               "is dominated by RT/interp/convert siblings of the same length."),
    "b1": F(HR, "(byte0 bit7, byte+1) sub-op pairs: (0x27,0x05)=popcount, (0xa7,0x05)=find_msb, "
                "(0xa7,0x04)=reverse_bits", "A18", ["EXP-M4-14"],
            "CORRECTION: the sub-op selector is (byte0 bit7 + byte+1), NOT byte+4. The former "
            "'byte+4 optype 0x02 popcount vs 0x03 find_msb' label was correlation, not causation."),
    "operand": TOKF("byte+3..+7 mixes a popcount source with SFU/interp/format coefficient words; "
                    "kept raw under clean-room rule 5."),
}

S["ishift"] = {
    "_default": U(),
    "_instruction": F(CC, "arithmetic shift-right by immediate located by own-MSL byte-diff", "M4",
                      ["EXP-M4-13", "EXP-0013"]),
    "shamt": F(CC, ">>1/2/4/8 -> byte+6 0x04/0x08/0x10/0x20 (shamt<<2), 4 own-MSL points", "M4",
               ["EXP-M4-13"]),
    "shift_type": F(CC, "0x78 = arithmetic shift-right op-type (1 observed value)", "M4",
                    ["EXP-M4-13"]),
    "src_cache": F(CC, "0x56 -> 0x54 when the source is a computed/consumed register", "M4",
                   ["EXP-M4-13"]),
    "form": TOKF("byte+1 bit0 is the 0xa7 10-vs-12-byte length selector."),
    "op8": TOKF("For the corpus-dominant 0xa7 interpolation/RT siblings (138/188) byte+6/+8/+9 are "
                "operand/coefficient words, NOT a shift amount."),
    "pad9": TOKF(),
}

S["ibfe"] = {
    "_default": U(),
    "_instruction": F(CC, "extract_bits located by own-MSL byte-diff; the runtime-operand form was "
                          "exercised behaviourally over 122 boundary rows but through "
                          "compiler-emitted code", "M4", ["EXP-M4-13", "EXP-0102", "EXP-0033"]),
    "offset": F(CC, "off = 1,3,4,5,6,8 -> b6 0x04/0x0c/0x10/0x14/0x18/0x20 (offset = b6>>2); "
                    "own-MSL compile-only", "M4", ["EXP-M4-13"]),
    "width": F(CC, "width = 1,4,8,12,16 -> 0x10/0x40/0x80/0xc0/0x100; width=0 means extract-to-MSB",
               "M4", ["EXP-M4-13"]),
    "width_lo": F(CC, "low nibble of the same scattered width immediate", "M4", ["EXP-M4-13"]),
    "sign_ext": F(CC, "0,1 - signed extract sets b6 bit1 and clears srcC_flags bit0", "M4",
                  ["EXP-M4-13"]),
    "srcC_flags": F(CC, "0x11 unsigned vs 0x10 signed (2 observed values)", "M4", ["EXP-M4-13"]),
    "dst": F(CC, "(reg<<1)|size proven by an own-MSL dst sweep b3 0x0c/0x0a/0x06 = r6/r5/r3",
             "M4", ["EXP-M4-13"]),
    "srcA": F(CC, "located by own-MSL byte-diff", "M4", ["EXP-M4-13"]),
    "lenhi": TOKF(), "b2_bit0": TOKF(), "store_en": TOKF(), "b2_fmt": TOKF(), "b4": TOKF(),
    "b5": TOKF(), "b6_bit0": TOKF(), "b7": TOKF(), "b11hi": TOKF(),
}

S["icmpsel"] = {
    "_default": U(),
    "_instruction": F(CC, "integer/float compare-select located by own-MSL byte-diff", "A18",
                      ["EXP-0013"]),
    "cmpmode": F(CC, "0x22 relational vs 0x26 equality (own-MSL a==b toggle)", "M4+A18",
                 ["EXP-0013", "EXP-M4-13"]),
    "cond": F(CC, "0x02 f> / 0x03 f< / 0x04 u> / 0x05 u< / 0x06 s> / 0x07 s< (6 of 256); "
                  "bits[1:3]=type, bit0=lt/gt", "A18", ["EXP-0013"]),
    "neg_lo": F(CC, "result-negate for ge/le/ne, byte+5 bit0 paired with byte+9 bit0", "A18",
                ["EXP-0013"]),
    "srcA": F(CC, "located by own-MSL byte-diff", "A18", ["EXP-0013"]),
    "tail": TOKF(), "cache": TOKF(), "mark0": TOKF(), "sel_marker": TOKF(),
    "sel_operand": TOKF("The byte that varies most corpus-wide; register-select variation needs a "
                        "splice."),
}

for m, sib in (("cvt_f2i", "float->int"), ("cvt_i2f", "int->float")):
    S[m] = {
        "_default": U(),
        "_instruction": F(CC, "convert located by own-MSL byte-diff; behaviourally exercised via "
                              "compiler-emitted code", "M4+A18", ["EXP-0013", "EXP-M4-13"]),
        "dst": F(CC, "byte+3 steps 0,2,4,6 with the RESULT lane in a reversed-lane vec4 chain "
                     "(4 own-MSL points, compile-only)", "M4", ["EXP-M4-13"]),
        "src": F(CC, "byte+5 steps 0x18,0x14,0x10,0x0c with the SOURCE lane, i.e. opposite to dst "
                     "(4 own-MSL points)", "M4", ["EXP-M4-13"]),
        "signflag": F(CC, "byte+7 bit6 = signed vs unsigned (2 values, own-MSL)", "M4+A18",
                      ["EXP-0013", "EXP-M4-13"]),
        "cvtop": TOKF(), "src_class": TOKF(),
        "mode": F(HR, "byte+2 bit17 at {0,1} corrupts BOTH the instruction's own result AND a "
                      "later reader; the other 7 bits of the byte re-swept individually, all "
                      "with no detectable effect", "M4", ["EXP-0089", "EXP-0119"],
                  "This is the LITERAL 0x54/0x56 bit that docs once called an inert cache hint. "
                  "It is load-bearing here."),
    }
S["cvt_f2i"]["dst_class"] = TOKF()
S["cvt_f2i"]["b9"] = TOKF()

S["cvt_f2h"] = {"_default": TOKF("fp32->fp16 narrowing convert; byte0 0x11 length-polymorphic on "
                                 "byte+1. Operand bytes located only."),
                "_instruction": F(CC, "located by own-MSL byte-diff", "A18", ["EXP-0013"])}

S["bf_alu"] = {
    "_default": U(),
    "_instruction": F(IBD, "splice byte+2 0x1c -> 0x1d flipped native bfloat 1+2 into 1x2", "A18",
                      ["EXP-O2D"]),
    "opsel": F(IBD, "0x1c add vs 0x1d mul (2 of 256), spliced and observed", "A18", ["EXP-O2D"]),
    "srcA": U(), "srcB": U(), "tail": TOKF(),
}

S["mov_zext16"] = {
    "_default": U(),
    "_instruction": F(CC, "16-bit zero-extend located by own-MSL byte-diff with negative controls "
                          "(sign-extend and 8-bit narrow do NOT use this op)", "M4", ["EXP-M4-13"]),
    "extend": F(CC, "0x01 = the low-16 zero-extend companion; other companions unmapped", "M4",
                ["EXP-M4-13"]),
    "src_reg": F(CC, "byte+1 bits0-6 source register (corpus n=596, 46 distinct values)", "M4",
                 ["EXP-M4-13"]),
    "src_flag": F(CC, "byte+1 bit7 uniform/special-file flag", "M4", ["EXP-M4-13"]),
    "subform": F(CC, "35 distinct values observed; per-value map partial", "M4", ["EXP-M4-13"]),
}

S["ilogic"] = {
    "_default": U(),
    "_instruction": F(IBD, "2-input LUT covering all 16 boolean functions, exercised through "
                           "own-MSL logic kernels", "A18", ["EXP-0013"]),
    "op_base": F(CC, "0,1 (xor base vs and/or base)", "A18", ["EXP-0013"]),
    "lut_a": F(CC, "per-source inverts; the 16 LUT2 functions were reached via MSL source, not by "
                   "synthesizing the field", "A18", ["EXP-0013"]),
    "lut_b": F(CC, "output invert bit (byte+5 bit3)", "A18", ["EXP-0013"]),
    "outmod": F(CC, "bit7 set for store-consumed forms, clear for compare-consumed forms", "M4",
                ["EXP-M4-13"]),
    "srcA": F(CC, "located at the falu srcA position", "M4", ["EXP-M4-13"]),
    "srcB": F(CC, "located at byte+3", "M4", ["EXP-M4-13"]),
    "z6": TOKF(), "z8": TOKF(), "z9": TOKF(),
}

S["fspecial"] = {
    "_default": U(),
    "_instruction": F(IBD, "single-op rcp/rsqrt/exp2/round/sqrt/log2 executed; accuracy measured "
                           "(rcp/rsqrt 0 ULP, sqrt/exp2/log2 ~1 ULP)", "M4+A18",
                      ["EXP-0026", "EXP-0103"]),
    "fn_hi": F(CC, "0 (0x2f: round/sqrt/log2) vs 1 (0xaf: rcp/rsqrt/exp2)", "A18", ["EXP-0026"]),
    "fnclass": F(CC, "0x0/0x1/0x2/0x3 (4 of 16) - the function select, located by own-MSL byte-diff",
                 "A18", ["EXP-0026", "EXP-0013"]),
    "dst": F(CC, "byte+1 HIGH nibble proven a GPR by an own-MSL 5-way rsqrt dst sweep "
                 "0x01/0x11/0x21/0x41/0x81 (compile-only)", "M4", ["EXP-M4-13"]),
    "roundmode": F(CC, "0 nearest / 2 floor / 4 ceil / 6 trunc (4 of 256) in the round family, or "
                       "0x20 = reciprocal precision flag", "A18", ["EXP-0013", "EXP-0026"]),
    "src": F(CC, "byte+3 source register low bits", "M4", ["EXP-M4-13"]),
    "src_ext": F(CC, "byte+5 source register extension", "M4", ["EXP-M4-13"]),
    "src_class": F(CC, "0x03 f32 / 0x02 f16-or-alt", "M4", ["EXP-M4-13"]),
    "src_cache": TOKF("0x56 fresh / 0x54 shared - the literal 0x54/0x56 bit, DOWNGRADED to UNKNOWN "
                      "for this family; never assume inert (EXP-0086).", ev=["EXP-0086"] + CENSUS),
    "fnsel": TOKF(), "precsel": TOKF(), "sched_flag": TOKF(),
}

S["fspecial_est"] = {
    "_default": U(),
    "_instruction": F(IBD, "the ~7.5-8 mantissa-bit Newton-Raphson seed measured for rcp/rsqrt/sqrt",
                      "A18", ["EXP-0026"]),
    "subop": F(CC, "0x09 rcp / 0x0b rsqrt / 0x0d sqrt (3 of 256), own-MSL byte-diff", "A18",
               ["EXP-0026"]),
    "dst": U(), "srcA": TOKF(), "b4": TOKF(), "b5": TOKF(),
}

S["icmp_pred"] = {
    "_default": U(),
    "_instruction": F(HR, "loop-guard and if-guard compares executed; predicate destination "
                          "swept exhaustively", "M4+A18", ["EXP-0104", "EXP-0115", "EXP-0112"]),
    "dst_pred": F(HR, "0..15 EXHAUSTIVE: 0 = correct, 1 = one distinct corruption, 2..15 = a "
                      "second uniform corruption; also A18-spliced p2->p0 and p2->p4", "M4+A18",
                  ["EXP-0104", "EXP-0115", "RT-ISA-FIX"],
                  "There is NO predicate register file to allocate: the compiler emits dst_pred=0 "
                  "in 0/18+ compiled instances and any nonzero value silently corrupts the branch "
                  "outcome. A driver must always emit 0."),
    "cond": F(HR, "cond=7 (inverted guard, skips the loop regardless of trip count) and the "
                  "natural value, each executed over 12 data points", "M4",
              ["EXP-0090", "EXP-0112"],
              "Low 3 bits = [type: float/uint/sint][direction: gt even / lt odd], the same map as "
              "icmpsel byte+6; bit4 flags the compact-immediate operand form (own-MSL located)."),
    "cmpmode": F(CC, "0x2 relational / 0x3 equality (own-MSL located)", "M4", ["EXP-M4-13"]),
    "neg": F(CC, "byte+1 bit7 negates the result for le/ge/ne (own-MSL located)", "M4",
             ["EXP-M4-13"]),
    "opclass": F(CC, "0xc0 register srcB vs 0xc2 immediate bound (2 observed values)", "M4",
                 ["EXP-M4-13"]),
    "srcA": U(), "srcB": U(), "opdesc_hi": TOKF(),
}

S["sel"] = {"_default": TOKF("4-byte branchless select; the 24-bit body is not decoded."),
            "_instruction": F(CC, "located by own-MSL byte-diff", "A18", ["EXP-0010"])}
S["psel"] = {"_default": TOKF("Role-typed by located position over the corpus; own MSL ternaries "
                              "fold to isel10, so psel was not single-toggle reproducible."),
             "_instruction": F(CC, "dominant corpus form 05 00 20 80", "M4", ["EXP-M4-13"])}

# --- control flow ---------------------------------------------------------
BRANCH_NOTE = ("Practical reach is FAR narrower and more irregular than the 48-bit encoding: "
               "delta=+1 from a valid target already faults, delta=-2 is an undocumented alias "
               "hole that still executes correctly, and past the function extent the outcome is a "
               "checkerboard of fault / hang / silent-zero. 13/162 points were run-to-run "
               "NONDETERMINISTIC (EXP-0115).")
S["jump"] = {
    "_default": U(),
    "_instruction": F(HR, "loop back-edge executed; zeroing it produces a contained infinite-loop "
                          "hang", "M4+A18", ["EXP-0010", "EXP-0115"]),
    "offset": F(HR, "162 independently constructed splice points per run around a valid target "
                    "(deltas -32..+9 dense plus far-forward/backward probes)", "M4",
                ["EXP-0115", "EXP-0010"], BRANCH_NOTE),
    "branch_ctrl": F(CC, "0x54 in 645/646 corpus jumps and every own-MSL loop back-edge; a single "
                         "corpus jump uses 0x64", "M4", ["EXP-M4-13"]),
    "link": F(STI, "0x00 in all 646 corpus jumps and all own-MSL loops; no other value observed or "
                   "constructed", "M4", ["EXP-M4-13"]),
}
S["jump_cond"] = {
    "_default": U(),
    "_instruction": F(IBD, "turning the guard unconditional (byte+1 0x01 -> 0x00) makes every lane "
                           "skip the loop body -> all-zero output", "A18", ["RT-ISA-FIX"]),
    "offset": F(CC, "signed 48-bit LE byte displacement; target = jump_addr + 4 + offset, located "
                    "over own-MSL if/else/while/for shapes", "A18", ["RT-ISA-FIX", "EXP-0010"],
                "EXP-0115 measured the practical reach on the sibling `jump`; see that field. "
                "EXP-0115 also flags the '+4' convention against db.json's own wording."),
    "cf_scope": F(CC, "0x54 / 0x56 mask-bank values observed", "M4", ["EXP-M4-13"]),
    "reserved": TOKF(),
}
S["if_push"] = {
    "_default": U(),
    "_instruction": F(IBD, "corrupting a matching 0f 06 reconverge (byte+1 0x06 -> 0x00) "
                                      "produces CMDBUF_ERROR; if_push executed in the validated CF "
                                      "skeleton", "M4+A18", ["RT-ISA-FIX", "EXP-0104", "EXP-0112"]),
    "scope": F(CC, "0x54 outer / 0x56 nested (ping-pongs with nesting parity); 0x04 inner mask-op "
                   "variant", "M4+A18", ["EXP-0104", "EXP-M4-13"]),
    "scope_kind": F(CC, "0x01 conditional-skip scope, 0x1a loop-iteration scope (2 observed)",
                    "M4", ["EXP-M4-13"]),
}
S["pop_reconverge"] = {
    "_default": U(),
    "_instruction": F(IBD, "byte+1 0x06 -> 0x00 -> CMDBUF_ERROR; executed at nesting depth up to "
                           "254 (the toolchain ceiling, not a hardware one)", "M4+A18",
                      ["RT-ISA-FIX", "EXP-0104", "EXP-0115"]),
    "scope_kind": F(CC, "0x02 loop-body scope, 0x01 outermost/loop-entry scope (2 observed)", "M4",
                    ["EXP-M4-13"]),
    "scope": F(CC, "mask-bank selector, low 0x04 form", "M4", ["EXP-M4-13"]),
    "reserved": TOKF(),
}
S["mask_op"] = {
    "_default": U(),
    "_instruction": F(TOK, "framing only (4B, byte+1==0x04); 1 corpus occurrence, role INFERRED",
                      CENSUS_T, CENSUS),
    "mask_bank": F(CC, "0x04 bankA / 0x24 bankB (2 observed values)", "M4", ["EXP-M4-13"]),
    "scope_kind": F(STI, "0x19 in the whole corpus - no observed variation", "M4", ["EXP-M4-13"]),
}
S["if_push_pred"] = {
    "_default": U(),
    "_instruction": F(HR, "25-point (dst_pred, if_push.pred) matrix executed", "M4", ["EXP-0115"]),
    "pred": F(HR, "0..15 EXHAUSTIVE, crossed against icmp_pred.dst_pred 0..15: COMPLETELY INERT - "
                  "matched or mismatched, it never changes anything", "M4", ["EXP-0115"],
              "REFUTES the hypothesis that this nibble selects the predicate the push consumes."),
    "scope": TOKF(), "level": TOKF(),
}
S["call"] = {
    "_default": U(),
    "_instruction": F(IBD, "direct call executed and its PC-relative target verified at 4 distinct "
                           "distances", "A18", ["EXP-0035"]),
    "offset": F(IBD, "4 distinct call distances; target = call_addr + 4 + offset", "A18",
                ["EXP-0035"]),
    "b3": TOKF(), "b5": TOKF(), "b6": TOKF(), "tail": TOKF(),
}
S["ret"] = {
    "_default": U(),
    "_instruction": F(IBD, "leaf and non-leaf returns executed to 3 levels of nesting", "A18",
                      ["EXP-0035", "EXP-0038"]),
    "linkmode": F(CC, "0x02 leaf / 0x12 non-leaf / 0x04,0x05 CF merge (4 of 256 observed)", "A18",
                  ["EXP-0035", "EXP-0038"]),
    "scoreboard": F(CC, "{0x22,0x26,0x02,0x06,0x2a} observed; bit5=wait-set present, "
                        "bit2=second-slot (located, not spliced)", "M4", ["EXP-M4-13"]),
}
S["ret_luse"] = {
    "_default": U(),
    "_instruction": F(CC, "byte+2==0x56 last-use variant located over the own-MSL corpus", "M4",
                      ["EXP-M4-13"]),
    "linkmode": F(CC, "same leaf/non-leaf/CF-merge map as `ret`", "A18", ["EXP-0035"]),
    "tail": TOKF("byte+2 bit17 is the literal 0x54/0x56 bit - DOWNGRADED to UNKNOWN, never assume "
                 "inert (EXP-0086).", ev=["EXP-0086"] + CENSUS),
}
S["call_indirect"] = {
    "_default": TOKF(),
    "_instruction": F(IBD, "function-pointer dispatch executed end to end (sel=0 -> A+B, "
                           "sel=1 -> A*B)", "A18", ["EXP-0035"]),
}

# --- memory ---------------------------------------------------------------
S["device_load"] = {
    "_default": U(),
    "_instruction": F(HR, "loads executed with independently generated base slot, index register, "
                          "immediate offset and element size, in 100 generated DAGs plus dedicated "
                          "memory-semantics matrices", "M4+A18",
                      ["EXP-0012", "EXP-0082", "EXP-0083", "EXP-0101", "EXP-0112"]),
    "space": F(IBD, "0x00 device/constant and 0x02 threadgroup (2 of 256)", "M4+A18",
               ["EXP-0012", "EXP-0100"],
               "CORRECTION: byte+1 is the address space, NOT an index register (RT-1a)."),
    "addr_mode": F(IBD, "0x54 (ALU-computed data) and 0x56 (direct live load-result forwarding)",
                   "M4", ["EXP-0087", "EXP-0090"],
                   "The 0x56 direct load-to-store forward is a register-file-BYPASSING path and is "
                   "explicitly outside the validated generation envelope (EXP-0112 section 4)."),
    "extmode": F(HR, "extmode = 2*R for R swept 0,1,2,3,7,15,16,20,31,32,47,48,61,62,63 (dense "
                     "0..63) plus 64,65,66,67,68,79,80,95,96,111,112,126,127", "M4",
                 ["EXP-0101", "EXP-0112"],
                 "RETRACTION: EXP-M4-13's destination formula dst = dst_lo|(dst_ext9<<2) is "
                 "REFUTED (EXP-0101). The register a later falu2/falu2i must reference is "
                 "extmode/2. R in [64,112] silently ALIASES to r(R mod 64) (proven with poison "
                 "controls); R in {126,127} raises CMDBUF_ERROR. A backend MUST restrict R to 0..63."),
    "base_slot": F(HR, "0x00..0xFF EXHAUSTIVE: slots 1..30 return their own distinct bound buffer, "
                       "slot 0 is anomalous, 31..127 read 0x00000000 with no fault, 128..255 "
                       "mirror 0..127 byte-for-byte", "M4", ["EXP-0083", "EXP-0010"],
                   "31 base slots are simultaneously usable via the direct-binding API; that is a "
                   "binding-path capacity, not proof of a hardware ceiling."),
    "index_reg": F(HR, "low values sweep to distinct GPRs; 0xff (r127) hard-FAULTS "
                       "(CMDBUF_ERROR) with a clean r95/r96 boundary", "M4+A18",
                   ["EXP-M4-10", "RT-1a-FIX", "EXP-0012"],
                   "The fault at 0xff REFUTES a mod-64 field: a 6-bit field would alias to r63 and "
                   "read fine."),
    "access_desc": F(HR, "0x00..0xFF EXHAUSTIVE - never changes the loaded value; HW-proven inert "
                         "padding", "A18", ["EXP-0012", "RT-1a-FIX"]),
    "ld_format": F(CC, "codes located by own-MSL byte-diff (bits[4:6] element size 00=16b/01=32b/"
                       "10=8b, bits[1:4] vector-component code, bit0 valid); no synthesized code "
                       "was executed", "M4", ["EXP-M4-13", "EXP-M4-10"]),
    "dst_lo": F(STI, "the verbatim (dst_lo=1, dst_ext9=1) token observed for terminal scalar "
                     "32-bit loads; no other value was ever made to work", "M4",
                ["EXP-0101", "EXP-0112"],
                "MUST be copied verbatim from a compiler-observed value for the same "
                "addr_mode/ld_format shape and NEVER derived from the target register - 4 "
                "adversarial cases break the load if derived, even with extmode correct."),
    "dst_ext9": F(STI, "the verbatim value 1 for terminal scalar 32-bit loads; forcing (0,0) "
                       "breaks the load (silent zero)", "M4", ["EXP-0101", "EXP-0112"],
                  "Same retraction as dst_lo: this is NOT the destination register."),
    "idx_off": F(HR, "0..2047 FULL DENSE sweep (device space) and a second full 0..2047 dense "
                     "sweep in threadgroup space; plus negative-side cross-checks at "
                     "0x3FE..0x402, 0x7FE, 0x7FF", "M4", ["EXP-0082", "EXP-0100"],
                 "Unsigned 11-bit, no internal holes. The LOAD offset unit is a FIXED 4 bytes, "
                 "independent of elem_size (neither element units nor byte units)."),
    "ldform_hi11": U("EXP-0082 swept 6 raw values of byte+11 bits2-7: 0x00/0x60/one other are "
                     "inert, 0x48 and 0x50 produce undecodable output. Semantics UNKNOWN and "
                     "explicitly flagged as follow-up - do not synthesize."),
    "elem_size": F(HR, "canonical codes 0,1,2,3,4 at representative indices plus 23 further raw "
                       "byte+12 values (load); ELEM_SCALE = {0:16, 3:4, 4:8} bytes exactly", "M4",
                   ["EXP-0082"],
                   "Codes 1 and 2 do NOT give 1-byte / 2-byte granularity - that hypothesis is "
                   "falsified. No power-of-two-violating stride was ever produced."),
    "reserved7": TOKF(), "reserved13": TOKF(),
}

S["device_store"] = {
    "_default": U(),
    "_instruction": F(HR, "stores executed with independently generated base slot, index register "
                          "and offset in 100 generated DAGs", "M4+A18",
                      ["EXP-0012", "EXP-0082", "EXP-0090", "EXP-0112"]),
    "space": F(IBD, "0x00 device and 0x02 threadgroup", "M4+A18", ["EXP-0012", "EXP-0100"]),
    "addr_mode": F(HR, "bit1 at {0,1} (the literal 0x54/0x56 position): INERT here - neither the "
                       "stored content nor the source register's later ALU reuse changed", "M4",
                   ["EXP-0119", "EXP-0087"],
                   "Genuinely different from every ALU family tested: the same literal bit is "
                   "load-bearing in falu2/unpack_convert/cvt_i2f and inert here."),
    "extmode": F(HR, "extmode = 2*(source GPR) for ALU-forwarded stores, same mechanism as the "
                     "load side; validated over the generated DAG corpus", "M4",
                 ["EXP-0090", "EXP-0101", "EXP-0112"]),
    "base_slot": F(HR, "0..255 census on the load path; store path probed at slots 0,3,31,32,63,"
                       "127,128,255 - slot 128 writes are DISCARDED (mirror is load-only)", "M4",
                   ["EXP-0083"]),
    "index_reg": F(HR, "0..95 fully round-trip correct; 96,97,100,111,120,127 uniformly FAULT; "
                       "112 is genuinely NONDETERMINISTIC (fault or silent-all-zero across "
                       "byte-identical splices)", "M4", ["EXP-0092"],
                   "Swept in lockstep with get_sr dst/dst_hi so the round trip is meaningful. "
                   "96 is a hard register-file ceiling."),
    "access_desc": F(HR, "0x00..0xFF exhaustive on the shared load/store addressing byte - inert",
                     "A18", ["EXP-0012", "RT-1a-FIX"]),
    "st_format": F(CC, "mirrors device_load ld_format per element type; an 8-live-value store "
                       "sweep with data provably in r0..r5 left byte+8/+9/+11 byte-identical, "
                       "proving it is NOT the data register", "M4", ["EXP-M4-10", "EXP-M4-13"],
                   "CORRECTION: device_store is NOT field-symmetric with device_load's dst. The "
                   "store DATA register is not a standalone field in this instruction."),
    "st_format_ext": F(CC, "bit set only for the 3-component store", "M4", ["EXP-M4-13"]),
    "st_desc_hi": F(CC, "byte+11 bits[2:8] store-format tail, located only", "M4", ["EXP-M4-13"]),
    "idx_off": F(IBD, "boundary points 0x1FF, 0x200, 0x3FF, 0x400, 0x7FF at idx 1023/1024 - all "
                      "landed outside the 8 KiB target, which is exactly what the 16-byte store "
                      "unit predicts", "M4", ["EXP-0082", "EXP-0100"],
                 "The STORE offset unit is a FIXED 16 bytes vs the LOAD's fixed 4 bytes - a real, "
                 "easy-to-miss asymmetry. Not densely swept on the store side."),
    "elem_size": F(HR, "25 raw byte+12 values probed on the store side (incl. 0x00,0x10,0x11,0x12,"
                       "0x14,0x18,0x1A,0x1C)", "M4", ["EXP-0082"]),
    "reserved7": TOKF(), "reserved13": TOKF(),
}

S["get_sr"] = {
    "_default": U(),
    "_instruction": F(HR, "special-register reads executed with an exhaustive selector sweep and a "
                          "destination-register boundary sweep", "M4+A18",
                      ["EXP-0031", "EXP-0092", "EXP-M4-14"]),
    "sr_sel": F(HR, "0x00..0xFF EXHAUSTIVE (256 values x 2 runs, zero faults, zero hangs): "
                    "0x80-0xFF reaches the special-register file (16 named, ~106 aliasing "
                    "0x9c/0x99/0x9a/0x82/0x85, 4 unclassified constants, 2 period-4 structured); "
                    "0x00-0x7F is a distinct 'selector materialized as an immediate' region, not "
                    "an SR read", "M4+A18", ["EXP-0092", "EXP-0031", "EXP-M4-14"],
                "Two caveats an implementer will hit: (1) 0xa8/0xa9/0xaa is NOT threadgroups_per_"
                "grid - a bare get_sr 0xa8 returns threads_per_threadgroup; the builtin is "
                "get_sr + a device_load + a divide (RT-7). (2) unclassified 0x80-0xFF values must "
                "not be treated as reserved-safe no-ops."),
    "dst": F(HR, "R = 0..95 fully round-trip correct; 96,97,100,111,120,127 uniformly FAULT; "
                 "R=112 NONDETERMINISTIC (fault in one run, silent-all-zero in the other, 8 "
                 "further informal repeats split 5/3)", "M4", ["EXP-0092"],
             "This is the ONLY validated write path to r64..r95 anywhere in the repository "
             "(EXP-0113). 96 is the hard register-file ceiling."),
    "dst_hi": F(HR, "the register EXTENSION half of the same lockstep 0..127 boundary sweep", "M4",
                ["EXP-0092"]),
    "form": F(CC, "byte0 bit3, set for the position-in-grid SR family; does not change the SR "
                  "select", "M4", ["EXP-M4-13"]),
    "dp_width": TOKF("Datapath width / dst-bank descriptor; located, semantics not established."),
    "dp_marker": F(STI, "fixed 32-bit-read marker 0x06 in every observed instance", "M4",
                   ["EXP-M4-13"]),
}

S["mov_imm"] = {
    "_default": U(),
    "_instruction": F(CC, "emitted for constant-folded builtins (threads_per_simdgroup = 0x20) and "
                          "tokenized; no synthesized instance independently executed", "M4+A18",
                      ["EXP-0031", "EXP-0010"]),
    "imm8": F(CC, "0x20 (=32) is the documented occurrence; the field was not swept", "A18",
              ["EXP-0031"]),
    "dst": U(),
}
S["uniform_mov"] = {
    "_default": U(),
    "_instruction": F(CC, "4-byte uniform->GPR copy located by own-MSL byte-diff", "A18",
                      ["EXP-0020"]),
    "usrc": F(CC, "uniform source index located; not swept (only one uniform is ever bound)",
              "A18", ["EXP-0020"]),
}
S["stop"] = {
    "_instruction": F(HR, "corrupting the whole word is a no-op - the program still terminates "
                          "correctly, so this is NOT a required terminator", "A18",
                      ["EXP-0003", "EXP-0010"]),
    "reserved": F(HR, "the full 24-bit body corrupted; HW-proven non-load-bearing padding", "A18",
                  ["EXP-0003", "EXP-0010"],
                  "The 'end-of-program flags/scope' hypothesis is DISPROVEN. True end-of-program "
                  "is out of band (the metadata code length). A driver emits 0x000000."),
}

# --- texture --------------------------------------------------------------
S["tex_sample"] = {
    "_default": U(),
    "_instruction": F(HR, "sample / gather / read / sample_compare / LOD-query executed; all 8 "
                          "compare functions HW-validated; gather offset affine and alias-free at "
                          "all 12 boundary/corner points", "M4+A18",
                      ["EXP-0016", "EXP-0034", "EXP-0106", "EXP-0114"]),
    "tex_slot": F(HR, "upper nibble 0x0..0xF EXHAUSTIVE (16/16) plus 12 representative low-nibble "
                      "values at both populated slots", "M4", ["EXP-0114", "EXP-0016"],
                  "RETRACTION: op+4 is NOT a stable per-texture binding index. Textures declared "
                  "at MSL indices 5/50/100 produce op4 sequence [0,128,0] - it names a short-lived "
                  "compiler-assigned register/uniform slot. Field is 4 bits (upper nibble); the "
                  "lower nibble is PROVABLY INERT. All 14 unpopulated nibble values are a "
                  "deterministic SILENT ZERO - never a fault, never an alias. The real 0..127 "
                  "binding-index selector lives in a still-UNDECODED preceding pointer-load."),
    "samp_slot_offset": F(IBD, "sampler slot 0x00 (s0) and 0x01 (s1) spliced (linear -> nearest); "
                               "out-of-range reads an unbound sampler (zeros). Constant gather "
                               "offset packs into the same byte: (1,0)->0x08, (1,1)->0x88",
                          "M4+A18", ["EXP-0016", "EXP-0034", "EXP-0106"],
                          "Gather offset is a signed [-8,7] per-axis field, HW-confirmed affine "
                          "and alias-free at all 12 boundary/corner points, and accepts a "
                          "genuinely dynamic per-lane offset (EXP-0106)."),
    "variant": F(HR, "dimension/LOD/compare codes 0x00,0x03,0x04,0x07,0x09,0x13,0x17,0x20,0x29,"
                     "0x37,0x39,0x53,0x79,0x80,0x97,0xc3 spliced and read back; a wrong dim code "
                     "silently reads the base slice or 0 (no hang)", "M4+A18",
                 ["EXP-0016", "EXP-0034", "EXP-M4-10"]),
    "mode": F(HR, "op+6 spliced 0x00 / 0x10 / 0x20 on a linear sample: filtering does NOT change "
                  "(a NEGATIVE result - filtering is the SAMPLER's job); 0x20 selects the "
                  "calculate_lod query", "A18", ["RT-5-isa-tex-simd-mat-rt-frag-falsify", "EXP-0016"],
              "RETRACTION: op+6 is NOT the filter selector."),
    "result_desc": F(IBD, "companion+3 0xa4/0xac/0xb4/0xbc - bit2 = gather, bits[3:5] = gather "
                          "component R/G/B/A, all four HW-validated", "A18", ["EXP-0034"]),
    "lod_present": F(CC, "op+7 bit2 = explicit LOD/bias present (own-MSL byte-diff)", "A18",
                     ["EXP-0034"]),
    "coord": F(CC, "op+1 coordinate register, located; the extra index operand (slice/face/z/"
                   "sample/ref) selected via op+3 is byte-diff only, NOT splice-validated",
               "A18", ["EXP-0016", "EXP-0034"]),
    "extra_coord": F(CC, "array layer = op+3>>3, 3D z = coord-imm & 0x7f, cube face = imm>>1, "
                         "MSAA sample = imm>>1 - splice-proven on M4 for the read path", "M4",
                     ["EXP-M4-10"]),
    "kind": F(CC, "companion low nibble 5 = sample/gather/read, 0xd = compute sample_compare",
              "A18", ["EXP-0016", "EXP-0034"]),
    "chain": F(CC, "bit5 marks a chained second texture op", "A18", ["EXP-0016"]),
    "result_sel": U(), "comp_flags": U(), "tex_type": U(), "samp_extra": U(),
}

S["tex_write"] = {
    "_default": U(),
    "_instruction": F(IBD, "texture write executed; proven a memory-family store, not the sampler "
                           "path", "A18", ["EXP-0016"]),
    "coord_dim": F(CC, "0x04 2d/2d_array, 0x08 3d, 0x0c cube (3 observed values)", "M4",
                   ["EXP-M4-13"]),
    "layer_reg": F(CC, "0x20 present for an array/layer store, 0 for plain 2d/3d", "M4",
                   ["EXP-M4-13"]),
    "seq_idx": F(CC, "0x88 + N for the Nth write in a shader", "M4", ["EXP-M4-13"]),
    "data_desc": F(CC, "0x3a/0x09 contiguous vec4 register block vs 0xfa/0x08 scattered sources",
                   "M4", ["EXP-M4-13"]),
    "data_desc_hi": F(CC, "second half of the same write-data descriptor", "M4", ["EXP-M4-13"]),
    "_note_slot": None,
}
del S["tex_write"]["_note_slot"]

S["tex_deriv"] = {
    "_default": U(),
    "_instruction": F(IBD, "dfdx/dfdy executed; implicit-LOD sampling does NOT emit this op",
                      "A18", ["EXP-0016"]),
    "axis": F(IBD, "0x92 = dfdx/X, 0x90 = dfdy/Y (2 of 256)", "A18", ["EXP-0016"],
              "Fine-vs-coarse derivative decode is an open follow-up."),
    "b1": TOKF(), "dstsrc": TOKF(), "src_comp": TOKF(), "tail": TOKF(),
}

S["tex_coord_setup"] = {
    "_default": U(),
    "_instruction": F(CC, "polymorphic 10-byte 0x2f form located over the own-MSL corpus", "M4",
                      ["EXP-M4-13"],
                      "The mnemonic is a MISNOMER: the same encoding also serves vertex "
                      "attribute-fetch address setup and float-classify (isnan/isnormal/frexp/"
                      "modf) ALU."),
    "srcA": F(CC, "byte+3 = srcA in the float-classify role", "M4", ["EXP-M4-13"]),
    "form": F(CC, "byte+4 0x42 (vertex attribute/varying address setup) vs {0x00,0x10,0x12,0x22} "
                  "(float-classify)", "M4", ["EXP-M4-13"]),
    "idx": F(CC, "byte+7 = dst-slot index (dst<<2) in the vertex-attribute role", "M4",
             ["EXP-M4-13"]),
}

S["tex_addr_setup"] = {
    "_default": U(),
    "_instruction": F(HR, "explicit-level sample executed against a 4x4x3 mip texture "
                          "(texel = 1000*L + 100*y + x) with every byte of the op swept", "A18",
                      ["EXP-M4-14"]),
    "form": F(HR, "0x00,0x01,0x05,0x07,0x0d swept: 0x01 coordinate projection (samples level 0), "
                  "0x05 sample-address + explicit LOD/gradient, 0x07 raw-coordinate passthrough, "
                  "0x0d alias of 0x05", "A18", ["EXP-M4-14"]),
    "cache": F(HR, "0x54,0x55,0x56,0x50,0x74,0x14 all give an identical sampled result - the WHOLE "
                   "byte is inert here", "A18", ["EXP-M4-14"]),
    "op_reg": F(HR, "0x00,0x02,0x04,0x06,0x08,0x0c,0x10,0x20,0x40,0xff swept: only 0x06 tracks the "
                    "LOD input (lod=1 -> 1100, lod=2 -> 2000); every other value reads a zero "
                    "register", "A18", ["EXP-M4-14"]),
    "op_hi": F(HR, "0x00 and 0x40 preserve the operand (bit6 inert); 0x02,0x04,0x08..0xff corrupt "
                   "it to level 0", "A18", ["EXP-M4-14"]),
    "op_reg2": F(HR, "0x0c -> L1, 0x02/0x06 -> L2, all other swept values -> L0", "A18",
                 ["EXP-M4-14"]),
    "rsv6": F(HR, "0x00..0x40 inert; only 0xff perturbs", "A18", ["EXP-M4-14"]),
    "op_mode": F(HR, "bit2 set {0x04,0x06,0x0c,0xff} keeps the operand active; bit2 clear "
                     "{0x00,0x02,0x08,0x10,0x20,0x40} makes it read 0", "A18", ["EXP-M4-14"]),
    "src_desc": F(HR, "only 0xf0 and 0xff preserve the operand; every value 0x00..0x40 makes it "
                      "read 0 (hi-nibble 0xf = 'operand is a register')", "A18", ["EXP-M4-14"]),
    "op_desc9": F(HR, "0xc0,0xc2,0xc4,0xc6,0xe4,0xf4 preserve; 0xc8,0xcc,0x44,0x84 drop the "
                      "operand (hi-nibble in {c,e,f} AND low-nibble in {0,2,4,6})", "A18",
                  ["EXP-M4-14"]),
    "op_cnt": F(HR, "0x08 -> L1, 0x0c -> L2, 0x18 -> L1, {0x00,0x04,0x0a,0x0e,0x10} -> L0", "A18",
                ["EXP-M4-14"]),
    "rsv11": F(HR, "0x00,0x02,0x04,0x06,0x08,0x0c,0x10,0x20,0x40,0xff all leave the result "
                   "unchanged - RESERVED pad", "A18", ["EXP-M4-14"]),
}

# --- subgroup -------------------------------------------------------------
S["simd_reduce"] = {
    "_default": U(),
    "_instruction": F(IBD, "simd_sum/prefix-scan executed and re-validated on a fresh compile "
                           "(simd_sum(int)=496)", "A18", ["EXP-0018", "RT-ISA-FIX"]),
    "dtype": F(IBD, "0x03 int-reduce, 0x07 int-minmax, 0x12 float-reduce, 0x09 inclusive-scan, "
                    "0x0b exclusive-scan; splicing 0x03 -> 0x01/0x07 left the sum unchanged, "
                    "refuting RT-5's competing enum", "A18", ["EXP-0018", "RT-ISA-FIX"]),
    "op": F(IBD, "(byte0 bit7, byte+1) op-select; float simd_product = 0xbf byte+1 0x06, "
                 "HW-validated against simd_sum", "A18", ["EXP-0018", "EXP-O2D"]),
    "scope": F(CC, "1 = SIMD-group, 0 = 2x2 quad (byte0 0xb7/0x37 quad forms)", "A18",
               ["EXP-0018"]),
    "dst": F(CC, "byte+3 (reg<<1): a 4-way live-reduce chain steps 0x0c,0x0a,0x06,0x02 with the "
                 "dst lane - own-MSL compile-only", "M4", ["EXP-M4-13"]),
    "src": F(CC, "byte+5 (reg<<2): steps 0x18,0x14,0x0c,0x04 with the src lane - own-MSL "
                 "compile-only", "M4", ["EXP-M4-13"],
             "CORRECTION: byte+4 (opmarker), previously labelled 'src', is a constant op-marker."),
    "opmarker": F(STI, "0x02 in every own compile; no variation observed", "M4", ["EXP-M4-13"]),
    "cache": TOKF("The literal 0x54/0x56 bit. DOWNGRADED to UNKNOWN - the original 'source "
                  "cache/last-use hint, not an op change' claim rested on a same-instruction "
                  "self-check that is structurally incapable of detecting a liveness bug "
                  "(EXP-0086). Emit exactly what you copied.", ev=["EXP-0086"] + CENSUS),
    "shape": U(), "b0hi": U(), "opcls": U(),
}

S["simd_shuffle"] = {
    "_default": U(),
    "_instruction": F(HR, "broadcast / xor / up / down / rotate executed; out-of-range behaviour "
                          "swept in both the dynamic and the static form", "M4+A18",
                      ["EXP-0018", "EXP-0104", "EXP-0115", "RT-ISA-FIX"]),
    "lane": F(HR, "28 swept points in the dynamic form and 60 independently constructed raw-byte "
                  "splices in the static form", "M4", ["EXP-0104", "EXP-0115"],
              "Out-of-range behaviour is NOT uniform across the family and NOT a wraparound: "
              "dynamic simd_shuffle aliases idx>=32 as (idx & 0x1C); the STATIC single-instruction "
              "form instead returns a HARD ZERO; simd_shuffle_xor and quad_shuffle hard-zero in "
              "both forms."),
    "mode": F(IBD, "0x00 quad, 0x04 SIMD, 0x05 simd_updown, 0x06 rotate/shuffle_and_fill", "A18",
              ["EXP-0018", "EXP-O2D"]),
    "dir": F(IBD, "byte0 bit7: 0x47 broadcast/up/fill_up vs 0xc7 xor/down/fill_down", "A18",
             ["EXP-0018"]),
    "dst": F(CC, "byte+3, located by own-MSL byte-diff", "M4", ["EXP-M4-13"]),
    "src": F(CC, "byte+4, located by own-MSL byte-diff", "M4", ["EXP-M4-13"]),
    "dsthi": F(CC, "byte+8 dst register high bits, located", "M4", ["EXP-M4-13"]),
    "cache": TOKF("Literal 0x54/0x56 bit - DOWNGRADED to UNKNOWN (EXP-0086).",
                  ev=["EXP-0086"] + CENSUS),
    "srctype": U(), "rtype": U(), "rsv9": TOKF(),
}

S["simd_ballot"] = {
    "_default": U(),
    "_instruction": F(HR, "3 genuinely divergent predicates; every lane reads back the identical "
                          "32-bit mask with bit i = predicate(lane i) exactly", "M4+A18",
                      ["EXP-0018", "EXP-0104", "RT-ISA-FIX"]),
    "pred": F(IBD, "byte+1 low nibble 0x7 identifies the family (splicing 0x17 -> 0x14 zeroes the "
                   "ballot); the HIGH nibble (0x07 active-mask/any/all vs 0x17 ballot(predicate)) "
                   "is NOT cleanly splice-convertible - its operands co-vary", "A18",
              ["RT-ISA-FIX", "RT-10-isa-pass2"],
              "Treat the high nibble as a decode label, not an independently settable field."),
    "dst": F(CC, "byte+3 destination mask register, located", "M4", ["EXP-M4-13"]),
    "psrc": F(CC, "byte+4 predicate source register, located", "M4", ["EXP-M4-13"]),
    "psrctype": U(), "form": U(), "form_sig": TOKF(), "cache": TOKF(),
}

# --- atomics --------------------------------------------------------------
ATOM_OPS = ("add 0x20, and 0x22, cmpxchg 0x24, fadd 0x26, smax 0x28, smin 0x2a, or 0x2c, "
            "sub 0x36, umax 0x38, umin 0x3a, xchg 0x3c, xor 0x3e, add_indexed 0x60")
for m in ("atomic_rmw", "atomic_mem"):
    S[m] = {
        "_default": U(),
        "_instruction": F(HR, "1024 threads -> counter 1024; op-splice add->max -> 32; "
                              "sign-straddle proven (init=1, v0=-1: smax->1, umax->0xFFFFFFFF, "
                              "smin->-1, umin->1)", "M4+A18", ["EXP-0018", "EXP-M4-10"]),
        "op": F(HR, "all 13 op codes spliced and observed: " + ATOM_OPS, "M4+A18",
                ["EXP-0018", "EXP-M4-10"],
                "The same 5-bit op enum is shared with atomic_tg (at bits 86-91). 64-bit atomics "
                "are ENTIRELY absent from MSL, so there is no width field to find (EXP-O2D)."),
        "base_slot": F(CC, "same base-slot model as device_load; located, not independently swept "
                           "on the atomic path", "A18", ["EXP-0018"]),
        "index_reg": F(CC, "per-lane index GPR, zeroed for a uniform address", "M4", ["EXP-M4-13"]),
        "per_lane": F(CC, "1 for a divergent per-lane address (&o[i]), 0 for a uniform address "
                          "(&o[0]); byte+13 bit1 tracks the same choice", "M4", ["EXP-M4-13"]),
        "amode": F(CC, "0x11 selects the ALU/reduced/immediate-operand form, 0x01 the "
                       "register-operand form", "M4", ["EXP-M4-13"]),
        "ret_flag": F(CC, "byte+7 bit0 = discard/no-writeback", "M4", ["EXP-M4-13"]),
        "ret_desc": F(CC, "byte+8 return-register descriptor", "M4", ["EXP-M4-13"]),
        "op_lsb": TOKF(), "op_msb": TOKF(), "rsv3": TOKF(), "rsv10": TOKF(), "rsv11": TOKF(),
        "addr_desc": TOKF(), "idx_off": TOKF(), "amode_hi": TOKF(),
    }
S["atomic_tg"] = {
    "_default": U(),
    "_instruction": F(IBD, "threadgroup atomics executed via own MSL", "M4+A18",
                      ["EXP-0018", "EXP-M4-12"]),
    "op": F(CC, "the SAME 5-bit op enum as the device atomics, relocated to bits 86-91: "
                + ATOM_OPS, "M4", ["EXP-M4-13"],
            "Enum values are HW-validated on the DEVICE atomic (EXP-0018/EXP-M4-10); their reuse "
            "at this bit position is a structural/corpus finding, not an independent splice."),
    "amode": F(CC, "0x56 direct-value amode for atomic_exchange, 0x54 for ALU/simd-reduced RMW",
               "M4", ["EXP-M4-13"]),
    "ret_desc": F(CC, "0x03 when the old value is consumed, 0x00 noret", "M4", ["EXP-M4-13"]),
    "op_desc": F(CC, "byte+5/+8 operand-register descriptors step together (0x02/0x22 returning, "
                     "0x01/0x20 noret, 0x00/0x02 xchg & cmpxchg)", "M4", ["EXP-M4-13"]),
    "data_desc": F(CC, "second half of the same stepping operand pair", "M4", ["EXP-M4-13"]),
    "rsv4": TOKF(), "rsv6": TOKF(), "xop_desc": TOKF(), "rsv9": TOKF(), "rsv10lo": TOKF(),
    "op_hi_rsv": TOKF(),
}

# --- matrix / RT ----------------------------------------------------------
S["matrix_mac"] = {
    "_default": U(),
    "_instruction": F(HR, "A*B+C with distinct known A,B,C read back over one 32-lane simdgroup; "
                          "all four of A*B / B*A / A*A / B*B distinguished", "A18",
                      ["EXP-0022", "EXP-O2C", "RT-10-isa-pass2"]),
    "a_reg": F(HR, "spliced to B's register -> B*B; swapped with byte+6 -> B*A (matmul is "
                   "non-commutative, so the operand identity is unambiguous)", "A18",
               ["EXP-O2C", "RT-10-isa-pass2"]),
    "b_reg": F(HR, "swapped with byte+5 -> B*A", "A18", ["EXP-O2C", "RT-10-isa-pass2"]),
    "c_src": F(IBD, "accumulator source register, splice-validated", "A18", ["EXP-O2C"]),
    "dst": F(IBD, "destination fragment register, splice-validated", "A18", ["EXP-O2C"]),
    "a_desc": F(IBD, "corrupting byte+3 zeroes the result - load-bearing, not padding", "A18",
                ["EXP-O2C"]),
    "op_enable": F(IBD, "0x24 enables the multiply; corrupting it drops the multiply and passes C "
                        "through", "A18", ["EXP-O2C", "RT-10-isa-pass2"],
                   "The 0x24 value is FP32-DATAPATH-SPECIFIC. The half datapath (dtype 0x00) uses "
                   "byte+10 = 0x8c / byte+11 = 0x00 and its accumulate byte is UNCHARACTERIZED."),
    "acc_en": F(IBD, "0x01 -> a*b+c, 0x00 -> a*b (simdgroup_multiply clears it)", "A18",
                ["EXP-O2C"],
                "FP32 datapath only; the half-datapath accumulate byte is uncharacterized (RT-10)."),
    "dtype": F(IBD, "0x00 half, 0x02 float/bfloat; splicing 0x02 -> 0x00 garbles fp32", "A18",
               ["EXP-O2C"]),
    "mode": F(IBD, "0x56 standalone, 0x54 tiled; splicing standalone -> tiled ZEROES the result "
                   "(tiled sources its accumulator from the MPP tile context) - SEMANTIC, not a "
                   "scheduling hint", "A18", ["EXP-O2C"]),
    "pad4": F(HR, "splice-inert padding", "A18", ["EXP-O2C"]),
    "dst_desc": TOKF(), "b11hi": TOKF(),
}

RT_INERT = ("RETRACTION: rt_intersect operand SUB-FIELDS are byte-diff correlations, NOT "
            "splice-validated. RT-5/RT-10 found every documented sub-field splice-INERT on the "
            "single-primitive intersection_query path. The earlier 'EXP-O2C 0x8b->0x1b "
            "HW-validated end-to-end' note is retracted; primitive-vs-instance dispatch is "
            "STRUCTURAL (kernel shape), not a spliceable field.")
S["rt_intersect"] = {
    "_default": U(RT_INERT),
    "_instruction": F(HR, "6 known rays against a built acceleration structure returned correct "
                          "t/prim/barycentrics; corrupting byte+1 0xea -> 0x00 hangs the GPU on "
                          "the traverse op and perturbs the distance on the result-read op",
                      "A18", ["EXP-0023", "RT-5-isa-tex-simd-mat-rt-frag-falsify"]),
    "subop": F(IBD, "0xea vs 0x00 - the op itself is load-bearing", "A18",
               ["RT-5-isa-tex-simd-mat-rt-frag-falsify"]),
    "as_type": F(CC, "0x8b primitive AS, 0x6b instance AS, 0xbb primitive-motion AS - a real "
                     "byte-diff correlate, but splicing it is INERT (0x8b/0x6b/0x1b/0x00 all give "
                     "the identical correct hit; only 0xff faults)", "A18",
                 ["RT-10-isa-pass2", "EXP-O2C"], RT_INERT),
    "mode": F(CC, "0x90 const origin, 0x10 dynamic-origin or motion, 0xd0 const-origin + "
                  "function-table, 0x11 result-read - byte-diff only, splice-INERT", "A18",
              ["RT-5-isa-tex-simd-mat-rt-frag-falsify", "EXP-O2C"], RT_INERT),
    "dst": F(CC, "byte0 high nibble; splicing 0xe4 -> 0x04/0x14 produced no change", "A18",
             ["RT-5-isa-tex-simd-mat-rt-frag-falsify"], RT_INERT),
    "flags": F(CC, "byte+6 bit7 set when an intersection_function_table is bound", "A18",
               ["EXP-0023"]),
    "ray_param": F(CC, "ray/parameter operand register; also carries the motion TIME "
                       "(device-loaded 0x46 vs folded-constant 0x26)", "A18", ["EXP-O2C"], RT_INERT),
}
for m in ("rt_as_load", "rt_ray_mem"):
    S[m] = {
        "_default": U(),
        "_instruction": F(CC, "14-37 per RT kernel; the traversal loop they drive was executed end "
                              "to end, but no field of this op was independently synthesized",
                          "A18", ["EXP-0023", "EXP-O2C"]),
        "field_off": F(CC, "the immediate offset that selects WHICH BVH-node / ray / query-state "
                           "field is fetched - there is no per-field opcode; located by byte-diff",
                       "M4", ["EXP-M4-13"]),
        "elem_size": TOKF(), "width": TOKF(), "off_lo": TOKF(), "off_hi": TOKF(),
        "flags": TOKF(), "reserved7": TOKF(), "reserved13": TOKF(), "mode": TOKF(),
    }
for m in ("rt_ray_mem_ldidx", "rt_ray_mem_short", "rt_transform_test", "rtq_dualsrc",
          "rt_query_traverse2"):
    S[m] = {"_default": TOKF("Length anchored over the own-MSL corpus; operand roles located by "
                             "byte-diff only. Per clean-room rule 5 the traversal arithmetic is "
                             "not reconstructed."),
            "_instruction": F(CC, "located and length-anchored over the own-MSL RT corpus", "M4",
                              ["EXP-M4-13"])}
S["rt_ray_mem_ldidx"]["addr_mode"] = F(CC, "byte-diff shows IDENTICAL ldidx bytes for instance_id "
                                           "vs geometry_id loads - a NEGATIVE result confirming "
                                           "the field is not a per-field selector", "M4",
                                       ["EXP-M4-13"])
S["rt_query_traverse"] = {
    "_default": U(),
    "_instruction": F(HR, "intersection_query committed-distance against a 2-triangle AS "
                          "(near t=1 / far t=5) with every byte of the load-bearing op swept",
                      "A18", ["EXP-M4-14"]),
    "opB": F(HR, "0x00,0x02,0x06,0x07,0x0a,0x0f,0x1a,0x20,0x40,0x42,0x48,0x50,0x60,0xc8,0xff "
                 "swept: {0x42,0x48,0xc8} give the correct near hit, {0x00,0x0a,0x0f,0x1a,0x20,"
                 "0x50,0x60,0xff} skip it, {0x02,0x06,0x07,0x40} HANG the traversal (contained)",
             "A18", ["EXP-M4-14"],
             "The correct-value set is NOT a simple linear register index; the class/index bit "
             "split is not decoded."),
    "sel": F(HR, "0x00,0x02,0x06,0x07,0x0a,0x0f,0x1a,0x20,0x40,0x48,0x50,0x60,0xff swept: "
                 "0x07=sel0 and 0x0f=sel1 preserve correctness, other values corrupt operand "
                 "selection. Only the committed-path op is load-bearing; the other 17 rtq ops in "
                 "the kernel are inert on this byte", "A18", ["EXP-M4-14"]),
    "opA": F(HR, "0x18, 0x1a, 0x00, 0xff swept - INERT on the load-bearing committed-path instance",
             "A18", ["EXP-M4-14"], "Role UNRESOLVED; kept raw."),
    "dst": U(),
}
S["ray_move"] = {
    "_default": U(),
    "_instruction": F(CC, "35-38 per kernel; also reused for MPP matmul2d TRANSPOSE tile data, so "
                          "matrix transpose is data movement, not a matrix opcode", "M4+A18",
                      ["EXP-O2C", "EXP-M4-13"]),
    "form": F(CC, "0x81 copy a computed source, 0x80 zero-initialise a component", "M4",
              ["EXP-M4-13"]),
    "b3": F(IBD, "0x08 reg32 plain copy, 0x00 zero, 0x12/0x22 uniform/high-class copy, 0x06 zero "
                 "variant; bit6 (0x40) on a uniform-class-source copy -> CMDBUF_ERROR, inert on "
                 "plain copies", "A18", ["EXP-M4-14"],
            "NEGATIVE (splice): the b3/src VALUE semantics could NOT be resolved - all 16 ray_move "
            "ops are INERT to committed_distance in the intersection_query testbed, because the "
            "traversal re-derives origin/direction from the direct device loads."),
}
for m in ("ray_move_copy6", "ray_move_zero6", "ray_move_zinit", "rtq_state_move"):
    S[m] = {"_default": U(),
            "_instruction": F(CC, "4-byte ray/query marshalling move located over the own-MSL RT "
                                  "corpus", "M4", ["EXP-M4-13"]),
            "form": F(CC, "byte+2 discriminates the sub-form (0x41 copy / 0x40 zero / 0x80 "
                          "zero-init / 0x09 query-state)", "M4", ["EXP-M4-13"])}
S["rtq_pred"] = {"_instruction": F(TOK, "byte-invariant 4-byte token (06 c2 00 00); exact micro-op "
                                        "NOT characterized", CENSUS_T, CENSUS)}
S["sfu_marker"] = {"_instruction": F(TOK, "byte-invariant 2-byte token (06 02); exact micro-op NOT "
                                          "characterized", CENSUS_T, CENSUS)}

# --- fences / barriers ----------------------------------------------------
S["threadgroup_barrier"] = {
    "_default": U(),
    "_instruction": F(HR, "256-thread divergent-writer litmus: neutralising the barrier makes "
                          "128/256 lanes read stale zeros with STATUS OK and no fault", "M4+A18",
                      ["EXP-0025", "EXP-0093"]),
    "sub": F(IBD, "0x04 compute threadgroup/execution barrier, 0x14 texture ACQUIRE, 0x02 fragment "
                  "tile-access barrier", "M4+A18", ["EXP-0093", "EXP-0025"],
             "CORRECTION (EXP-0093): compute threadgroup_barrier(mem_texture) is a genuine "
             "ACQUIRE (sub=0x14) / RELEASE (sub=0x04) instruction PAIR; an earlier note recorded "
             "sub=0x04 for both members."),
    "mem_scope": F(IBD, "0x41 mem_none, 0x61 mem_threadgroup, 0x85 mem_device, 0x51/0xd1 "
                        "mem_texture; bidirectional splice of bit0 (0x85 <-> 0x84) both adds and "
                        "removes execution convergence (128/256 vs 0/256 divergent lanes)",
                   "M4+A18", ["EXP-0093", "EXP-0025"],
                   "byte+3 bit0 is the EXECUTION-CONVERGENCE enable, independent of the requested "
                   "memory-fence class. Splicing 0x61 -> 0x00 makes 128/256 lanes read stale "
                   "zeros - the exact silent-corruption hazard a driver must get right."),
    "flags": F(CC, "0x09 threadgroup/none, 0x08 device, 0x0e texture (own-MSL byte-diff)",
               "M4", ["EXP-0093"]),
    "b5": F(STI, "0x00 in every own-MSL compile and across the corpus", "M4+A18", ["EXP-0025"]),
}
S["mem_fence"] = {
    "_default": U(),
    "_instruction": F(IBD, "standalone device fence: symmetric (both-sides-fenced) message passing "
                           "gives 0/1350 mismatches; relaxed emits no fence at all and corrupts up "
                           "to 100% of messages once concurrency crosses ~4 pairs", "M4",
                      ["EXP-0093", "EXP-O2D"]),
    "sub": F(CC, "byte+1 0x04 for the 6-byte fence form", "M4", ["EXP-0093"]),
    "memclass": F(CC, "byte+4 0x0a device memory-class flag (byte+3 0x84 device vs the barrier's "
                      "0x85 = 0x84|0x01)", "M4", ["EXP-0093", "EXP-O2D"]),
    "b5": F(STI, "0x00 in every observed instance", "M4", ["EXP-0093"]),
}
S["pixel_order"] = {
    "_default": U(),
    "_instruction": F(IBD, "raster-order-group mutual exclusion: neutering either half of the "
                           "acquire/release pair reproduces the race on an otherwise "
                           "byte-identical binary; an identity-splice control rules out the "
                           "splice mechanism as a confound (16/16 cases)", "M4",
                      ["EXP-0093", "EXP-0029"]),
    "kind": F(IBD, "0x14 acquire/wait vs 0x04 release/signal; BOTH independently necessary "
                   "(neither half is redundant)", "M4", ["EXP-0093"]),
    "scope": F(CC, "{0x50, 0xd0} observed (bit7 differs, acquire vs release)", "M4",
               ["EXP-0029", "EXP-O2D"]),
    "flags": F(CC, "0x06 raster-order/texture fence flag", "M4", ["EXP-0093", "EXP-O2D"]),
    "b5": F(STI, "0x00 in every observed instance", "M4", ["EXP-0029"]),
}
S["scoreboard_fence"] = {
    "_default": U(),
    "_instruction": F(CC, "4-byte 0x07 fence located over the own-MSL corpus around calls and "
                          "break/continue divergence", "A18", ["EXP-0025", "RT-ISA-FIX"]),
    "kind": F(CC, "0x22 (pre-call), 0x02 / 0x00 (control-flow) observed", "A18", ["RT-ISA-FIX"]),
    "scope": TOKF("byte+2 in {0x00,0x02} is the length discriminator against the 6-byte "
                  "0x07-family forms."),
    "mask": TOKF(),
}
S["dev_scoreboard_fence"] = {
    "_default": U(),
    "_instruction": F(CC, "0x80 wide-scope sibling of the 0x07/0x87 fence family, located over the "
                          "own-MSL corpus", "M4", ["EXP-M4-13", "EXP-M4-01"]),
    "scope_flag": F(CC, "0x00 dominant, 0x04 in one rare texture_sample occurrence", "M4",
                    ["EXP-M4-13"]),
}
S["compute_fence_scoped"] = {
    "_default": TOKF("0x87 high-scope fence variants; operand VALUE maps are partial."),
    "_instruction": F(CC, "byte+1 in {0x9e,0x8e,0x90,0x86,0x00} and byte+2 in {0x26,0x80,0x02} "
                          "observed over the corpus", "M4", ["EXP-M4-13"]),
}
S["mem_fence8"] = {
    "_default": TOKF(),
    "_instruction": F(CC, "8-byte byte+4==0x80 scope form emitted by intersection_query traversal; "
                          "located over the corpus", "M4", ["EXP-M4-13"]),
    "mask": F(CC, "byte+3 0x14 / 0x0c observed", "M4", ["EXP-M4-13"]),
}
S["link_save_restore"] = {
    "_default": U(),
    "_instruction": F(HR, "3-level-deep non-leaf call chain executed; in a RACE-FREE frame the op "
                          "is a no-op fence and every payload field is inert, in a SPILLING frame "
                          "(12 live temporaries) byte0 0x07 -> 0x00 corrupts the SAVE and HANGS "
                          "the RESTORE", "A18", ["EXP-M4-14", "EXP-0035", "EXP-0038"]),
    "scope": F(HR, "0x00, 0x01, 0x80, 0x81, 0x83, 0xff swept: 0x81/0x83 pass (bit7 AND bit0 both "
                   "set), 0x00/0x80/0x01 corrupt the SAVE and HANG the RESTORE, 0xff -> GPU "
                   "page-fault", "A18", ["EXP-M4-14"]),
    "dir_offset": F(HR, "SAVE=0x0000, RESTORE=0x1fff, plus a systematic scaling sweep "
                        "(+5: 0x00->0x01->0xff; +6: 0x00->0x01->0x1f) showing corruption scaling "
                        "with the value", "A18", ["EXP-M4-14"],
                    "CORRECTION: dir_offset is 16-bit (bytes+5/+6), NOT the DB's former 24-bit "
                    "field - byte+7 is reserved and inert on both instances."),
    "marker": F(HR, "0x00, 0x04, 0x54, 0x55, 0xff all reproduce the baseline - RESERVED/inert",
                "A18", ["EXP-M4-14"]),
    "b3": F(HR, "0x00, 0x01, 0xff all reproduce the baseline - RESERVED/inert", "A18",
            "EXP-M4-14".split()),
    "b1": F(HR, "0x00, 0x01 inert; only 0xff perturbs the result", "A18", ["EXP-M4-14"]),
    "reserved7": F(HR, "0x00, 0x01, 0xff on both the SAVE and the RESTORE instance - inert",
                   "A18", ["EXP-M4-14"]),
}
S["frame_prologue"] = {
    "_default": U(),
    "_instruction": F(HR, "non-leaf callee frame executed; every byte of the prologue swept",
                      "A18", ["EXP-M4-14", "EXP-0038", "EXP-0035"]),
    "subop": F(HR, "0x00,0x01,0x02,0x03,0x04,0x0b,0x13,0x23,0x43 swept: only values with "
                   "bits[1:0]==0b11 run (0x03/0x0b/0x13/0x23/0x43); 0x00/0x01/0x02/0x04 fault",
               "A18", ["EXP-M4-14"]),
    "marker": F(HR, "0x00, 0x04, 0x54, 0x55, 0xff all run to baseline - RESERVED/inert", "A18",
                ["EXP-M4-14"]),
    "frame_size": F(HR, "bytes+3/+4 at 0x00/0x01/0x08/0xff (nonzero -> huge frame -> GPU fault); "
                        "byte+5 at 0x10, 0x1f, 0x20, 0x21, 0x30, 0x40", "A18", ["EXP-M4-14"],
                    "16-byte granular; over-allocation is tolerated (0x20 -> 0x30) but too small "
                    "or misaligned faults. NOT cleanly monotonic - 0x40 faults while 0x30 runs - "
                    "so the sub-field layout is NOT fully resolved."),
}
S["spill_frame_marker"] = {
    "_default": U(),
    "_instruction": F(HR, "byte0/+1/+2 sweeps are runtime no-ops for the tested computation; "
                          "byte+3 = 0xff faults. EXACT ROLE UNRESOLVED", "A18",
                      ["EXP-M4-14", "EXP-0041"],
                      "EXP-0041 found this exact word ABSENT from all nine retained M4 own mains "
                      "including 208-576 B declared scratch, so it is NOT a universal spill marker."),
    "b3": F(HR, "0xff faults; the other swept values are inert - the only live byte", "A18",
            ["EXP-M4-14"]),
    "b1": F(HR, "swept, runtime-inert", "A18", ["EXP-M4-14"]),
    "b2": F(HR, "swept, runtime-inert", "A18", ["EXP-M4-14"]),
}
S["tg_addr_compute"] = {
    "_default": U(),
    "_instruction": F(HR, "threadgroup-tile reduction executed (o[i] = 2i+3) with every byte "
                          "swept", "A18", ["EXP-M4-14"]),
    "b3": F(HR, "0x00, 0x01, 0x08, 0x40, 0xff individually AND ff/ee/dd on +3/+4/+5 "
                "simultaneously - output unchanged; RESERVED/inert", "A18", ["EXP-M4-14"]),
    "b4": F(HR, "0x00, 0x01, 0xff plus the simultaneous splice - inert", "A18", ["EXP-M4-14"]),
    "b5": F(HR, "0x00, 0x01, 0xff plus the simultaneous splice - inert", "A18", ["EXP-M4-14"]),
}
S["frame_marker_compact"] = {"_default": TOKF(),
                             "_instruction": F(TOK, "2-byte compact marker, length-anchored",
                                               CENSUS_T, CENSUS)}
S["cubearray_coord_const"] = {"_default": TOKF(),
                              "_instruction": F(TOK, "4-byte constant word feeding the cube-face "
                                                     "coordinate math; length-anchored", "M4",
                                                ["EXP-M4-12"])}
S["frame_marker"] = {
    "_default": U(),
    "_instruction": F(CC, "the `43 00 00 01` call/frame-setup form precedes every out-of-line "
                          "CALL; located over the own-MSL corpus", "A18", ["EXP-0035", "EXP-0030"],
                      "CORRECTION (EXP-0035): this is the GENERIC call/frame marker, not a "
                      "mesh-emit op. Mesh set_vertex/set_index/set_primitive lower to ordinary "
                      "0xe7/0xd7 stores."),
    "srcA_reg": F(CC, "byte+1 bits0-6 source register in the ordinary compact-move role", "M4",
                  ["EXP-M4-13"]),
    "srcA_uni": F(CC, "byte+1 bit7 uniform-file/high-half flag", "M4", ["EXP-M4-13"]),
    "subform": F(CC, "source-class/size sub-form", "M4", ["EXP-M4-13"]),
    "companion": F(CC, "0x01 = the zero-extend companion; other values carry a second-operand "
                       "descriptor", "M4", ["EXP-M4-13"]),
}

# --- fragment / interpolation --------------------------------------------
S["iter"] = {
    "_default": U(),
    "_instruction": F(IBD, "per-component varying interpolation executed; redirecting the slot "
                           "moved the output from color.x to color.y", "A18",
                      ["EXP-0029", "EXP-0031"]),
    "src_slot": F(IBD, "0x00 -> 0x02 (slot<<1): switched the interpolated output from color.x to "
                       "color.y", "A18", ["EXP-0029"]),
    "mode": F(IBD, "0x00 pixel-centre/linear, 0x02 centroid or per-sample, 0x04 perspective "
                   "denominator (3 of 256)", "A18", ["EXP-0029"],
              "Perspective-correct interpolation is a MULTI-INSTRUCTION lowering, not a mode bit."),
    "dst": F(CC, "byte+3 destination GPR, located by own-MSL byte-diff", "A18", ["EXP-0029"]),
    "loc": U(), "grp": U(), "lead": U(), "coeff_sel": U(), "c7": U(), "b9": U(),
}
S["iter_at"] = {
    "_default": U(),
    "_instruction": F(CC, "centroid / per-sample setup located by own-MSL byte-diff", "A18",
                      ["EXP-0029"]),
    "loc": F(CC, "byte+7 0x01 centroid, 0x03 sample (2 observed values)", "A18", ["EXP-0029"]),
}
S["iter_flat"] = {
    "_default": TOKF(),
    "_instruction": F(CC, "[[flat]] emits this distinct 6-byte op (no barycentric interpolation); "
                          "own-MSL byte-diff", "A18", ["EXP-0029"]),
}
S["frag_color_store"] = {
    "_default": U(),
    "_instruction": F(IBD, "fragment colour output executed; discard_fragment proven to suppress "
                           "the store", "M4+A18", ["EXP-0029", "EXP-0111"]),
    "src": F(IBD, "byte+3 source colour GPR, splice-proven", "A18", ["EXP-0029"]),
    "rt_index": F(IBD, "RT0=0x00, RT1=0x02, RT2=0x04 (rt<<1), splice-proven; MRT emits one store "
                       "per target", "A18", ["EXP-0029"]),
    "fmt": F(CC, "byte+7 tracks the ATTACHMENT format, proven by a colour-format sweep with the "
                 "shader return width held at float4: RGBA8Unorm/sRGB/BGRA8=0x4e, "
                 "RGBA16Float=0x0e, RGBA32Float=0x2e, R32Float=0x22, R8Unorm=0x42", "M4",
             ["EXP-M4-13", "EXP-0108"]),
    "store_mode": F(STI, "0x54 in 130/130 corpus stores - no variation observed", "M4",
                    ["EXP-M4-13"]),
    "flags": F(CC, "0x00 in every plain store; 0x08 in the MRT/array-slice variant", "M4",
               ["EXP-M4-13"]),
    "mask": F(CC, "0x01 in plain stores", "M4", ["EXP-M4-13"]),
    "slice_addr": F(CC, "0x00000000 in single-RT stores; carries the layer/slice address only in "
                        "array-target stores", "M4", ["EXP-M4-13"]),
}
S["frag_color_pack"] = {
    "_default": U(),
    "_instruction": F(HR, "colour pack executed against a real render target with per-component "
                          "pixel readback; every byte of the former raw 24-bit fmt_word swept",
                      "A18", ["EXP-M4-14"]),
    "src_present_mask": F(HR, "0x10, 0x40, 0x50, 0x60, 0xd0, 0xe0, 0xff swept on BOTH pack ops: "
                              "0x10 = component-0 only, 0x40 = component-1 only, 0x50/0xd0 = both, "
                              "0x60/0xe0 = both zeroed, 0xff = ILLEGAL, hard GPU fault", "A18",
                          ["EXP-M4-14"],
                          "RETRACTION: the 24-bit fmt_word is NOT an inert attachment-format "
                          "constant. byte+7 == 0xff hard-faults the GPU."),
    "src_gate_select": F(HR, "0x00,0x01,0x05,0x40,0x41,0x42,0x43,0x44,0x45,0x46,0x47,0x80,0x85,"
                             "0xff swept on both pack ops: bit2 gates both components, bit6 gates "
                             "component 0, and the low bits can REROUTE which source channel "
                             "feeds a slot; no value in the swept range faults", "A18",
                         ["EXP-M4-14"]),
    "conv_scale": F(HR, "0x00,0x42,0x80,0x82,0xc0,0xc1,0xc2,0xff swept: bit1 = component-1 enable, "
                        "bits6-7 = scale/exponent (0x82 halves G from 0x80 to 0x40); extreme "
                        "values alias/overflow across the 2-wide pair; no value faults", "A18",
                    ["EXP-M4-14"]),
    "val": F(CC, "byte+6 carries the colour component value", "A18", ["EXP-M4-14"]),
    "fmt_class": F(CC, "0x54 tilebuffer/attachment (fragment) vs 0x56 compute pack", "M4",
                   ["EXP-M4-13"]),
    "dst": U(), "src_desc": U(), "mode": U(), "comp_off": U(),
}
S["tile_read"] = {
    "_default": U(),
    "_instruction": F(IBD, "programmable blend proven in-shader: out = src*0.5 + clear*0.5", "A18",
                      ["EXP-0019", "EXP-0029"]),
    "rt_index": F(CC, "render-target index, located by own-MSL byte-diff", "A18", ["EXP-0029"]),
    "dst": F(CC, "byte+3 destination GPR, located", "A18", ["EXP-0029"]),
    "b2": TOKF(), "b4": TOKF(), "b6": TOKF(), "b7": TOKF(), "tail": TOKF(),
}
S["tile_read_mrt"] = {
    "_default": TOKF(),
    "_instruction": F(CC, "plain-read sibling of tile_read; located over the own-MSL corpus", "M4",
                      ["EXP-M4-13"]),
    "rt_index": F(CC, "render-target / imageblock-slice selector, located", "M4", ["EXP-M4-13"]),
    "dst": F(CC, "byte+3 destination GPR, located", "M4", ["EXP-M4-13"]),
}
for m in ("imageblock_store", "imageblock_load"):
    S[m] = {
        "_default": U(),
        "_instruction": F(IBD, "explicit imageblock read/write executed end to end (a tile kernel "
                               "overwrote an RGBA16F attachment)", "A18", ["EXP-O2D"]),
        "slice_off": F(IBD, "0x00 / 0x04 / 0x08 for imageblock struct fields at byte offsets "
                            "0 / 8 / 16 (offset>>1), HW-proven", "A18", ["EXP-O2D"],
                       "Explicit imageblocks address by BYTE OFFSET; simple MRT "
                       "frag_color_store addresses by RT INDEX (rt<<1). Do not conflate them."),
        "fmt": F(CC, "0x0e half4, 0x22 float (2 observed values)", "A18", ["EXP-O2D"]),
        "b4": TOKF(), "b6": TOKF(), "tail": TOKF(),
    }
S["frag_tile_setup"] = {
    "_default": U(),
    "_instruction": F(CC, "emitted around each colour store and tilebuffer read; located by "
                          "own-MSL byte-diff", "M4", ["EXP-M4-13", "EXP-O2D"]),
    "sel": F(CC, "steps 0x0c -> 0x30 -> 0xc0 across RT0/RT1/RT2 and 0x00/0x08 around a tile read",
             "M4", ["EXP-M4-13"]),
    "access": F(CC, "0x06 store-setup vs 0x08 tile-read (own-MSL render byte-diff)", "M4",
                ["EXP-M4-13"]),
    "b1": F(STI, "0x02 in every observed instance", "M4", ["EXP-M4-13"]),
    "b5": F(STI, "0x00 in every observed instance", "M4", ["EXP-M4-13"]),
}
S["frag_depth_store"] = {
    "_default": TOKF(),
    "_instruction": F(CC, "[[depth]] output op located by own-MSL byte-diff; distinct from the "
                          "16-byte texture write that shares byte0 0xd7", "A18", ["EXP-0029"]),
}
S["n3_sample_read"] = {"_default": TOKF(),
                       "_instruction": F(CC, "fragment sample-id / sample-position read, located "
                                             "over the corpus", "M4", ["EXP-M4-13"])}

# --- vertex / varying -----------------------------------------------------
S["vary_store"] = {
    "_default": U(),
    "_instruction": F(IBD, "redirecting a store slot moved that varying to a different FS channel",
                      "A18", ["EXP-0037", "EXP-0029"],
                      "MIS-TOKENIZATION FLAGGED: this descriptor currently also swallows the "
                      "6-byte fragment kill/target-mask op (byte0=0x57, byte+2=0x54) as an 8-byte "
                      "vertex vary_store. A proper split is a pending DB change (EXP-0091)."),
    "src": F(IBD, "byte+3 source GPR (reg<<1), in-order 0,2,4,..,14 over r0..r7", "A18",
             ["EXP-0037"]),
    "out_slot": F(IBD, "[[position]].xyzw = 0x00/0x20/0x40/0x60 (slots 0-3), user varyings "
                       "0x80/0xa0/0xc0/0xe0 (slots 4-7)", "A18", ["EXP-0037"],
                  "Position vs varying is the SLOT RANGE, not a distinct opcode."),
    "out_slot_hi": F(CC, "byte+5 bit0 extends the slot to 8-15 (wraps byte+4 back through 0x00)",
                     "M4", ["EXP-M4-13"]),
    "b5_tag": F(STI, "constant 0x20 tag in every observed instance", "M4", ["EXP-M4-13"]),
    "hint2": F(CC, "carries the same 0x54/0x55/0x56 data-source mode as the device_store amode",
               "M4", ["EXP-M4-13"]),
    "hint1": U(), "hint6": U(), "b7": U(),
}
S["vary_slot"] = {
    "_default": U(),
    "_instruction": F(CC, "slot descriptor emitted immediately before each vary_store; located "
                          "over the corpus", "M4", ["EXP-M4-13"]),
    "slot": F(CC, "byte+3 monotone, tracks the following store's slot", "M4", ["EXP-M4-13"]),
    "sel": F(CC, "{0x04,0x0a,0x0c} output-class forms observed", "M4", ["EXP-M4-13"]),
}
S["vtx_out_pos"] = {
    "_default": U(),
    "_instruction": F(CC, "vertex output-position op; length corrected to 8 to remove the dominant "
                          "spurious 0x40 desync", "M4", ["EXP-M4-13"]),
    "slot": F(CC, "0x04/0x08/0x0c/0x10/0x14 observed", "M4", ["EXP-M4-13"]),
}
S["vtx_coord_xform"] = {"_default": TOKF("Operand bytes deliberately left raw - the "
                                         "coordinate-select sequence is not reconstructed "
                                         "(clean-room rule 5)."),
                        "_instruction": F(CC, "statically separated from simd_ballot by the fixed "
                                              "byte+2==0xa2 / byte+3==0xb0 pair", "M4",
                                          ["EXP-M4-13"])}
S["mesh_out_src"] = {"_default": TOKF(),
                     "_instruction": F(CC, "2-byte mesh compact source op feeding the following "
                                           "0xe7 store; located over the corpus", "M4",
                                       ["EXP-M4-13", "EXP-0030"])}

# --- half / bfloat --------------------------------------------------------
S["half_alu"] = {
    "_default": U(),
    "_instruction": F(HR, "native fp16 add/mul executed with distinct per-lane inputs; every "
                          "operand byte swept", "A18", ["EXP-M4-14", "EXP-0033"]),
    "srcA": F(HR, "0x02, 0x04, 0x06, 0x08 swept: only 0x02 reads a; every other value makes srcA "
                  "read 0 so the result is b alone", "A18", ["EXP-M4-14"],
              "RETYPES the former 'srcB@byte+3' label - byte+3 is the FIRST, negatable source."),
    "srcB": F(HR, "0x00, 0x02, 0x04, 0x06, 0x08 swept: 0x00/0x04 read b, 0x02/0x06 null the op, "
                  "0x08 gives a+const", "A18", ["EXP-M4-14"]),
    "src_modifier": F(HR, "byte+5 swept with distinct per-lane inputs: bits6:7 (0xc0) are a "
                          "required operand-valid base (clearing them yields 0), bit3 (0x08) = "
                          "srcA-negate (0xc8 -> -a+b), bit0 suppresses srcB, bits1/2 suppress "
                          "srcA", "A18", ["EXP-M4-14"]),
    "opsel": F(IBD, "0x1c hadd vs 0x1d hmul (byte+2 low 3 bits), splice-observed", "A18",
               ["EXP-M4-14", "EXP-0033"]),
    "dst": U(), "opflags": U(),
}
S["half_alu_ext8"] = {
    "_default": U(),
    "_instruction": F(HR, "half add+saturate and half fma executed; byte+7 swept", "A18",
                      ["EXP-M4-14", "EXP-0033"]),
    "saturate": F(HR, "byte+7 0x82 clamps saturate(9) to 1; 0x80 (bit1 clear) passes 9 unclamped; "
                      "0xc0 also passes", "A18", ["EXP-M4-14"]),
    "op_valid_marker": F(HR, "every byte+7 value WITHOUT bit7 set nulls the op (result 0) - a "
                             "required op-valid marker", "A18", ["EXP-M4-14"]),
    "srcA": F(HR, "byte+3 0x02 works, 0x04/0x06 break; byte+6 swept 0x00..0xc0 all inert", "A18",
              ["EXP-M4-14"]),
    "opsel": F(IBD, "gains 6 = hfma (byte+2 = 0x1e); half fma compiles to this 8-byte form", "A18",
               ["EXP-M4-14"]),
    "rsv6": F(HR, "0x00..0xc0 swept, every value kept the result - fully INERT/reserved in the "
                  "add+saturate instance", "A18", ["EXP-M4-14"]),
    "b5": F(HR, "bits3/4 null in this instance; largely inert", "A18", ["EXP-M4-14"]),
    "srcB_desc": F(IBD, "0x01 required in the add+saturate instance; carries the fma srcA-negate "
                        "(byte+7 0xc0 -> 0xc8)", "A18", ["EXP-M4-14"]),
    "b7_lo": U("Remaining byte+7 bits - unresolved."),
    "b7_mid": U("Remaining byte+7 bits - unresolved."),
    "dst": U(), "opflags": U(),
}
S["half_alu_fma12"] = {
    "_default": U(),
    "_instruction": F(HR, "fma(abs(a),b,c) compiles to a clean 12-byte 0x10 op and executes "
                          "correctly (a=[-8,-2,-4,-1], b=1, c=[1,2,4,8] -> [9,4,8,9])", "A18",
                      ["EXP-M4-14"],
                      "LENGTH-RULE DEFECT FLAGGED: a fixed 'always 12B for byte0==0x10' rule is "
                      "WRONG. Own-MSL plain half fma is only 8B, and 121/126 corpus instances "
                      "embed a real op-leader byte (0x9f iadd, 0xa8, 0x54, 0xe7) inside `ext`."),
    "srcA": F(HR, "byte+4 0x83 -> fma(|a|,b,c); 0x82 -> |a| alone; 0x80 -> 0", "A18",
              ["EXP-M4-14"]),
    "opsel": F(IBD, "6 = hfma (byte+2 = 0x1e)", "A18", ["EXP-M4-14"]),
    "ext": TOKF("KEPT RAW and flagged: this descriptor's 12-byte length OVER-CONSUMES a following "
                "instruction leader in 121/126 corpus instances.", ev=["EXP-M4-14"] + CENSUS,
                target="A18"),
    "dst": U(), "opflags": U(),
}
S["half_pack"] = {
    "_default": U(),
    "_instruction": F(IBD, "float2 -> fp16 round trip executed; confirmed 4 bytes across half2 "
                           "add / mul / fma", "A18", ["EXP-0038", "EXP-0033"]),
    "dstlo": F(CC, "byte0 high nibble = dst; the same op appears as 0x08/0x18/0x28/0x38 for "
                   "r0/r1/r2/r3", "A18", ["EXP-0038"]),
    "src": F(CC, "byte+2 = source register", "A18", ["EXP-0038"]),
    "b3": TOKF(),
}
for m in ("h_alu_hi", "h_alu_hi_ext", "h_coord_hi", "h_coord_hi_ext", "packed_half2_hi"):
    S[m] = {"_default": U("Layout inherited from the HW-anchored half_alu / falu2 families; not "
                          "independently exercised in the high-half form."),
            "_instruction": F(CC, "high-half / packed-half2 forms located over the own-MSL corpus "
                                  "(byte0 low-nibble 8, high nibble = dst)", "M4",
                              ["EXP-M4-13", "EXP-M4-01"]),
            "opsel": F(CC, "0x1c hadd / 0x1d hmul / 0x1e hfma (h_alu_hi) or 0x24 / 0x26 / 0x2e "
                           "(packed and coordinate forms) - the SAME enum as the 0x09/0x10 "
                           "families, located by corpus", "M4", ["EXP-M4-13"])}
S["cvt_f2h_dst"] = {"_default": U(),
                    "_instruction": F(CC, "generalises the byte0==0x11 cvt_f2h to r0..r15; located "
                                          "over the corpus", "M4", ["EXP-M4-13"]),
                    "opsel": F(CC, "0x1c base convert, 0x3c same convert with the source-mode bit "
                                   "set", "M4", ["EXP-M4-13"])}
S["cvt_bf16"] = {"_default": U(),
                 "_instruction": F(CC, "bfloat convert located by own-MSL byte-diff", "M4",
                                   ["EXP-M4-13", "EXP-O2D"]),
                 "srcw": F(CC, "0x03 float32 source, 0x02 float16 source", "M4", ["EXP-M4-13"]),
                 "dir": F(CC, "0x40 result bfloat, 0x80 result half", "M4", ["EXP-M4-13"])}
for m, opv in (("bf_add_dst", "0x1c add"), ("bf_mul_dst", "0x1d mul"), ("bf_fma_dst", "0x1e fma")):
    S[m] = {"_default": U(),
            "_instruction": F(CC, "native bfloat " + opv + " for any dst register; generalises the "
                                  "HW-spliced byte0==0x11 bf_alu", "M4", ["EXP-M4-13", "EXP-O2D"]),
            "fmt": F(CC, "0x02 scalar / 0x04 bfloat2-packed lane", "M4", ["EXP-M4-13"])}
S["bf_alu8_var"] = {"_default": TOKF("Role-typed from the bf_add_dst layout; the byte+1/byte+2 "
                                     "op-select value map and the per-bit tail map need a splice."),
                    "_instruction": F(CC, "byte+1 != 0x02 residual of the 0x11 group", "M4",
                                      ["EXP-M4-13"])}

# --- misc / catch-alls ----------------------------------------------------
S["ibitcount"] = {
    "_default": U(),
    "_instruction": F(HR, "popcount executed on inputs [15,16,65535,0x40000001] -> [4,1,16,2] "
                          "with every operand byte swept", "A18", ["EXP-M4-14", "EXP-0033"]),
    "form": F(HR, "(byte0 bit7, byte+1): (0x27,0x05) popcount, (0xa7,0x05) find_msb -> [3,4,15,30], "
                  "(0xa7,0x04) reverse_bits", "A18", ["EXP-M4-14"],
              "CORRECTION: the sub-op selector is (byte0 bit7 + byte+1), NOT byte+4."),
    "fn_hi": F(HR, "byte0 bit7 spliced 0x27 <-> 0xa7", "A18", ["EXP-M4-14"]),
    "op_enable": F(HR, "byte+4 swept 0x00..0x0a: only bit1 matters - 0x02/0x03/0x06/0x07/0x0a "
                       "compute, 0x00/0x01/0x04/0x05/0x08/0x09 give 0", "A18", ["EXP-M4-14"],
                   "CORRECTION: byte+4 is an op-ENABLE gate, NOT the sub-op selector. The former "
                   "'optype 0x02 popcount vs 0x03 find_msb' label was correlation, not causation."),
    "dst": F(HR, "byte+3 swept 0x00/0x02/0x04/0x06/0x08 (reg<<1): non-zero breaks delivery "
                 "([0,0,0,0])", "A18", ["EXP-M4-14"]),
    "src": F(HR, "byte+5 swept 0x00/0x04/0x08/0x0c/0x10 (reg<<2): non-zero points at an empty "
                 "register so popcount(0)=0", "A18", ["EXP-M4-14"]),
    "srcdesc": F(HR, "byte+6 swept: 0x00 degenerates the op to identity (raw input returned, "
                     "popcount NOT applied); bit6 (0x40) must be set for the GPR source to be read "
                     "(0x3c/0x9c -> 0; 0x5c/0x4e/0x58/0x5e/0x7c/0xdc read normally)", "A18",
                 ["EXP-M4-14"]),
    "cache": U("A18<->M4 CONTRADICTION, UNRESOLVED - the only direct cross-target contradiction "
               "in this corpus. EXP-M4-14 (A18 Pro) recorded that only byte+2 0x54/0x55 (bit1 "
               "clear) BREAK the stored result while 0x56 writes back. EXP-0119 (M4) re-spliced "
               "EXP-M4-14's OWN literal anchor bytes (27 05 56 00 02 00 5c 04 / 27 05 54 ...) and "
               "got the CORRECT popcount either way, with the src operand unconditionally released "
               "to two independent later readers REGARDLESS of the bit. A dispatch-shape confound "
               "(EXP-M4-14 used a real multi-thread kernel; EXP-0119 used grid=1/tg=1) is not "
               "ruled out. Semantics NOT established - do not emit a chosen value here."),
    "tail": F(STI, "0x04 marker in every observed instance", "A18", ["EXP-M4-14"]),
}
S["irotate"] = {"_default": TOKF(),
                "_instruction": F(CC, "rotate-by-immediate is a single 12-byte 0x27 op; "
                                      "rotate-by-register is a multi-instruction lowering", "A18",
                                  ["EXP-0033"])}
S["ibfins"] = {
    "_default": U(),
    "_instruction": F(CC, "shift-left / bitfield-insert; byte-identical to the 0xa7 ibfe except "
                          "byte0", "M4", ["EXP-M4-13", "EXP-0033"],
                      "insert_bits has NO dedicated op in MSL lowering (mask + shift + combine); "
                      "this is the shl/insert mirror of the extract family."),
    "srcdesc": F(CC, "byte+8 0xf0 register operand / 0xc0 immediate operand", "M4", ["EXP-M4-13"]),
    "form": F(CC, "byte+1 sub-op select, located", "M4", ["EXP-M4-13"]),
    "mask_imm": F(CC, "scattered mask immediate (byte+5 + byte+6 bit0)", "M4", ["EXP-M4-13"]),
    "mask_hi": F(CC, "high bit of the scattered mask immediate", "M4", ["EXP-M4-13"]),
    "dst": F(CC, "byte+3 (reg<<1)|size, located", "M4", ["EXP-M4-13"]),
    "cache": TOKF("Literal 0x54/0x56 bit - DOWNGRADED to UNKNOWN (EXP-0086).",
                  ev=["EXP-0086"] + CENSUS),
}
S["ibfe_mesh_attr"] = {"_default": TOKF(),
                       "_instruction": F(CC, "bitfield-extract of a packed flat per-primitive mesh "
                                             "attribute (source-address mode byte+2==0x66)", "M4",
                                         ["EXP-M4-13"])}
S["pack_convert"] = {"_default": TOKF("byte+5..+9 format-conversion / rounding descriptor kept raw "
                                      "(n=4, not individually decoded)."),
                     "_instruction": F(CC, "pack_float_to_unorm2x16 / snorm / half located by "
                                           "own-MSL byte-diff", "A18", ["EXP-0033"]),
                     "src": F(CC, "byte+3 source GPR, located", "M4", ["EXP-M4-13"]),
                     "fmt_class": F(CC, "byte+2==0x56 gates the compute pack form", "M4",
                                    ["EXP-M4-13"])}
S["unpack_convert"] = {
    "_default": U(),
    "_instruction": F(CC, "unpack_unorm2x16_to_float / snorm located by own-MSL byte-diff; "
                          "separated from simd_ballot on byte+1's low nibble (ballot=7, unpack=4)",
                      "A18", ["EXP-0038", "RT-ISA-FIX"]),
    "cache": F(HR, "bit17 at {0,1} corrupts BOTH the instruction's own result AND a later reader; "
                   "the other 7 bits of the same byte re-swept individually, ALL with no "
                   "detectable effect", "M4", ["EXP-0089", "EXP-0119"],
               "This is the LITERAL 0x54/0x56 bit that RT-1a-FIX called an inert cache hint. It is "
               "load-bearing here. CAVEAT: db.json's own match table forces every other bit of "
               "this byte, so the 7-bit resweep constructed bytes that do not re-decode as "
               "unpack_convert - an open self-consistency question (EXP-0119 section 2.5)."),
    "reg_sel": F(CC, "byte+7 high nibble steps e/b/c/a/6/3 across successive unpacks in one "
                     "kernel; most likely the result destination (role INFERRED, not "
                     "splice-confirmed)", "M4", ["EXP-M4-13"]),
    "size": F(CC, "byte+7 low nibble, 0xa typical", "M4", ["EXP-M4-13"]),
    "convert_desc": TOKF("Format-conversion descriptor, kept raw."),
    "src_class": TOKF("Low nibble 0x04 is forced by the match."),
}
S["carry_gen"] = {
    "_default": U(),
    "_instruction": F(IBD, "u64 add carry chain executed; neutralising the 0x32 op drops the "
                           "carry (splice-proven load-bearing)", "A18", ["EXP-0038", "EXP-0033"]),
    "cmpmode": F(CC, "byte+4==0x22 ordered-compare mode", "A18", ["EXP-0038"]),
    "subop": F(CC, "byte+2==0x35 carry-generate marker", "A18", ["EXP-0038"]),
    "dst": U(), "srcA": U(), "b5": TOKF(),
}
S["copysign"] = {"_default": TOKF(),
                 "_instruction": F(CC, "4-byte 0x07 low-nibble-7 sign-combine ALU; out-specifies "
                                       "scoreboard_fence on 24 vs 9 match bits", "M4",
                                   ["EXP-M4-13"])}
S["fldexp"] = {"_default": TOKF(),
               "_instruction": F(CC, "emitted only for the dynamic-exponent ldexp (the "
                                     "constant-exponent form folds to an fmul)", "M4",
                                 ["EXP-M4-13"])}
S["coord_madf"] = {"_default": TOKF("Body kept raw."),
                   "_instruction": F(CC, "byte0-LEADER 0x2e form gated on byte+2==0x23; the far "
                                         "more common case is a 0x09 float op handled by the "
                                         "float op-select length rule", "M4",
                                     ["EXP-0037", "EXP-M4-13"])}
S["funary_imm"] = {"_default": U(),
                   "_instruction": F(CC, "own-MSL orimm (a|0x100) reproduces the byte+2==0x0f form "
                                         "byte-exact", "M4", ["EXP-M4-13"]),
                   "src": F(CC, "byte+1 low bit = size (b32=1) in 760/763 corpus instances - the "
                                "(reg<<1)|size convention, so byte+1 is the source operand, not "
                                "byte+3", "M4", ["EXP-M4-13"]),
                   "modtail": TOKF(), "lut_a": TOKF(), "mod": TOKF(), "srcB": TOKF(),
                   "form": TOKF(), "dst": U()}
S["sr_read_wide"] = {
    "_default": U(),
    "_instruction": F(CC, "8-byte member of the get_sr low-nibble-4 datapath family; located over "
                          "the own-MSL corpus (n=996)", "M4", ["EXP-M4-13"]),
    "dst": F(CC, "byte0 high nibble proven to span r0..r15 by an own-MSL sweep (compile-only)",
             "M4", ["EXP-M4-13"]),
    "phase": F(CC, "byte+7 0x80 marks the CANDIDATE (during-traversal) property read, 0x00 the "
                   "COMMITTED (post-traversal) read; 0x20 a further candidate sub-variant",
               "M4", ["EXP-M4-13"],
               "SUPERSEDES an earlier n=26 'const 0x00 reserved byte' note."),
    "sel": F(CC, "0x7f simd-matrix wide builtin, 0x00 wide scalar base, 0x21/0x01/0x48 "
                 "intersection_query property reads", "M4", ["EXP-M4-13"]),
    "width": F(CC, "toggles 0x02<->0x06 across successive component reads; 0x22/0x26/0x46 across "
                   "property kinds", "M4", ["EXP-M4-13"]),
    "operand": F(CC, "steps 0x00,0x10,0x18,.. with the wide-component index as dst advances",
                 "M4", ["EXP-M4-13"]),
    "marshal": TOKF("Getter/element operand descriptor; the marshal SEQUENCE is deliberately not "
                    "reconstructed (clean-room rule 5)."),
}
for m in ("n3_mov", "shift_amt_move", "reg_move_c2var"):
    S[m] = {"_default": U(),
            "_instruction": F(CC, "compact 4-byte move family located over the own-MSL corpus",
                              "M4", ["EXP-M4-13", "EXP-0036"]),
            "dst": F(CC, "byte0 high nibble proven a destination register by parallel-extend diffs "
                         "/ an own-MSL reg sweep (compile-only)", "M4", ["EXP-M4-13"]),
            "src_reg": F(CC, "byte+1 bits0-6 source register", "M4", ["EXP-M4-13"]),
            "src_flag": F(CC, "byte+1 bit7 uniform-file / high-half flag", "M4", ["EXP-M4-13"])}
S["n3_mov"]["srcA_reg"] = S["n3_mov"].pop("src_reg")
S["n3_mov"]["srcA_uni"] = S["n3_mov"].pop("src_flag")
S["n3_mov"]["companion"] = F(CC, "0x01 with subform 0x00 is the zero-extend high-half-zero "
                                 "companion", "M4", ["EXP-M4-13"])
S["shift_amt_move"]["kind"] = F(CC, "byte+2 low nibble 0xc: 0x1c shift, 0x3c rotate", "M4",
                                ["EXP-M4-13"])

REGMOVE_NOTE = (
    "RETRACTION / HARD NEGATIVE: the five reg_move_* descriptors are ONE instruction with a single "
    "8-bit byte+2 field, and NONE of them is a general GPR-to-GPR move. The readback is independent "
    "of the producer's VALUE and of the producer's FAMILY, depends only on src_reg, is "
    "register-pair-quantized (reg and reg^1 read identically) and varies with the kernel's buffer "
    "signature - the signature of a fixed per-kernel PRELOADED/UNIFORM-FILE slot. The 0x00000100 "
    "seen on failure is that slot's content, not a sentinel. byte+2 values 0x26 and 0x0F are "
    "NONDETERMINISTIC across runs. AS OF 2026-08-28 NO VALIDATED GPR-TO-GPR MOVE EXISTS ON APPLE9.")
for m in ("reg_move_c0", "reg_move_c1", "reg_move_c9", "reg_move_cb"):
    S[m] = {
        "_default": U(REGMOVE_NOTE),
        "_instruction": F(HR, "byte+2 swept across 26+ raw values with paired producer-value and "
                              "producer-family controls, in two independent gated runs", "M4",
                          ["EXP-0087", "EXP-0090", "EXP-0101", "EXP-0113"], REGMOVE_NOTE),
    }
S["reg_move_c0"]["src_reg"] = F(HR, "producer-independent and register-PAIR-quantized at every one "
                                    "of 4 tested pairs; src_reg is ALWAYS 0 in all 1545 corpus "
                                    "instances", "M4", ["EXP-0101", "EXP-0113"], REGMOVE_NOTE)
S["reg_move_c1"]["src_reg"] = F(HR, "4 src_reg values (0,2,4,8) x 3 buffer-count variants: content "
                                    "was uniformly 0 in all 12 cases, both runs", "M4",
                                ["EXP-0101", "EXP-0113"], REGMOVE_NOTE)
S["reg_move_c9"]["src_reg"] = F(HR, "4 tested register pairs, both runs: X and X^1 read identical "
                                    "content, producer-independent", "M4", ["EXP-0113"],
                                REGMOVE_NOTE)
for m in ("reg_move_c0", "reg_move_c1", "reg_move_c9"):
    S[m]["op_desc"] = F(HR, "bit2 (0x04) redirects the write to a different register; only "
                            "byte+2=0x01 with op_desc=0x08 and src_flag=0 ever moved a value, and "
                            "even that is UNIFORM-SOURCED ONLY", "M4",
                        ["EXP-0087", "EXP-0090", "EXP-0101"], REGMOVE_NOTE)
    S[m]["src_class"] = F(HR, "byte+2 high nibble swept; most values are SILENT NO-OPS that zero "
                              "the destination (26 raw cases)", "M4", ["EXP-0087", "EXP-0101"],
                          REGMOVE_NOTE)
S["tg_atomic_prep"] = {"_default": TOKF(),
                       "_instruction": F(CC, "threadgroup-atomic RMW descriptor prep, located over "
                                             "the corpus", "M4", ["EXP-M4-13"])}
S["n3_addr_prep"] = {
    "_default": U(),
    "_instruction": F(CC, "emitted ONLY by 2D read_write texture ops; isolated with controlled "
                          "own-MSL variants (k_add / k_addy0 / k_tex_atomic)", "A18",
                      ["EXP-M4-14"]),
    "dst": F(CC, "tracks register allocation across controlled own-MSL variants (r3 in "
                 "k_tex_atomic, r1 in k_add, r0/r1 in k_addy0)", "A18", ["EXP-M4-14"]),
    "src_reg": F(CC, "the two preps of an op pair differ by 2 in the index (0x8a/0x8c, 0x84/0x86); "
                     "bit7 set in all instances", "A18", ["EXP-M4-14"]),
    "op_variant": F(CC, "0xbf atomic_fetch_add, 0x36 atomic_fetch_max, 0x22 texture read - "
                        "co-varies exactly with which texture op the prep feeds", "A18",
                    ["EXP-M4-14"]),
    "src_companion": F(CC, "byte+4 moves in lockstep with src_reg (delta 4 vs delta 2)", "A18",
                       ["EXP-M4-14"]),
    "tail": F(STI, "all instances end 02 00 00 00 00 with byte+5 always 0x02; one outlier carried "
                   "0x20 at byte+8", "A18", ["EXP-M4-14"]),
}
S["int_alu_ehi"] = {
    "_default": TOKF("Located by role only, from committed permissively licensed Dawn/Tint "
                     "std140 shaders - NOT own-MSL single-toggle. Our own MSL emits 0x9f (iadd) "
                     "for equivalent integer address math, so this form could not be reproduced."),
    "_instruction": F(CC, "0xef std140 uniform->storage matrix-copy form", "M4", ["EXP-M4-13"]),
    "dst": F(CC, "byte+3 register, located", "M4", ["EXP-M4-13"]),
}
S["b_alu14_c83"] = {"_default": TOKF("Operand/format bit TYPES resolved; the exact arithmetic is "
                                     "NOT resolved (needs splice)."),
                    "_instruction": F(CC, "14-byte byte+2==0x83 integer/simd ALU located over the "
                                          "corpus", "M4", ["EXP-M4-13"])}
S["b_alu14_prep2"] = {"_default": TOKF("byte+1 == (dst<<1)|1 is a SEMANTIC invariant used to "
                                       "separate genuine prep words from trailing data words."),
                      "_instruction": F(CC, "2-byte compact prep word preceding a b_alu14", "M4",
                                        ["EXP-M4-13"])}
for m in ("b_alu10_lo7", "b_alu10_loe", "b_alu10_lof"):
    S[m] = {"_default": U(),
            "_instruction": F(CC, "0x?b 10-byte modifier/convert/setup ALU located over the "
                                  "own-MSL corpus (n=919 / 25 / 484)", "M4", ["EXP-M4-13"]),
            "dst": F(CC, "byte0 high nibble proven a destination register by an own-MSL reg sweep "
                         "(compile-only)", "M4", ["EXP-M4-13"]),
            "src_reg": F(CC, "byte+1 bits0-6 source register (covaries with dst across the "
                             "subgroup-matrix load/store sweep)", "M4", ["EXP-M4-13"]),
            "src_flag": F(CC, "byte+1 bit7 source-class / uniform flag", "M4", ["EXP-M4-13"]),
            "opsel_hi": F(CC, "byte+2 high nibble op-select family (0x27 tex/operand-setup "
                              "dominant, 0x17 `& mask`, 0x07 base, 0x47/0x57/0x67)", "M4",
                          ["EXP-M4-13"]),
            "z6": F(STI, "const 0 across all corpus instances", "M4", ["EXP-M4-13"]),
            "ext8": F(CC, "0x00 dominant, 0x10 in 176/919 (b_alu10_lo7)", "M4", ["EXP-M4-13"]),
            "ext9": F(STI, "const 0 across all corpus instances", "M4", ["EXP-M4-13"]),
            "srcA": F(CC, "byte+3 second-source descriptor (0x81 = single-source marker)", "M4",
                      ["EXP-M4-13"]),
            "modA": TOKF(), "modB": TOKF(), "outmod": TOKF()}
S["op04_len8"] = {
    "_default": TOKF("The 6-byte body is HETEROGENEOUS: audited over the full corpus this token "
                     "fires 205x on own compute kernels + 618x on third-party, and byte+2 spans "
                     "real op-leader bytes {0x00,0x9f,0x1b,0x02,0xe7,0x20,0x80,0x62,0x72,0x52,"
                     "0x39,...}. Typing it would fabricate a coherence the data contradicts.",
                     ev=["EXP-M4-14", "EXP-M4-13"], target="A18"),
    "_instruction": F(HR, "HW-VALIDATED NEGATIVE: renamed from the misleading `frag_pos_read`. "
                          "[[position]]/[[front_facing]] lower to get_sr + iter, splice-confirmed "
                          "on live A18; this 8-byte op materialises from NONE of 7 distinct "
                          "own-MSL fragment provocations", "A18", ["EXP-M4-14", "EXP-M4-13"],
                      "LENGTH-RULE DEFECT FLAGGED: the fixed 8-byte length for byte0==0x04 is a "
                      "CANDIDATE OVER-CONSUMER of a following instruction leader."),
}
for m in ("n2_compact2", "n2_op8", "n2_op10", "n4_cf_word", "n4_rt_word", "n1_word", "n3_word",
          "pad_operand", "operand_word", "operand_word_x2_h5", "operand_word_x2_h6",
          "operand_word_x2_h7", "operand_word_a2_01"):
    S[m] = {"_default": TOKF("Length/framing token. Value bits deliberately NOT decoded "
                             "(clean-room rule 5: no SFU range-reduction / marshalling recipe)."),
            "_instruction": F(TOK, "length-anchored over the own-MSL corpus (+4/+2 lands on the "
                                   "next op leader in every occurrence); exact micro-op role "
                                   "NOT characterized", CENSUS_T, CENSUS)}
S["falu_acc"] = {
    "_default": U(),
    "_instruction": F(IBD, "compact 4-byte float accumulate executed in a reduction", "A18",
                      ["EXP-0025", "RT-1a-FIX"]),
    "cache": F(IBD, "0x18 <-> 0x38 spliced: the reduction result is unchanged", "A18",
               ["RT-1a-FIX", "EXP-0025"],
               "CAVEAT: this was a SAME-INSTRUCTION self-check, structurally incapable of "
               "detecting a register-liveness effect on a LATER reader. EXP-0086 downgraded the "
               "whole 0x54/0x56/0x18/0x38 class to UNKNOWN. Do NOT treat as inert."),
    "op": F(CC, "byte+2 arithmetic-enable bit clear distinguishes it from the 6-byte fadd", "A18",
            ["EXP-0025"]),
    "dst": U(), "srcA": U(), "srcB": U(),
}
S["falu_compact4"] = {
    "_default": U(),
    "_instruction": F(CC, "compact float ALU modes 0x18/0x38/0x19/0x21/0x30/0x31/0x39 observed "
                          "over the own-MSL corpus", "M4", ["EXP-M4-01", "EXP-M4-13"]),
    "opmode": F(CC, "7 observed byte+2 values; the 0x30/0x31 pair carries the source cache / "
                    "last-use hint bit", "M4", ["EXP-M4-13"]),
    "dst": U(), "src": U(), "opsel": U(), "operand": U(),
}
for m in ("falu2_srcmod10", "falu_srcmod12b"):
    S[m] = dict(S["falu2"])
    S[m] = {k: v for k, v in S[m].items() if k in ("dst", "srcA_size", "srcA_reg", "srcB_size",
                                                   "srcB_reg", "srcB_imm", "srcB_neg", "mod_lo",
                                                   "mod_hi", "ctrl")}
    S[m]["_default"] = U()
S["falu2_srcmod10"]["_instruction"] = F(CC, "10-byte abs-source form; length 6+2*(byte+4&3) with "
                                            "byte+4 low2==2, located over the corpus", "M4",
                                        ["EXP-M4-10", "EXP-M4-13"])
S["falu2_srcmod10"]["ext_srcmod"] = TOKF("32-bit source-modifier / trailing-operand word.")
S["falu2_srcmod10"]["opsel"] = F(CC, "opsel 4=fadd / 5=fmul, identical to falu2_ext", "M4",
                                 ["EXP-M4-13"])
S["falu2_srcmod10"]["opflags"] = U()
S["falu_srcmod12b"]["_instruction"] = F(HR, "12-byte 2-source extended form constructed and "
                                            "executed OUTSIDE a loop; reproduces falu2's clean "
                                            "single-target bit19 contract exactly", "M4",
                                        ["EXP-0119", "EXP-0089"])
S["falu_srcmod12b"]["opflags"] = F(HR, "bits19/20/21 individually at {0,1} with opsel_mod=0: "
                                       "bit19 = release srcA (matches falu2 exactly), bits20/21 "
                                       "NULL for this construction", "M4", ["EXP-0119"],
                                   "Resolves EXP-0089's open question: the widened/anomalous "
                                   "loop_boundary behaviour is attributable to LOOP REPETITION, "
                                   "not to the 12-byte form itself.")
S["falu_srcmod12b"]["opsel"] = F(HR, "opsel_mod 0..7 exhaustive: 0 is the only clean value; 4 "
                                     "CORRUPTS an entirely unrelated, independently seeded "
                                     "register (r6) that a later reader then reads as zero; "
                                     "1,2,3,5,6,7 give a locally contained 0.0 own-result", "M4",
                                 ["EXP-0119"],
                                 "A field this project's own tooling modelled as an innocuous "
                                 "`mod` byte is, for at least one value, an out-of-spec encoding "
                                 "with a blast radius WIDER than the instruction's own operands.")
S["falu_srcmod12b"]["ctrl"] = F(HR, "relative bit2 (absolute instruction bit 34) at {0,1}: outside "
                                    "a loop it runs STATUS OK (own result becomes 0.0, later "
                                    "reader unaffected); the SAME bit inside a loop produced a "
                                    "genuine GPU HANG in EXP-0089", "M4", ["EXP-0119", "EXP-0089"],
                                "The hang requires the loop context. One negative data point, not "
                                "an exhaustive sweep of the interaction space.")
S["falu_srcmod12b"]["ext_srcmod"] = TOKF("48-bit 3rd-source + modifier region; values need splice.")
S["falu3_srcmod12"] = {
    "_default": U(),
    "_instruction": F(HR, "12-byte 3-source form constructed and executed; addressing validated "
                          "on both operand slots", "M4", ["EXP-0119"]),
    "srcA_reg": F(HR, "value {3,67} addressing cross-check (67 reads r3, never the unwritten r67)",
                  "M4", ["EXP-0119"], ALIAS_NOTE),
    "srcB_reg": F(HR, "value {3,67} addressing cross-check", "M4", ["EXP-0119"], ALIAS_NOTE),
    "ext_srcmod": TOKF("48-bit 3rd source + modifier region; UNCHARACTERIZED (EXP-0119 says so "
                       "explicitly - the 3rd source of this family was not testable)."),
    "opflags": U("Lifetime contract for this family is UNTESTED - EXP-0119 could not validate the "
                 "own-result formula, so only ADDRESSING is established here."),
}
S["falu2_ext8b"] = {
    "_default": U(),
    "_instruction": F(CC, "8-byte op-select {0,1} sub-form (bit17==0 AND bit18==0), a distinct op "
                          "class from fadd/fmul; located over the corpus", "M4", ["EXP-M4-13"]),
    "src2": F(CC, "byte+4 third source register: low bit set in every corpus instance, 22 distinct "
                  "register values", "M4", ["EXP-M4-13"]),
    "exttail": TOKF("KEPT RAW and FLAGGED: heterogeneous (193/250 distinct 32-bit tails, several "
                    "containing real op-leader bytes such as 0xa7) - a candidate over-match / "
                    "over-consumption.", ev=["EXP-M4-13"] + CENSUS, target="M4"),
}
S["cvt_i2f_src"] = {
    "_default": U(),
    "_instruction": F(CC, "byte+1==0x17 sibling of cvt_i2f; the convert and its width/sign fields "
                          "are identical to the HW-validated cvt_i2f", "M4+A18",
                      ["EXP-0013", "EXP-M4-13"]),
    "signflag": F(CC, "byte+7 bit6 = signed i2f vs unsigned u2f", "M4+A18",
                  ["EXP-0013", "EXP-M4-13"]),
    "src_cache": TOKF("byte+1 bit4 marks source-consumed-by-a-following-ALU routing; byte+2 "
                      "0x54 vs 0x56 is the literal cache bit - DOWNGRADED to UNKNOWN (EXP-0086).",
                      ev=["EXP-0086"] + CENSUS),
    "dst_desc": U(), "src_class": U(), "src": U(), "cvtop": U(),
}

# --- corrections to the two dict-copied float forms (do NOT inherit falu2's sweeps) ---
for _m in ("falu2_srcmod10", "falu_srcmod12b"):
    for _f in ("dst", "srcA_size", "srcA_reg", "srcB_size", "srcB_reg", "srcB_imm", "srcB_neg",
               "mod_lo", "mod_hi"):
        S[_m][_f] = U("Bit position inherited from the HW-validated falu2 layout; NOT "
                      "independently exercised in this extended form.")
S["falu2_srcmod10"]["ctrl"] = U("Bit position inherited from falu2; not exercised in this form.")
S["falu_srcmod12b"]["srcA_reg"] = F(IBD, "r3 (seeded) and r6 (positive control, separately seeded "
                                         "to 12.0) - 2 register values with the predicted effect",
                                    "M4", ["EXP-0119"])
S["falu_srcmod12b"]["srcB_reg"] = U("Not exercised in this form.")

# --- explicit emittable VETOes -------------------------------------------
# docs/evidence-classification.md's rule is "every field an EMITTER MUST FILL". Where a
# load-bearing byte is proven live but is NOT modelled as a field in db.json, the descriptor
# cannot honestly be called emittable no matter how its listed fields are labelled.
EMITTABLE_VETO = {
    "tg_addr_compute":
        "byte0's HIGH nibble and byte+1 are HW-proven LIVE operand selectors (splicing them "
        "corrupts the tile dataflow) but neither is modelled as a field - db.json's match "
        "(0,8,0x1c) OVER-FITS the r1 form. An emitter must fill bytes this descriptor does not "
        "expose, and the value->register map is not a clean linear index (EXP-M4-14).",
}

# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------
def main():
    raw = open(DB, "rb").read()
    db = json.loads(raw.decode("utf-8"))
    sha = hashlib.sha256(raw).hexdigest()

    out_instr = {}
    counts = {}
    emittable = []
    total_fields = 0
    unknown_mnemonics = []

    EMIT_OK = (HR, IBD)

    for ins in db["instructions"]:
        m = ins["mnemonic"]
        spec = S.get(m)
        if spec is None:
            unknown_mnemonics.append(m)
            spec = {}
        default = spec.get("_default") or U()
        entry = {}
        ie = spec.get("_instruction")
        if ie is None:
            ie = F(TOK, "framing only (descriptor round-trips; no execution evidence located)",
                   CENSUS_T, CENSUS)
        entry["_instruction"] = json.loads(json.dumps(ie))

        fields = ins.get("fields", [])
        all_emit = True
        for f in fields:
            n = f["name"]
            fe = spec.get(n)
            if fe is None:
                fe = default
            fe = json.loads(json.dumps(fe))
            entry[n] = fe
            total_fields += 1
            counts[fe["label"]] = counts.get(fe["label"], 0) + 1
            if fe["label"] not in EMIT_OK:
                all_emit = False
        # Instructions with zero fields cannot be called emittable on field evidence:
        # they qualify only if the instruction itself is hardware-run / isolated-byte-diff.
        if not fields:
            all_emit = entry["_instruction"]["label"] in EMIT_OK
        if m in EMITTABLE_VETO:
            entry["_instruction"]["note"] = (
                (entry["_instruction"].get("note", "") + " ").strip() +
                " EMITTABLE VETO: " + EMITTABLE_VETO[m])
            all_emit = False
        if all_emit:
            emittable.append(m)
        out_instr[m] = entry

    if unknown_mnemonics:
        print("WARNING: no spec for %d mnemonics (defaulted to untested/tokenization-only): %s"
              % (len(unknown_mnemonics), ", ".join(sorted(unknown_mnemonics))), file=sys.stderr)

    doc = {
        "_license": "GPL-3.0-or-later",
        "spec": "docs/evidence-classification.md",
        "generated": "2026-08-28",
        "db_sha256": sha,
        "_conventions": {
            "default": "untested. A field with no committed experiment that exercised it is "
                       "untested with evidence []. Positional knowledge alone is not a label.",
            "evidence_ids": "directory-name prefixes under experiments/ - this includes the RT-* "
                            "red-team splice-and-observe experiments (A18 Pro), which are "
                            "committed experiments with retained raw evidence, alongside "
                            "EXP-NNNN and EXP-M4-NN / EXP-O2X.",
            "tokenization-only": "used where the field's only established role is consuming bytes "
                                 "so the instruction length/framing round-trips; its evidence is "
                                 "the census / round-trip experiments (EXP-0036 A18 consolidation "
                                 "census, EXP-M4-12 residue closure, EXP-M4-13 full-corpus "
                                 "convergence) plus tools/agx-isa/roundtrip_test.py.",
            "corpus-correlation": "used only where db.json or docs/ attributes the co-variation "
                                  "finding to a named experiment. EXP-M4-13 is COMPILE-ONLY "
                                  "(no dispatch), so nothing sourced from it can exceed this "
                                  "label.",
            "tested-but-unexplained": "a field that WAS exercised on hardware but whose semantics "
                                      "remain unexplained is untested (semantics not established) "
                                      "with the observation recorded in `note`.",
            "target": "per field, never assumed to transfer. EXP-0001..0046 and the RT-* passes "
                      "and EXP-M4-14 ran on A18 Pro/G17P; EXP-0047+ and EXP-M4-01..M4-13 ran on "
                      "M4/G16G. The EXP-0119 A18<->M4 contradiction is unresolved.",
            "emittable": "an instruction qualifies only if EVERY field in its db.json descriptor "
                         "is hardware-run or isolated-byte-diff (docs/evidence-classification.md "
                         "section 2, the emittable rule). Field-less descriptors qualify only if "
                         "the instruction itself is hardware-run / isolated-byte-diff.",
        },
        "coverage": {
            "total_instructions": len(db["instructions"]),
            "total_fields": total_fields,
            "by_label": {k: counts.get(k, 0) for k in
                         (HR, IBD, CC, TOK, STI, API, HP, UT)},
            "by_label_pct": {k: round(100.0 * counts.get(k, 0) / total_fields, 1) for k in
                             (HR, IBD, CC, TOK, STI, API, HP, UT)},
            "emittable_instructions": len(emittable),
            "emittable_mnemonics": sorted(emittable),
            "decodable_not_yet_emittable": len(db["instructions"]) - len(emittable),
        },
        "instructions": out_instr,
    }
    with open(OUT, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=False)
        fh.write("\n")
    print("wrote %s" % OUT)
    print("instructions=%d fields=%d" % (len(db["instructions"]), total_fields))
    for k in (HR, IBD, CC, TOK, STI, API, HP, UT):
        print("  %-26s %4d  (%.1f%%)" % (k, counts.get(k, 0),
                                         100.0 * counts.get(k, 0) / total_fields))
    print("emittable instructions: %d / %d" % (len(emittable), len(db["instructions"])))
    print("  " + ", ".join(sorted(emittable)))


if __name__ == "__main__":
    main()
