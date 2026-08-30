#!/usr/bin/env python3
"""EXP-0165: apply the EXP-0161 db_defects that survived independent re-derivation
to a tools/agx-isa/db.json.

  python3 analysis/apply_defects.py <path/to/db.json>

Idempotence is NOT assumed: run it against a pristine db.json.  Every edit is
guarded by an assertion on the value it expects to replace, so a second run or a
drifted input aborts instead of corrupting the descriptor.

Applied:  DEF-0161-1 (fspecial operand bytes), DEF-0161-2 (mov_zext16 register in
          byte0's high nibble) + its n3_mov corollary, DEF-0161-3 as CORRECTED by
          this experiment's re-derivation (fnclass bit3 don't-care, bit2 LIVE),
          DEF-0161-4 (roundmode bit0 -> NaN), DEF-0161-5 (scoreboard_model),
          DEF-0161-7 (carry_gen operand size bit).
Not applied: DEF-0161-6's DECODE relaxation (see RESULTS.md); the hardware fact
          is recorded in `carry_gen.semantics` instead.

FIELD NAMES ARE DELIBERATELY PRESERVED.  tools/agx-isa/validate_labels.py hard-
fails on any db.json field with no validation.json entry and on any validation.json
entry naming a field db.json no longer has, and this experiment may not edit
validation.json.  So the corrections are applied as POSITION changes over the
existing name set wherever a same-arity permutation exists; every name whose new
position makes the name itself historical says so in its own `note`.
"""
from __future__ import print_function
import json, sys

def ins(db, m):
    for i in db["instructions"]:
        if i["mnemonic"] == m:
            return i
    raise KeyError(m)

def fld(i, n):
    for f in i["fields"]:
        if f["name"] == n:
            return f
    raise KeyError("%s.%s" % (i["mnemonic"], n))

def expect(cond, msg):
    if not cond:
        raise AssertionError("apply_defects: precondition failed: " + msg)


# ---------------------------------------------------------------------------
FSPECIAL_SEM = (
 "d[dst] = SFU(src). Function = (byte0 bit7 `fn_hi`, byte+1-lo `fnclass`). "
 "OPERAND BYTES CORRECTED ON HARDWARE -- EXP-0161 (G17P), re-derived independently "
 "in EXP-0165 (db_defects :: DEF-0161-1). The pre-2026-08-30 descriptor had the "
 "DESTINATION and the SOURCE in the wrong bytes, which an emitter could not detect: "
 "the program runs, faults nothing, and writes the wrong register. The measured model is: "
 "**byte+3 is the DESTINATION register**, packed `reg = v >> 1` (bit 0 is HW-tested "
 "don't-care on the f32 datapath and is NOT the project-standard is32 bit -- the "
 "compiler's own f32 rsqrt encodes byte+3 = 0x00); "
 "**byte+5 is the SOURCE register**, packed `reg = v >> 2` (bits 0-1 HW-tested "
 "don't-care); and **byte+1's HIGH nibble is HW-TESTED INERT** -- all 16 values "
 "reproduce the unmutated result exactly, in two independent carriers and two gated "
 "runs, and the result always lands in the same register. It is retained under its "
 "historical name `src_ext` only so the per-field evidence chain in validation.json "
 "survives; it is NOT a source-register extension and NOT the destination. "
 "EVIDENCE: 16-register architectural dumps -- sweeping byte+5 moves which register is "
 "READ (it is released to zero) in blocks of 4 and the computed rsqrt matches that "
 "register's seed exactly (60/60 fit, 0 misfits, both runs); sweeping byte+3 moves "
 "which register RECEIVES the result in blocks of 2 (28/28 fit, 0 misfits, both runs); "
 "an exact-mask search over all 256 masks returns exactly `(v & 0xFE) == 0` for byte+3 "
 "and `(v & 0xFC) == 0` for byte+5, i.e. exactly the free bits the model predicts. "
 "GENERATED: 20/20 `r_i = rsqrt(r_j)` encodings for arbitrary i,j -- encodings the "
 "compiler never emitted -- predicted host-side and executed correctly (the old model "
 "scores 10 fail + 10 unpredictable on the same 20). "
 "This also EXPLAINS rather than contradicts EXP-0138's byte+3 report ('only 2 and 3 "
 "give the correct rsqrt; 188 values silently return 0.0; 6 and 7 leave the poison "
 "intact'): that is exactly what a DESTINATION selector does in a carrier whose store "
 "reads r1. "
 "REGISTER RANGE / DO-NOT-EMIT REGION: byte+3 = v gives destination r[v>>1], so "
 "v = 0..191 reaches r0..r95 -- the whole 96-GPR file -- and v = 192..255 would name "
 "r96..r127, which do not exist. Every one of those 64 values HANGS or FAULTS the "
 "command buffer (EXP-0161 danger arm: 45 of 64 gave a genuine "
 "kIOGPUCommandBufferCallbackErrorHang, 19 were only ever observed as innocent "
 "victims of their neighbours' resets, 0 ever worked; EXP-0138 independently recorded "
 "60 faults plus three watchdog hangs at 192/193/194 on M4). An emitter must never "
 "encode a destination register >= 96 here. The safe region 0..191 is dense and clean "
 "in three carriers. "
 "SOURCE RANGE: byte+5 = v gives source r[v>>2], so the field reaches r0..r63 only; "
 "r0..r14 are directly verified by the register dump, r15..r63 executed without fault "
 "but could not be verified in this carrier. "
 "FUNCTION SELECT (measured BY COMPUTED VALUE on G17P, EXP-0161 + EXP-0165 "
 "re-derivation, db_defects :: DEF-0161-3 as corrected): on the standard-SFU datapath "
 "(byte+6/+7 = 0xb0/0x40) `fnclass` bit 3 is a DON'T-CARE -- v and v+8 are identical "
 "in every one of the 8 pairs, in three carriers -- but bit 2 is NOT a blanket "
 "don't-care, which is where EXP-0161's own summary over-generalised. Measured map: "
 "with fn_hi=1 (byte0 0xaf): class&3 = 1 -> rsqrt, 2 -> exp2, 3 -> rsqrt (same as 1), "
 "0 -> returns +inf for every input; and bit 2 is inert for class&3 in {1,2,3} but "
 "live at class&3 = 0 (classes 4/12 store nothing at all). "
 "With fn_hi=0 (byte0 0x2f): class&3 = 0 -> rint, 1 -> rsqrt, 2 -> log2, 3 -> a "
 "primitive that returns NaN for 11 of 12 positive-finite inputs (consistent with the "
 "sincos/tan range-reduction primitive this enum has always named, not proof of it); "
 "and bit 2 is live at class&3 in {0,1} (class 4/12 store nothing; class 5/13 FAULT "
 "the command buffer) and inert at {2,3}. So the pre-existing `fn_hi` enum is now "
 "HW-CONFIRMED ON G17P BY COMPUTED VALUE at class 2 (0 -> log2, 1 -> exp2), and the "
 "`fnclass` enum's 0/1/2/3 rows are confirmed for the DIRECT (0x2f) family. "
 "Note that on this datapath class 0 does NOT compute rcp -- rcp needs fnsel 0x10. "
 "ROUND MODE / NaN BIT (db_defects :: DEF-0161-4, HW, G17P): on the rsqrt (0xaf) and "
 "log2 (0x2f) SFU datapaths byte+8 has exactly ONE live bit, bit 0, and setting it "
 "returns NaN in ALL 12 output lanes for EVERY input -- 128 of 256 values, in two "
 "carriers x two gated runs, 128/128 each time -- while all 128 even values reproduce "
 "the correct result bit-for-bit. **An emitter must never set byte+8 bit 0.** The "
 "round-mode enum below (0 nearest / 2 floor / 4 ceil / 6 trunc) is a claim about the "
 "DIRECT ROUND family only; it was NOT re-tested by computed value on a round carrier "
 "(EXP-0161's D4_FSPEC_FLOOR arm is committed but was never run), and on the two SFU "
 "datapaths that were tested, values 2/4/6 are indistinguishable from 0. "
 "OTHER FIELDS, accept-rules measured densely over all 256 values (G17P, "
 "the accepted set is the set that reproduces the unmutated result): "
 "`src_cache` byte+2 (v & 0x02) == 0x02 in the natural carriers and fully inert in the "
 "synthesized one -- carrier-dependent, do not assume inert; "
 "`src_class` byte+4 (v & 0x02) == 0x02, one live bit, clearing it silently zeroes; "
 "`fnsel` byte+6 (v & 0x99) == 0x90, 16 of 256, identical in all three carriers; "
 "`precsel` byte+7 (v & 0x64) == 0x40 (32 of 256) in the natural carriers, looser "
 "((v & 0x60) == 0x40) in the synthesized one; "
 "`sched_flag` byte+9 HW-TESTED INERT over all 256 values in both carriers. "
 "The op itself: one hardware special-function op; fast-math emits it directly "
 "(~1 ULP). exp/exp10 = exp2(x*k); log/log10 = log2(x)*k; pow = exp2(b*log2(a)); "
 "a/b = a*rcp(b). "
 "`emit_unsafe` is RETAINED, but its meaning has changed: the descriptor geometry is "
 "no longer wrong (EXP-0165 fixed it) -- the flag now marks the two documented "
 "do-not-emit regions, byte+3 >= 192 and byte+8 bit 0."
)

FSPECIAL_PROV = (
 "HW-VALIDATED (EXP-0013 exp2/log2/round; EXP-0026 rcp/rsqrt/sqrt): exp2/log2 exact on "
 "powers of two, 1 ULP elsewhere; floor/ceil/trunc/rint via byte+8 round-mode; under "
 "fast-math 1/x, rsqrt, sqrt each compile to a single op of this group at ~0-1 ULP, and "
 "a/b = a*rcp(b), pow = exp2(b*log2(a)). "
 "OPERAND MODEL SUPERSEDED AND CORRECTED -- HW-VALIDATED (EXP-0161, G17P; independently "
 "re-derived from EXP-0161's immutable raw register dumps in EXP-0165): the byte-diff "
 "operand assignment from EXP-M4-13 R7 (compile-only, `dst` = byte+1 high nibble, `src` "
 "= byte+3, `src_ext` = byte+5) is REFUTED by the 16-register architectural dump and by "
 "20/20 generated encodings. byte+1's high nibble is inert; byte+3 is the destination; "
 "byte+5 is the source. EXP-M4-13's 5-way `byte+1 -> 0x01/0x11/0x21/0x41/0x81` sweep "
 "was a COMPILE-ONLY correlation and never executed. "
 "Function map, NaN bit, and all per-byte accept rules: HW-VALIDATED (EXP-0161, G17P, "
 "dense 256-value sweeps in three carriers over two gated runs); the fnclass bit-2/bit-3 "
 "refinement is EXP-0165's re-derivation of the same raw data."
)

MOV_ZEXT16_SEM = (
 "r[n] = r[n] & 0xFFFF -- 16-bit ZERO-extend / narrow, IN PLACE on ONE register used as "
 "BOTH source and destination. n = byte0's HIGH nibble. "
 "REGISTER FIELD RECOVERED -- HW (EXP-0161, G17P; re-derived independently in EXP-0165, "
 "db_defects :: DEF-0161-2). The pre-2026-08-30 descriptor pinned byte0 to the full "
 "fixed byte 0x13 and modelled byte+1 as the source register, so the real register "
 "selector was invisible to an emitter and the modelled one did nothing. Measured: a "
 "dense byte0 sweep in a synthesized carrier (the instruction alone, r0..r14 seeded by "
 "device_load from an authored buffer, judged by the 16-register dump) shows "
 "byte0 = 0xN3 narrows r[N] AND NOTHING ELSE, for N = 0..10, 11 of 11 fits with 0 "
 "misfits in both gated runs; nibbles 0xB..0xF execute as a NO-OP (no register changes "
 "at all) -- 4 independent observations each. No byte0 value whose LOW nibble is not 3 "
 "ever performs the narrow (all 16 low-nibble buckets checked). "
 "GENERATED: 11 of 16 `r[n] = r[n] & 0xFFFF` encodings pass a host-computed 16-register "
 "prediction; the 5 failures are exactly the 0xB..0xF no-op nibbles. One anomaly is "
 "recorded rather than smoothed: nibble 0x8 (r8) narrowed correctly in 4 of 5 "
 "observations (both gated sweeps, gen01, gen02) and was a no-op once (gen03). "
 "byte+1 IS NOT A SOURCE REGISTER -- HW-TESTED INERT over all 256 values (128 values of "
 "bits 0-6 x both values of bit 7), in a carrier where the instruction is demonstrably "
 "live (its byte0 := 0x00 falsifier fires) and where fifteen device_loads and a "
 "sentinel store separate the source from the instruction, so ALU forwarding cannot "
 "explain it; reproduced in a SECOND register form (byte0 = 0x53, i.e. r5) as its own "
 "gated pair. This CLOSES EXP-0146's open question -- which left (a) 'byte+1 is not a "
 "source selector' and (b) 'the operand was ALU-forwarded from the preceding "
 "device_load' undecided -- as (a). EXP-0146's own carrier is also shown to be dead: "
 "the falsifier byte0 := 0x00 scores `ok` there (the correct a & 0xFFFF still comes "
 "out), so that arm proves nothing either way. byte+1 keeps its historical name "
 "`src_flag` (now the whole byte, not a 1-bit flag) ONLY so the per-field evidence "
 "chain in validation.json survives a db.json field cannot be renamed without editing "
 "that file; it is an inert byte, not a flag and not a source selector. "
 "MATCH: byte0's low nibble (3) is the group discriminator -- this is the same compact "
 "4-byte n3 group as `n3_mov`, of which this descriptor is the ZERO-EXTEND member -- and "
 "byte+3's low 3 bits (0b001) are the zero-extend companion discriminator: all 32 of "
 "256 byte+3 values with (v & 0x07) == 0x01 reproduce the narrow exactly and no other "
 "value does, so bits 3-7 of byte+3 (`extend`) are free. `subform` (byte+2) accepts "
 "(v & 0xC7) == 0x00, 8 of 256, identically in both register forms. "
 "NEGATIVE controls (EXP-M4-13, own-MSL) still stand: SIGN-extend short->int does NOT "
 "use this op (it lowers to an iadd/bfe sign path) and 8-bit narrow uchar does NOT "
 "either (ilogic AND 0xff), so this really is the 16-bit ZERO-extend."
)

MOV_ZEXT16_PROV = (
 "HW-VALIDATED (EXP-0013): u2us zero-extends the low 16 bits (0xFFFFFFFF -> 0xFFFF, "
 "0x18000 -> 0x8000). "
 "OPERAND MODEL SUPERSEDED AND CORRECTED -- HW-VALIDATED (EXP-0161, G17P; independently "
 "re-derived in EXP-0165): the register lives in byte0's high nibble, not byte+1. "
 "EXP-M4-13 R8's byte+1 = source-register reading was a COMPILE-ONLY corpus correlation "
 "carried over from the reg_move_cb sibling and is refuted for this op by a 256-value "
 "hardware sweep in two independent register forms. EXP-0146 (HW, M4) observed the same "
 "inertness and correctly left the cause OPEN; EXP-0161 settles it. "
 "The 16-bit narrow itself, the 0xN3 register map, the no-op nibbles and the byte+2 / "
 "byte+3 accept rules are HW-VALIDATED on G17P."
)

N3_MOV_APPEND = (
 " OPEN QUESTION CLOSED -- HW (EXP-0161, G17P; re-derived in EXP-0165). For the "
 "ZERO-EXTEND companion member of this family (byte+2 (v & 0xC7) == 0x00 and byte+3 "
 "(v & 0x07) == 0x01, split out as the `mov_zext16` descriptor), the instruction is an "
 "IN-PLACE narrow of the ONE register named by `dst`: `r[dst] = r[dst] & 0xFFFF`. "
 "`srcA_reg` and `srcA_uni` are HW-TESTED INERT over all 256 combinations there, in two "
 "independent register forms and in a carrier where forwarding is excluded -- so for "
 "that member they are not a source selector at all. `dst` reaches r0..r10 on G17P; "
 "nibbles 0xB..0xF execute as a no-op. Whether `srcA_reg` is a real source selector for "
 "the OTHER companion values is UNTESTED -- do not generalise the inertness beyond the "
 "zero-extend member."
)

CARRY_GEN_APPEND = (
 " OPERAND PACKING AND SIZE BIT -- HW-VALIDATED (EXP-0161, G17P; independently "
 "re-derived in EXP-0165, db_defects :: DEF-0161-7). `srcA` (byte+1) and `srcB` "
 "(byte+3) are the project-standard packed operand selector `(reg << 1) | is32` with an "
 "INERT bit 7: reg = (v >> 1) & 0x3F -- the released-register map in the synthesized "
 "carrier fits 22/22 for srcB -- and **bit 0 is a REAL SIZE BIT**. With it SET the "
 "compare is 32-bit; with it CLEAR the hardware compares only the LOW 16 BITS of both "
 "operands. Established the hard way: 16 generated encodings built with is32 = 0 while "
 "predicting a 32-bit compare failed 9 of 16, and all 16 outcomes are explained exactly "
 "by the 16-bit rule; the corrected model then passed 48/48 generated encodings across "
 "both widths and both settings of the inert bit 7 (re-scored in EXP-0165 directly from "
 "the committed register dumps, 16/16 and 48/48, against 7/16 and 39/48 for an "
 "always-32-bit model). An emitter that leaves bit 0 clear gets a silent 16-bit "
 "compare. `dst` (byte0 high nibble) selects the predicate register the following psel "
 "reads. `cmpmode` (byte+4) accepts (v & 0xA7) == 0x22, 8 of 256; db.json enumerates "
 "only 0x22. "
 "byte+2 MATCH OVER-CONSTRAINT REPRODUCED ON G17P (EXP-0161; verified in EXP-0165 "
 "against every one of the 256 swept values in BOTH carriers and BOTH gated runs): the "
 "accepted set is exactly {0x05,0x07,0x15,0x17,0x25,0x27,0x35,0x37} and "
 "`(v & 0xCD) == 0x05` is the UNIQUE mask rule that separates it from the 248 rejected "
 "values -- an exhaustive search over all 256 candidate masks returns that one and no "
 "other. This is a value-for-value G16G -> G17P reproduction of EXP-0146. Relaxing the "
 "match is still a DECODE change and is still DEFERRED: expressing (v & 0xCD) == 0x05 "
 "in this schema needs three match entries plus two new fields for the freed bits 1 and "
 "4-5, and a new field name cannot be added without editing validation.json in the same "
 "commit (tools/agx-isa/validate_labels.py hard-fails on an unlabelled field)."
 " EMITTER CAVEAT (EXP-0165, see `length_rule_gaps :: carry_gen_r9_shadow_20260830`): "
 "OUR OWN TOKENIZER currently mis-lengths 16 legal `srcA` values here -- byte+1 in "
 "{0x00,0x10,0x14,0x19,0x1e,0x20,0x22,0x25,0x28,0x2a,0x51,0x87,0x9d,0xa3,0xa5,0xcb} is "
 "claimed by isadb.py's R9 trailing-word closure as a 2-byte pad before the low-nibble-2 "
 "length rule is reached. The HARDWARE runs those encodings correctly (6 of EXP-0161's "
 "48 passing generated cases are in that set); it is a defect in our decoder, not in the "
 "encoding, and it does not restrict what an emitter may produce."
)
# ---------------------------------------------------------------------------


def apply_all(path):
    db = json.load(open(path))

    # ---------------- DEF-0161-1 : fspecial operand bytes -----------------
    f = ins(db, "fspecial")
    d, s, e = fld(f, "dst"), fld(f, "src"), fld(f, "src_ext")
    expect((d["start"], d["width"]) == (12, 4), "fspecial.dst was byte+1 hi nibble")
    expect((s["start"], s["width"]) == (24, 8), "fspecial.src was byte+3")
    expect((e["start"], e["width"]) == (40, 8), "fspecial.src_ext was byte+5")
    # byte+1 high nibble: HW-TESTED INERT. Keeps the historical name `src_ext`.
    e["start"], e["width"], e["type"] = 12, 4, "mod"
    e["note"] = ("byte+1 HIGH nibble. HW-TESTED INERT on G17P: all 16 values reproduce "
                 "the unmutated result exactly, in two carriers x two gated runs, and "
                 "the result always lands in the same register (EXP-0161/EXP-0165, "
                 "DEF-0161-1). HISTORICAL NAME: this is NOT a source-register extension "
                 "and NOT the destination -- db.json modelled it as `dst` until "
                 "2026-08-30. The name is retained only because renaming a db.json "
                 "field orphans its validation.json evidence row. Emit 0.")
    # byte+3: the DESTINATION register.
    d["start"], d["width"], d["type"] = 24, 8, "reg"
    d["note"] = ("byte+3 = the DESTINATION register, packed reg = v >> 1 (bit 0 is "
                 "HW-tested don't-care and is NOT the is32 bit). v = 0..191 -> r0..r95; "
                 "v >= 192 names a register outside the 96-GPR file and HANGS/FAULTS the "
                 "command buffer -- never emit it. HW, G17P (EXP-0161/EXP-0165, "
                 "DEF-0161-1): destination map 28/28 fit, 0 misfits, both gated runs; "
                 "20/20 generated encodings.")
    # byte+5: the SOURCE register.
    s["start"], s["width"], s["type"] = 40, 8, "reg"
    s["note"] = ("byte+5 = the SOURCE register, packed reg = v >> 2 (bits 0-1 HW-tested "
                 "don't-care). Reaches r0..r63. HW, G17P (EXP-0161/EXP-0165, "
                 "DEF-0161-1): released-register map 60/60 fit, 0 misfits, both gated "
                 "runs, each source identified twice over (the computed rsqrt matches "
                 "that register's seed AND that register is released to zero).")
    # ---------------- DEF-0161-3 (as corrected) ---------------------------
    fc = fld(f, "fnclass")
    fc["enum"] = {
        "0": "rcp|round -- on the std-SFU datapath (fnsel 0xb0): 0x2f -> rint, "
             "0xaf -> +inf (rcp needs fnsel 0x10)",
        "1": "rsqrt|sqrt",
        "2": "exp2|log2 (fn_hi selects: 0 -> log2, 1 -> exp2; HW-confirmed by computed "
             "value on G17P)",
        "3": "sincos/tan primitive -- on 0x2f returns NaN for 11 of 12 positive finite "
             "inputs; on 0xaf indistinguishable from class 1 (rsqrt)",
        "4": "NOT a separate class: 4 = class 0 with bit 2 set, which stores nothing at "
             "all on both datapaths (HW, G17P)",
    }
    fc["note"] = ("HW, G17P (EXP-0161, re-derived and CORRECTED in EXP-0165, "
                  "DEF-0161-3). On the std-SFU datapath (byte+6/+7 = 0xb0/0x40) bit 3 is "
                  "a DON'T-CARE -- v and v+8 are identical in all 8 pairs, in three "
                  "carriers -- but bit 2 is NOT: at class&3 = 0 it is live on BOTH "
                  "datapaths (4/12 store nothing) and at class&3 = 1 it is live on 0x2f "
                  "(5/13 FAULT) while inert on 0xaf. EXP-0161's summary line 'only the "
                  "low two bits are live' and 'values 1,3,5,...,15 all compute the same "
                  "function' hold on the 0xaf carrier only and are NOT general.")
    fh = fld(f, "fn_hi")
    fh["note"] = ("HW-CONFIRMED BY COMPUTED VALUE on G17P (EXP-0161/EXP-0165): with the "
                  "same bytes otherwise, fn_hi = 0 computes log2 and fn_hi = 1 computes "
                  "exp2 at fnclass 2.")
    # ---------------- DEF-0161-4 : roundmode bit 0 ------------------------
    rm = fld(f, "roundmode")
    expect(rm["start"] == 64 and rm["width"] == 8, "fspecial.roundmode is byte+8")
    rm["enum"] = dict(rm["enum"])
    rm["enum"]["1"] = ("DO NOT EMIT -- bit 0 set returns NaN in every lane for every "
                       "input on the rsqrt and log2 SFU datapaths (HW, G17P)")
    rm["note"] = ("HW, G17P (EXP-0161/EXP-0165, DEF-0161-4): on the rsqrt (0xaf) and "
                  "log2 (0x2f) datapaths byte+8 has exactly ONE live bit -- bit 0 -- and "
                  "setting it returns NaN in ALL 12 output lanes for EVERY input: "
                  "128/128 odd values, in two carriers x two gated runs. All 128 even "
                  "values reproduce the correct result bit-for-bit, so 2/4/6 are "
                  "indistinguishable from 0 there. The round-mode enum is a claim about "
                  "the DIRECT ROUND family only and was NOT re-tested by computed value "
                  "on a round carrier.")
    sf = fld(f, "sched_flag")
    sf["note"] = ("HW-TESTED INERT on G17P: all 256 values reproduce the unmutated "
                  "result in both carriers (EXP-0161).")
    f["fields"].sort(key=lambda x: x["start"])
    f["semantics"] = FSPECIAL_SEM
    f["provenance"] = FSPECIAL_PROV

    # ---------------- DEF-0161-2 : mov_zext16 -----------------------------
    z = ins(db, "mov_zext16")
    expect(z["match"] == [[0, 8, 19]], "mov_zext16 match was byte0 == 0x13")
    expect(z["length"] == 4, "mov_zext16 is 4 bytes")
    sr, sfl, sub, ext = (fld(z, "src_reg"), fld(z, "src_flag"),
                         fld(z, "subform"), fld(z, "extend"))
    expect((sr["start"], sr["width"]) == (8, 7), "mov_zext16.src_reg was byte+1 bits0-6")
    expect((sfl["start"], sfl["width"]) == (15, 1), "mov_zext16.src_flag was byte+1 bit7")
    expect((ext["start"], ext["width"]) == (24, 8), "mov_zext16.extend was byte+3")
    z["match"] = [[0, 4, 3], [24, 3, 1]]
    sr["start"], sr["width"], sr["type"] = 4, 4, "reg"
    sr["note"] = ("byte0 HIGH nibble = the ONE register, used as BOTH source and "
                  "destination (r[n] = r[n] & 0xFFFF). HW, G17P: 0xN3 narrows r[N] and "
                  "nothing else for N = 0..10 (11/11 fit, 0 misfits, both gated runs); "
                  "N = 0xB..0xF execute as a NO-OP. db.json modelled this nibble as part "
                  "of a fixed match until 2026-08-30 (EXP-0161/EXP-0165, DEF-0161-2).")
    sfl["start"], sfl["width"], sfl["type"] = 8, 8, "mod"
    sfl.pop("enum", None)
    sfl["note"] = ("byte+1, WHOLE BYTE. HW-TESTED INERT on G17P: all 256 values reproduce "
                   "the narrow exactly, in two independent register forms, in a carrier "
                   "where the instruction is live and forwarding is excluded. It is NOT "
                   "a source-register selector and NOT a flag; the name is historical and "
                   "retained only so its validation.json evidence row survives. Emit 0.")
    sub["note"] = ("byte+2. HW, G17P: accepts (v & 0xC7) == 0x00, 8 of 256, identically "
                   "in both register forms (EXP-0161).")
    ext["start"], ext["width"] = 27, 5
    ext["note"] = ("byte+3 bits 3-7. The zero-extend companion discriminator is byte+3's "
                   "LOW 3 bits (0b001), now part of `match`; the remaining 5 bits are "
                   "HW-tested free -- all 32 of 256 byte+3 values with (v & 0x07) == 0x01 "
                   "reproduce the narrow and no other value does (EXP-0161, G17P).")
    z["fields"].sort(key=lambda x: x["start"])
    z["semantics"] = MOV_ZEXT16_SEM
    z["provenance"] = MOV_ZEXT16_PROV

    # ---------------- DEF-0161-2 corollary : n3_mov -----------------------
    n = ins(db, "n3_mov")
    expect("SOURCE REGISTER INERT IN THE ONLY CARRIER -- UNRESOLVED" in n["semantics"],
           "n3_mov still carries the unresolved-source note")
    n["semantics"] = n["semantics"] + N3_MOV_APPEND
    n["provenance"] = n["provenance"] + (" Zero-extend member resolved on hardware: "
                                         "EXP-0161 (G17P), re-derived in EXP-0165.")

    # ---------------- DEF-0161-7 (+ DEF-0161-6 as a note) : carry_gen -----
    c = ins(db, "carry_gen")
    a_, b_ = fld(c, "srcA"), fld(c, "srcB")
    expect((a_["start"], a_["width"]) == (8, 8), "carry_gen.srcA is byte+1")
    expect((b_["start"], b_["width"]) == (24, 8), "carry_gen.srcB is byte+3")
    packed = ("packed operand selector (reg << 1) | is32, bit 7 INERT. **bit 0 is a real "
              "SIZE bit**: set = 32-bit compare, clear = the hardware compares only the "
              "LOW 16 BITS (HW, G17P, EXP-0161/EXP-0165, DEF-0161-7). reg = (v >> 1) & "
              "0x3F.")
    a_["note"] = "byte+1: " + packed
    b_["note"] = ("byte+3: " + packed + " Released-register map fits 22/22 in the "
                  "synthesized carrier.")
    c["semantics"] = c["semantics"] + CARRY_GEN_APPEND
    c["provenance"] = c["provenance"] + (" Operand packing, the 16/32-bit size bit and "
                                         "the byte+2 accept set: HW-VALIDATED "
                                         "(EXP-0161, G17P), re-derived in EXP-0165.")

    # ---- EXP-0165 NEW FINDING: legal carry_gen encodings are MIS-LENGTHED ----
    g = db["length_rule_gaps"]
    expect("carry_gen_r9_shadow_20260830" not in g, "length gap not already recorded")
    g["carry_gen_r9_shadow_20260830"] = {
        "found_by": "EXP-0165 analysis/functional_check.py, re-emitting the encodings "
                    "EXP-0161 executed successfully on G17P",
        "instructions": ["carry_gen"],
        "symptom": "isadb.py's EXP-M4-13 R9 trailing-word closure fires BEFORE the "
                   "low-nibble-2 length rule and maps 16 (byte0=0x32, byte+1) pairs to "
                   "a 2-byte pad word: byte+1 in {0x00,0x10,0x14,0x19,0x1e,0x20,0x22,"
                   "0x25,0x28,0x2a,0x51,0x87,0x9d,0xa3,0xa5,0xcb}. Those are legal "
                   "`carry_gen` srcA selectors -- (reg<<1)|is32 for r0(16b), r8, r10, "
                   "r12, r15, r16, r17, r18, r20, r21, r40 and four bit-7 forms -- so a "
                   "6-byte `32 <b1> 35 .. 22 ..` that the HARDWARE EXECUTES CORRECTLY "
                   "tokenizes as a 2-byte `operand_word`/`b_alu14_prep2` and the "
                   "remaining 4 bytes desync. HW proof: 6 of EXP-0161's 48 passing "
                   "generated carry_gen encodings are in this set.",
        "reproduce": "python3 experiments/EXP-0165-db-defect-repair/analysis/"
                     "functional_check.py tools/agx-isa  -> 6 re-emit failures",
        "required_fix": "isadb.py, NOT db.json: the R9 closure must not fire on a "
                        "low-nibble-2 leader whose byte+2 is a real op-select (<= 0x3f).",
        "status": "OPEN. EXP-0165 built and MEASURED that guard "
                  "(work/probe_r9): it fixes all 6 (functional re-emit 73/79 -> 79/79) "
                  "but REGRESSES the frozen corpus metric -- clean files 833 -> 832 and "
                  "strict leftover bytes 388604 -> 389002 -- so it was NOT applied. A "
                  "successor needs a narrower guard, and it is a decode change that "
                  "belongs in its own experiment.",
    }

    # ---------------- DEF-0161-5 : scoreboard_model -----------------------
    sm = db["scoreboard_model"]
    expect("device_store_hazard" not in sm, "scoreboard_model not already amended")
    sm["max_in_flight"] = (sm["max_in_flight"] +
        " NOTE: that '>= 20 outstanding, all consumed correctly' claim holds for ALU "
        "consumers ONLY -- see `device_store_hazard`.")
    sm["device_store_hazard"] = (
        "HW, G17P (EXP-0161 harness/pilot_seed.py, 8 controlled variants; re-derived in "
        "EXP-0165 -- db_defects :: DEF-0161-5). A `device_store`'s DATA-REGISTER read is "
        "NOT interlocked against a pending `device_load` into that register. With a "
        "single wave of 15 loads, the registers read by the FIRST ~5 stores issued "
        "afterwards come back with their PRE-LOAD value, silently and with STATUS OK. "
        "The effect follows the STORE order, not the load order: dumping r15..r0 instead "
        "of r0..r15 moved the stale set from r0..r4 to r11..r14. It reproduces with only "
        "5 loads outstanding. It is a latency, not a capacity limit: inserting 4 filler "
        "ops leaves 5 registers stale, 16 filler ops leaves 3, and 64 filler ops leaves "
        "0; issuing the whole load wave a second time also clears it completely (15/15 "
        "correct, stable over 8 consecutive dispatches). An emitter that stores a "
        "just-loaded register must separate the two, or re-load. This is the one known "
        "silent-corruption surface for device RAW on G17P and it contradicts the blanket "
        "reading of `mechanism` above.")

    json.dump(db, open(path, "w"), indent=2)
    print("patched", path)


if __name__ == "__main__":
    apply_all(sys.argv[1])
