#!/usr/bin/env python3
"""EXP-0212 -- apply the hardware-confirmed descriptor defects queued in
tools/agx-isa/PENDING_DB_DEFECTS.md to a db.json.

  python3 analysis/apply_db_edits.py <in_db.json> <out_db.json> [--only GROUP,...]

Every edit is keyed to a defect id in PENDING_DB_DEFECTS.md and to the committed
experiment artifact that carries the observation.  Nothing here is applied on the
PENDING file's authority alone: each edit names the experiment, the raw/derived
artifact, and the exact numerator/denominator behind it.

GROUPS
  a_notes     non-span corrections: prose, enums, field notes.  Cannot invalidate
              an existing verdict -- no field's start/width changes.
  b_spans     span-moving corrections: a field narrows, splits, or a new field
              appears.  These are the DEF-0166-2 hazard class; every affected
              validation.json row is handled by apply_validation_notes.py.
  d_match     match-bit corrections.  These CAN change tokenization and are
              measured A/B against the own-MSL corpus before being kept.

CLEAN ROOM: reads only this repository's own committed artifacts.  No Apple binary
is introspected; every cited observation comes from our own MSL compiled at runtime
and dispatched on our own G17P target.
"""
import json, sys

GROUPS = ["a_notes", "b_spans", "d_match"]

E01, E02, E03, E04, E05, E06, E07 = ("EXP-0199", "EXP-0200", "EXP-0201", "EXP-0202",
                                     "EXP-0203", "EXP-0204", "EXP-0205")
E06b, E07b = "EXP-0206", "EXP-0207"
TAG = "[EXP-0212, applied 2026-08-30]"


def by_m(db):
    return {i["mnemonic"]: i for i in db["instructions"]}


def fld(ins, name):
    for f in ins.get("fields", []):
        if f["name"] == name:
            return f
    raise KeyError("%s has no field %s" % (ins["mnemonic"], name))


def addnote(ins, name, text):
    f = fld(ins, name)
    f["note"] = ((f.get("note", "") + " ") if f.get("note") else "") + text


def addsem(ins, text):
    ins["semantics"] = ins["semantics"].rstrip() + " " + text


# ===========================================================================
# GROUP A -- non-span corrections
# ===========================================================================
def group_a_notes(db):
    M = by_m(db)
    n = 0

    # ---- DEF-0201-1 -------------------------------------------------------
    addnote(M["falu3_srcmod12"], "opsel",
            "%s DEF-0201-1 (%s, G17P): this span OVERLAPS the descriptor's own match "
            "constraint [17,1,1]. Bit 17 is PINNED, so only bits 16 and 18 are free within "
            "this mnemonic and the ENCODABLE RANGE IS 4 VALUES {2,3,6,7}, not 8. Values with "
            "bit 17 clear are a DIFFERENT instruction (falu_srcmod12b), which the pinned "
            "tokenizer confirms per case. Evidence: raw/g17p_20260830_a_run01+a_run02 "
            "sweep.jsonl, analysis/maps.json. The span is NOT narrowed here: the two free bits "
            "are non-contiguous, so no single (start,width) expresses them."
            % (TAG, E03)); n += 1

    # ---- DEF-0201-2 -------------------------------------------------------
    addnote(M["falu3"], "op",
            "%s DEF-0201-2 (%s, G17P, compiled three-source fma carrier). CORRECTION to the "
            "low-3 class map: class 5 is NOT a constant zero -- it is a MULTIPLY BY ZERO. The "
            "result's sign follows srcB (-0.0 for negative srcB) and an INFINITE srcB yields "
            "NaN (0x7fc00000). REFUTED on this carrier: low-3 classes 0 (`a+b`), 1 (`a*b`) and "
            "2 (`a*b+a`) -- 0 and 2 return a lane-uniform constant drawn from an unrelated live "
            "register and 1 returns +0.0. Classes 4, 6 and 7 are confirmed bit-exactly. The "
            "published map came from a synthesized-and-lifted carrier with seeded registers; "
            "NEITHER record is retracted, and the reconciling hypothesis (classes 0/2/3 "
            "re-decoding the operand descriptors to a source class a 3-source carrier does not "
            "name) is NOT established. Evidence: analysis/op_semantics.json."
            % (TAG, E03)); n += 1

    # ---- OBS-0201-1 -------------------------------------------------------
    addsem(M["falu3"],
           "%s DENORMAL BEHAVIOUR, OBS-0201-1 (%s, G17P): a denormal operand and/or a denormal "
           "RESULT does not survive this fused multiply-add. 1.4e-45 * 2.0 + 0.0, whose IEEE "
           "result is 0x00000002, returned 0x00000000. The two flush points (input flush vs "
           "output flush) are NOT separated by this arm. Found by the bit-exact offline "
           "classifier; the sweep's own tolerance-based comparison accepted it as correct. "
           "Evidence: analysis/op_semantics.json." % (TAG, E03))
    n += 1

    # ---- DEF-0201-3 -------------------------------------------------------
    addnote(M["copysign"], "operands",
            "%s DEF-0201-3 (%s, G17P): byte+3 is a LIVE operand descriptor with accept rule "
            "(v & 0x7E) == 0x00, but it does NOT encode the operand ROLE. Two carriers "
            "differing only in which argument is the magnitude source compile to BYTE-IDENTICAL "
            "instructions (`07 c2 88 00` at the same offset) and compute copysign(a,b) and "
            "copysign(b,a) respectively. The role is established by the surrounding register "
            "allocation, behind bytes this descriptor models as match constants. CONSEQUENCE "
            "for an emitter: the 4-byte word can be generated from the descriptor and executes "
            "(generated-point), but a canonical recipe must additionally state how the roles are "
            "established, which %s could not. Evidence: analysis/maps.json."
            % (TAG, E03, E03)); n += 1

    # ---- OBS-0201-2 -------------------------------------------------------
    addnote(M["fspecial_est"], "subop",
            "%s OBS-0201-2 (%s): ENUM PROVENANCE FLAG, not a hardware claim. On G17P our own "
            "`precise::rsqrt` AND `precise::sqrt` both lower to subop 0x0f, and "
            "`precise::divide(1,x)` to subop 0x0d, where this enum reads 9=rcp, 11=rsqrt, "
            "13=sqrt, 15=rsqrt. That is a COMPILER OBSERVATION ABOUT OUR OWN SOURCE; nothing is "
            "concluded here about what the hardware computes for each subop, and the enum is "
            "left as it stands. Evidence: work/census.json." % (TAG, E03)); n += 1

    # ---- DEF-0202-3 -------------------------------------------------------
    for m in ("shift_amt_move", "b_alu10_lo7"):
        addnote(M[m], "src_flag",
                "%s DEF-0202-3 (%s, G17P): the enum {0: gpr, 1: uniform/class} is INHERITED, "
                "not observed, and is UNSUPPORTED by any observation this target allows. Across "
                "56 authored carriers the compiler emits src_flag = 0 in all 11 "
                "`shift_amt_move` occurrences; on `b_alu10_lo7`, where it emits BOTH values, "
                "splicing either leaves the output BYTE-IDENTICAL (768/768 comparisons, both "
                "runs). Nine carriers spanning SEVEN operand-producer classes gave 0 movement, "
                "and the same-dimension positive control (`b_alu10_lo7.src_flag` itself) did "
                "not move either -- so this is `carrier-undecidable`, NOT inertness. The enum "
                "is deliberately NOT removed: this records that it is unobserved, not that it "
                "is wrong." % (TAG, E04))
        n += 1

    # ---- DEF-0202-4 -------------------------------------------------------
    f = fld(M["ibitcount"], "form")
    f["enum"]["21"] = "observed on our own k_pc_two (occurrence 1); role UNNAMED -- DEF-0202-4"
    addnote(M["ibitcount"], "form",
            "%s DEF-0202-4 (%s): the enum {4: reverse, 5: count/scan} is INCOMPLETE. Our own "
            "`k_pc_two` compiles to form = 21 (0x15) at its second occurrence, a value the enum "
            "did not name; it is added above with its role explicitly unnamed. Evidence: "
            "raw/prefreeze/census_b.json, pc_two occ1 `2715540003005c04`." % (TAG, E04)); n += 1

    # ---- DEF-0202-2 -------------------------------------------------------
    addnote(M["ibitcount"], "dst",
            "%s DEF-0202-2 (%s, G17P, 2560 ledger-verified cases over five occurrences and two "
            "gated runs): `dst = reg << 1` is INCOMPLETE in two ways. (1) BIT 0 IS NOT PART OF "
            "THE REGISTER INDEX -- the program reproduces at EXACTLY {compiled, compiled+1} on "
            "all five occurrences. (2) dst[7:6] == 0b11 IS ILLEGAL -- values 192..255 fault "
            "CONTIGUOUSLY, all 64 of them, on all five occurrences, in both runs. The span is "
            "deliberately NOT narrowed to (25,7): a narrower span could not express the [7:6] "
            "illegality, and bit 0 is a don't-care for the index rather than a proven globally "
            "inert bit. Evidence: PC/{pc_store,pc_alu,pc_two,iu_ctz,pc_dump}#0/dst."
            % (TAG, E04)); n += 1

    # ---- half_pack semantics (write_target / source_release / length_gate) --
    addsem(M["half_pack"],
           "%s CORRECTED AND EXTENDED BY %s (G17P, host-oracle match on full post-state). "
           "(1) WRITE TARGET: this member writes the destination's HIGH 16 bits and PRESERVES "
           "its LOW 16 bits; its byte0-low-nibble-0 sibling writes the LOW half. The name "
           "`pack` is a misnomer for what was measured -- a per-lane fp16 ALU op on the HIGH "
           "lane, which is exactly why a `half2` operation takes ONE INSTRUCTION PER LANE "
           "(4 arms x 512 field cases, full-post-state oracle match 100%%). "
           "(2) SOURCE RELEASE: at byte+2 = 0x18 the instruction ZEROES both named source "
           "half-lanes (opflags 3 source release), and WHICH lane is zeroed follows the "
           "descriptor's value -- so the release is part of the field's semantics, not a "
           "constant side effect. Every release-free candidate model scored 2/80; with the "
           "release the arithmetic member scores 80/80, confirmed on 2048 gated field cases. "
           "(3) LENGTH GATE, INDEPENDENT HARDWARE CONFIRMATION of DEF-0154-1: the HARDWARE "
           "consumed exactly FOUR bytes for ALL 256 byte+1 values (all four 2-byte length "
           "markers survived in every case, every arm, every run), while `isadb.instr_length` "
           "accepts byte0 == 0x18 as a 4-byte half_pack only when byte+1 == 0x05 -- so our own "
           "tokenizer returned `<unknown>` for the anchor `18 0d 18 11` and disagreed with "
           "itself on 11 of the 256 byte+1 values. THE BYTE+1 GATE IS NOT A LENGTH CONDITION. "
           "The length rule is NOT changed here (it is the length-rule owner's file); this is "
           "the second independent measurement asking for it. Evidence: raw/g17p_run31..32."
           % (TAG, E05))
    n += 1

    # ---- simd_reduce.dtype (NOT narrowed) ---------------------------------
    addnote(M["simd_reduce"], "dtype",
            "%s %s (G17P, four carriers, dense 256-value sweep, two gated runs): the DECODED "
            "width is context-dependent and at most 6 bits. Live bits measured by per-bit "
            "differential: [0,3] on sr_sum and sr_max, [0,1,3] on sr_scan, [0,1,2,3,5] on the "
            "f32 carrier; bits 4, 6 and 7 are INERT-WITHIN-FIELD on all four carriers and the "
            "integer carriers repeat with period 16. Even values return each lane's own input "
            "on the integer carriers, i.e. bit 0 behaves as an enable -- an observation with a "
            "plausible reading, NOT a semantic map. THE SPAN IS DELIBERATELY NOT NARROWED: "
            "bit 4 (value 16) is `f16_incl_scan` in this enum and NONE of the four carriers is "
            "fp16, so the inertness observation has no detection power in the dimension bit 4 "
            "would control (RE_EXPERIMENT_PROCESS_CORRECTIONS section 7). FIELD-DEPENDENCY "
            "EDGE: dtype <-> op; see the `op` note." % (TAG, E07)); n += 1

    addsem(M["simd_reduce"],
           "%s FIELD-DEPENDENCY EDGE, %s (G17P): `op` and `dtype` are NOT INDEPENDENT. The "
           "{0,1,2,3} -> {ior,isum,smax,umax} map holds at opcls=1 with dtype=3, but at dtype=7 "
           "op values 0 and 3 returned EXCLUSIVE-SCAN shapes, and at dtype=9 the predictions for "
           "op != 1 all failed. A single-field sweep of either cannot describe the other. Also "
           "bounded: with one negative word in the input, `umax` and `smin` predict the SAME "
           "vector, so op=3 is consistent with either -- a future input set needs a large "
           "positive value as well as a negative one." % (TAG, E07))
    n += 1

    # ---- simd_ballot.pred -------------------------------------------------
    addnote(M["simd_ballot"], "pred",
            "%s %s (G17P): THIS ENUM IS REFUTED AS MODELLED, and the field is NOT changed here "
            "because its own experiment requires a dedicated gated run first. Our own compiler "
            "emits byte+1 = 0x07 (pred = 0) for BOTH `simd_ballot(predicate)` AND "
            "`simd_active_threads_mask()`; the two compiled forms differ in byte+5 (psrctype "
            "0x00 vs 0x02) and in the byte+7..9 tail (`58 22 12` vs `08 02 18`). Sweeping pred "
            "over ALL 16 values changed nothing on 6 carriers whose detection-power controls "
            "all fired, including two carriers that DO compute the two different forms. "
            "Hypothesis-grade adversarial probe (raw/adversarial01, SINGLE observations, not "
            "gated): psrctype alone changed nothing; the tail alone gave a silent zero; "
            "psrctype + tail together turned 0x6C8AF35D into 0xFFFFFFFF (the all-active mask); "
            "and byte+6 `form` alone, 0x00 -> 0x14, did the same. So the ballot-form selection "
            "attributed to `pred` is carried by byte+5 / byte+6 / byte+7..9." % (TAG, E07)); n += 1

    # ---- call.b6 ----------------------------------------------------------
    addnote(M["call"], "b6",
            "%s %s (G17P): the `bit 1 must be set` rule from EXP-0179 arm S is CARRIER-DEPENDENT, "
            "not universal, and the encodable range of 128 that followed from it does not hold. "
            "Our OWN compiler emits b6 = 0x54 (bit 1 CLEAR) for both calls inside the non-leaf "
            "callee `c_mid`, and 0x56 (bit 1 SET) for the call in `_agc.main` -- so the rule is "
            "refuted by our own compiled bytes before any sweep. Measured: b6 accepts values "
            "with bit 1 clear at cl_leaf (0x04, 0x08 and 0x24 are all correct) and is COMPLETELY "
            "INERT over all 16 sampled values at cl_atomic. Re-scope it before an emitter relies "
            "on it. Evidence: raw/prefreeze/census.json; CTRL:b6@* arms." % (TAG, E06b)); n += 1

    # ---- ret / ret_luse linkmode ------------------------------------------
    for m in ("ret", "ret_luse"):
        f = fld(M[m], "linkmode")
        f["enum"] = {
            "2": "leaf (v & 3 == 2)",
            "18": "nonleaf_restore_link (0x10 = restore-link flag; v & 3 == 2)",
            "4": "FAULTS on G17P -- the old `cf_merge` reading is REFUTED (EXP-0206)",
            "5": "FAULTS on G17P -- the old `cf_merge_push` reading is REFUTED (EXP-0206)",
        }
        addnote(M[m], "linkmode",
                "%s %s (G17P, raw/g17p_20260830_run03 + run04): the ACCEPTED SET is `v & 3 == 2` "
                "-- 64 of 256 -- at FOUR independent occurrences (cl_atomic real ret_luse, "
                "cl_leaf leaf ret, cl_chain non-leaf ret, and the ret.linkmode control at "
                "cl_chain), identical at all four. EXP-0156 recorded it as `v & 7 == 4`; that is "
                "refuted by our own compiled bytes alone, because the compiler emits 0x02 and "
                "0x12 and BOTH have `v & 7 == 2`. Bit 4 (0x10) is the non-leaf restore-link "
                "flag. Enum values 4 and 5 FAULT here." % (TAG, E06b))
        n += 1

    # ---- stop -------------------------------------------------------------
    addsem(M["stop"],
           "%s CORRECTED BY %s (G17P, three carriers, two gated runs). The clause `corrupting "
           "any of it is a no-op` is TOO STRONG and is withdrawn: it is true only for the byte "
           "values previously tried. THE FINAL WORD IS FETCHED AND EXECUTED. The 24-bit BODY is "
           "inert over 73 sampled values on three carriers, and byte0 values "
           "0x00/0x01/0x0c/0x0d/0x2e/0xff are harmless -- but replacing BYTE 0 with a "
           "control-flow leader (0x0f or 0x8f) FAULTS reproducibly on all three carriers and in "
           "both runs. Most opcodes with an all-zero body happen to be harmless; a branch or "
           "return leader is not. Separately, a MID-PROGRAM `stop` genuinely terminates: "
           "synthesized over the optional 4-byte frame marker it leaves the pre-sentinel written "
           "and all 32 value words still POISON. THE DRIVER RULE IS UNCHANGED: emit 0x000000. "
           "Evidence: CTRL:byte0@* and stop.reserved@synth_mid@* arms." % (TAG, E06b))
    n += 1

    # ---- get_sr -----------------------------------------------------------
    addsem(M["get_sr"],
           "%s THE dst_hi CLAUSE ABOVE IS REFUTED ON G17P by %s and must not be relied on. "
           "`dst_hi` (byte+3 bits 5-7) was INERT across 8 of 8 values on FIVE arms in TWO stages "
           "(compute sr_c/sr_dump/sr_hi, fragment sr_f/sr_f2), two gated runs in opposite case "
           "order, 100%% per-value agreement -- with the in-dimension control firing on every "
           "arm: splicing `dst` (the LOW half of the same register number) moves the observable, "
           "and on the register-dump carrier it clobbers a NAMED codeword slot (slot 9 at "
           "dst=10), so a relocated write IS visible to this read-back plan. Relocating `dst_hi` "
           "clobbers nothing and changes nothing. What DOES move the destination bank is "
           "`dp_width` (byte+2): the documented 0x50 `top dst bank` ladder step moves the "
           "observable and clobbers codeword slot 8. Bounded to the compiled dst values on those "
           "five carriers, dst_hi 0..7 (which is its full range)." % (TAG, E07b))
    addnote(M["get_sr"], "dst_hi",
            "%s %s (G17P): NOT the destination-register extension. Inert 8/8 on five arms, two "
            "stages, two gated runs, with the in-dimension control firing on every arm. The bank "
            "appears to live in byte+2 (`dp_width`). See the descriptor semantics."
            % (TAG, E07b))
    addnote(M["get_sr"], "form",
            "%s %s (G17P): `form` is NOT merely a datapath/width modifier -- it is a READ-ENABLE "
            "whose effect is CONDITIONAL on `dp_width`. At dp_width 0x10 it is inert on all six "
            "arms; at dp_width 0x14 it changes the output on all five compute/fragment arms, "
            "INCLUDING the four whose compiler-chosen dp_width was 0x10, so the effect follows "
            "the FIELD, not the carrier. With dp_width 0x14, form=1 makes the read contribute "
            "exactly zero: out(form=1) == out(form=0) - lane*65536 for all 64 lanes on sr_hi, "
            "and the 18-selector map collapses from 6 distinct payloads to 1. FIELD-DEPENDENCY "
            "EDGE: form <-> dp_width. Bounded to dp_width in "
            "{0x00,0x04,0x10,0x11,0x14,0x15,0x50,0x54} x form in {0,1} on six carriers."
            % (TAG, E07b))
    addnote(M["get_sr"], "sr_sel",
            "%s %s (G17P) -- CANDIDATE, one dispatch shape tested, ENUM DELIBERATELY UNCHANGED. "
            "Under dispatchThreads(64) with threadsPerThreadgroup(64) -- ONE threadgroup -- "
            "selector 168 (enumerated elsewhere as `threadgroups_per_grid.x`) returns 64 on both "
            "compute arms and in both gated runs, the same value selector 152 "
            "(threads_per_threadgroup.x) returns, where the documented reading predicts 1. "
            "Selectors 169/170 return 1, which both readings predict. 168 is the ONLY selector "
            "where the host oracle was refuted, and it was refuted identically at form=0 and "
            "form=1. Candidate reading: 168 is a GRID SIZE IN THREADS (threads_per_grid.x). One "
            "dispatch shape is not enough to rewrite the enum." % (TAG, E07b))
    n += 4

    # ---- dev_scoreboard_fence ---------------------------------------------
    addsem(M["dev_scoreboard_fence"],
           "%s THE CLAUSE `The compiler inserts it around divergent control flow and before "
           "atomics/calls` IS UNSUPPORTED and is withdrawn as a description of our own "
           "compiler's behaviour (%s, G17P). Two carriers built precisely for that description "
           "-- divergent device atomics plus threadgroup_barrier(mem_flags::mem_device) -- emit "
           "ZERO occurrences of this descriptor. They emit the 0x07 `scoreboard_fence` sibling "
           "instead (`07 02 00 00` before the atomics, then `07 22 02 00`, `07 42 02 00`). "
           "Splicing that occurrence's byte0 0x07 -> 0x80 produces a legal, cleanly-executing "
           "dev_scoreboard_fence, and all 256 scope_flag values then run without fault. This "
           "reproduces EXP-0141's finding on a much stronger carrier. The INSTRUCTION is real "
           "and executes; what is refuted is the claim about when it is emitted."
           % (TAG, E07b))
    n += 1

    # ---- frag_color_store -------------------------------------------------
    addsem(M["frag_color_store"],
           "%s UNDECODED FORM, RECORDED AS A GAP (%s, G17P): a fragment shader returning a "
           "struct with a `[[sample_mask]]` member alongside `[[color(0)]]` at 4 samples emits "
           "NO frag_color_store at all, and its program does not tokenize -- one `<unknown>` "
           "record and a 20-byte leftover "
           "(`a2113f15801003c09f015410031e600014041215`). No descriptor here covers the "
           "sample-mask colour-output form. Evidence: raw/prefreeze/census03."
           % (TAG, E07b))
    n += 1

    # ---- mesh_out_src.sel -------------------------------------------------
    addnote(M["mesh_out_src"], "sel",
            "%s %s (G17P, first dispatch this field has ever had): `sel` is NOT free framing. "
            "129 of 256 values SUPPRESS THE DRAW entirely; 127 run legally and identically on "
            "the one carrier that emits the op. HAZARD MAP ONLY: this arm is "
            "CARRIER-UNDECIDABLE -- no control could move its frame to a different VALID payload "
            "-- so the 127-value apparent inertness is NOT a finding and must not be read as "
            "`inert`. Only the 129-value suppression map is a result." % (TAG, E07b)); n += 1

    # ---- tex_sample.mode --------------------------------------------------
    f = fld(M["tex_sample"], "mode")
    f["type"] = "mod"
    f["enum"] = {
        "0": "gather/read/sample_compare (baseline) -- see the note: this is a BITFIELD, not an enum",
        "16": "0x10 is INERT on every arm tested (DEF-0204-1)",
        "32": "0x20 = bit 5, LIVE under implicit LOD, INERT under explicit level() (DEF-0204-2)",
    }
    addnote(M["tex_sample"], "mode",
            "%s DEF-0204-1 / DEF-0204-2 (%s, G17P, 10 arms, ledger-verified 5119/5119, 6 of 10 "
            "arms at 256/256): THE DOCUMENTED ENUM IS WRONG. `mode` is a BITFIELD, not a "
            "three-value enum, and its live mask is AT MOST 0x2C. 0x10 is INERT on every arm -- "
            "INCLUDING the two arms where it is the compiler's own baseline. Bit 5 (0x20) is "
            "CONTEXT-DEPENDENT: live under implicit LOD, inert under explicit `level()`, "
            "reproduced at 256/256 on all five explicit-level arms -- a FIELD-DEPENDENCY EDGE, "
            "so a single-carrier sweep cannot describe it. The pre-registered model was refuted "
            "1/30 and replaced by a bit rule; the label stays `untested` because Gate E was not "
            "met." % (TAG, E06)); n += 1

    # ---- cubearray_coord_const --------------------------------------------
    addsem(M["cubearray_coord_const"],
           "%s THE `UNREACHABLE` READING IS CORRECTED BY %s (DEF-0204-3, G17P): the descriptor "
           "is SHADOWED, not absent. `f0 c0 04 <b3>` decodes as cubearray_coord_const, length 4, "
           "for all 256 values STANDALONE and at a TRAILING boundary; at an INTERIOR 4-byte "
           "boundary the same bytes decode as `pad_operand`. That is the mechanical reason for "
           "the 0 corpus firings, and it is the same failure mode %s independently found for "
           "`n4_cf_word`. Two experiments, two descriptors, same shape, found on the same day by "
           "different methods. The descriptor is still NOT deleted, and the reason is now sharper "
           "than `0 firings`." % (TAG, E06, E02))
    n += 1

    # ---- tex_write.rsv10 (NOT renamed) ------------------------------------
    addnote(M["tex_write"], "rsv10",
            "%s DEF-0204-4 (%s): `rsv10` (byte+10) IS NOT RESERVED. The census's three "
            "explicit-mip-level writes differ ONLY here -- 0x00 / 0x10 / 0x20 for levels 0 / 1 / "
            "2 -- so byte+10 carries the write's MIP LEVEL. THE FIELD IS DELIBERATELY NOT "
            "RENAMED: this is a THREE-POINT COMPILER DIFFERENTIAL (OWN-SHADER-DIFF), not a swept "
            "or spliced result, and renaming it would attach this row's existing `hardware-run` "
            "label -- earned on a different question -- to a role that was never dispatched. "
            "Renaming is exactly the name-reuse hazard DEF-0166-2 names. Recorded for the "
            "orchestrator; the rename needs one splice." % (TAG, E06)); n += 1

    # ---- vary_slot --------------------------------------------------------
    addsem(M["vary_slot"],
           "%s THE `byte+3 = the varying slot (monotone, tracks the store slot)` CLAUSE IS "
           "REFUTED ON G17P by %s, against a control that fired. Carrier c_vary4 carries four "
           "varyings with the widely separated constants 1000/2000/3000/4000 copied straight "
           "into the four colour channels, so any permutation, duplication or dropout is "
           "directly readable and NAMES THE SLOT USED. The positive control -- "
           "`vary_store.out_slot`, byte+4 of a DIFFERENT instruction -- matched the host model "
           "`out_slot == index << 5` on 26 of 32 cases exactly and agreed 32 of 32 across two "
           "captures, with ALL SIX downward relocations predicted and observed exactly by "
           "channel and value. Against that control, `vary_slot.slot` produced ZERO relocations "
           "in 256 values x 2 captures. The surviving model is that BIT 2 IS AN ENABLE and the "
           "other seven bits are inert here: 255 of 256 values match its per-case prediction "
           "(128 `ok` iff (v & 0x04) == 0, 127 `draw_gone`, 1 cross-run disagreement). "
           "Accepted sets measured at the same time: `sel` (byte+1) 16 of 256, exactly "
           "(v & 0x0f) == 0x0c -- and 0x04 and 0x0a, which this descriptor lists as valid forms, "
           "are NOT accepted; byte0 (declared match 0x00) accepts the contiguous range "
           "0x00..0x3b, 60 of 256, so it is NOT a fixed match byte; byte+2 (declared match 0x40) "
           "accepts 4 of 256, exactly (v & 0x7e) == 0x40. The match is NOT relaxed here: %s "
           "records the wider family as unresolved and four `dX 0Y 40 ZZ` instructions in the "
           "same vertex shader that isadb.instr_length cannot tokenize at all."
           % (TAG, E01, E01))
    n += 1

    # ---- EXP-0200 re-attributions -----------------------------------------
    addsem(M["n4_rt_word"],
           "%s SITE RE-ATTRIBUTION, %s (G17P stop-scan, 905 shared offsets, 99.56%% cross-run "
           "agreement, 75 offsets halting in both runs): the three signature sites this "
           "descriptor was swept at are NOT instruction boundaries. At rq_mdist+1306, "
           "rq_bbox+1316 and rq_bbox+6378 the hardware's enclosing span is TEN bytes with the "
           "signature at BYTE +6; a planted `stop` at the signature offset does not halt, while "
           "offsets around it do. EXP-0187's `n4_rt_word.dst` hazard wall (64 of 256 values "
           "fault, exactly (v & 0b110) == 0b100, confirmed on a third carrier, 6/6 carrier-runs, "
           "384 fault + 1152 clean observations, zero exceptions) is NOT withdrawn -- it is "
           "RE-ATTRIBUTED to byte +7 of a 10-byte instruction. The descriptor itself is real: at "
           "the one hardware-verified 4-byte boundary (cw_trans+324) `04 42 20 80`, generated by "
           "us from this descriptor's own match constraints with no donor field, executes with "
           "the carrier's exact oracle intact in both runs. NEXT EXPERIMENT: sweep byte +7 of "
           "the 10-byte instruction at rq_mdist+1300, not this signature." % (TAG, E02))
    addsem(M["rtq_pred"],
           "%s SITE RE-ATTRIBUTION, %s (G17P stop-scan): the swept signature site rq_bbox+966 is "
           "BYTE +6 of a TEN-byte instruction spanning [960,970), not an instruction start. As "
           "with n4_rt_word, `06 c2 00 00` generated from this descriptor's own match "
           "constraints DOES execute correctly at the one hardware-verified 4-byte boundary "
           "(cw_trans+324), so the descriptor is real and the SITES were wrong." % (TAG, E02))
    addsem(M["n4_cf_word"],
           "%s SHADOWING, %s (G17P stop-scan): this descriptor is NOT absent and NOT simply "
           "wrong -- it is SHADOWED. It exists as a real 4-byte instruction (cw_trans+324, where "
           "a planted `stop` DOES halt and the local halt sequence 320/322/324/328/334/344/352 "
           "gives spans of 2,2,4,6,10,8 bytes), but its signature ALSO matches BYTE +2 of the "
           "6-byte `pop_reconverge` `0f 06 04 01 00 00` at 3 of 4 sites in three carriers. This "
           "is the mechanical explanation of EXP-0172's DEF-0172-4 (`n4_cf_word has no "
           "observable effect at all`): that 256-value b3 sweep was sweeping BYTE +5 OF A "
           "pop_reconverge, whose body is already documented non-load-bearing. The right next "
           "experiment is a different offset, not a bigger sweep. GENERAL LESSON RECORDED: a "
           "signature scan cross-checked with decode_one is NOT sufficient to establish that an "
           "occurrence exists -- 0 of the 7 signature-derived 4-byte occurrences the hardware "
           "scanned turned out to be boundaries." % (TAG, E02))
    n += 3

    # ---- EXP-0200 measured lengths (recorded, NOT applied to `length`) -----
    addsem(M["icmpsel"],
           "%s MEASURED LENGTH DISAGREEMENT, %s (G17P stop-scan) -- RECORDED, NOT APPLIED. At "
           "`b2 17 2d 73 82 2a 04 42 20 80` (rq_mdist+1300) and `b2 07 2d 6f 82 02 04 42 20 80` "
           "(rq_bbox+1310) the hardware's enclosing instruction span is TEN bytes, where this "
           "descriptor and isadb.instr_length both say 14. The blanket change is REFUSED: every "
           "14-byte instance this project has HW-VALIDATED (EXP-0013 whole programs icmp_lt / "
           "ucmp_lt / fcmp_lt, which run on hardware and tokenize with zero leftover) has "
           "byte+2 == 0x1d, and both 10-byte hardware sites have byte+2 == 0x2d. The length is "
           "therefore CONTEXT-DEPENDENT and the corpus-fitted rule and the G17P measurement "
           "disagree exactly where each is silent about the other -- the same shape as the "
           "half_alu_fma12 length disagreement. A candidate narrowing (byte+2 == 0x2d -> 10, "
           "byte+2 == 0x1d -> 14) was measured A/B by EXP-0212 against the 1080-file own-MSL "
           "corpus; see that experiment's RESULTS.md for the numbers. Recorded here so the "
           "disagreement is visible rather than smoothed away." % (TAG, E02))
    addsem(M["icmp_pred"],
           "%s MEASURED LENGTH DISAGREEMENT, %s (G17P stop-scan) -- RECORDED, NOT APPLIED. At "
           "rq_bbox+960 the hardware's enclosing span is TEN bytes "
           "(`2a 00 2b c0 06 00 06 c2 00 00`), where this descriptor says 6. This is ONE site. "
           "The 6-byte reading is HW-anchored elsewhere (EXP-0010 `0a 01 22 82 14 22` in running "
           "control-flow programs), so the honest status is that the low-nibble-a family has at "
           "least two lengths and no discriminator is established. Changing `length` on one "
           "site would break every 6-byte instance. NEXT EXPERIMENT: find the discriminator "
           "before touching the length." % (TAG, E02))
    n += 2

    # ---- frame_marker_compact (length recorded, not applied) --------------
    addsem(M["frame_marker_compact"],
           "%s THE 2-BYTE LENGTH IS REFUTED IN THE TESTED ENVELOPE, %s (G17P, insertion at seven "
           "instruction boundaries the compiler did not choose, in two straight-line compute "
           "carriers, with a 32-word host oracle, an independent pre-sentinel and two "
           "0xDEADBEEF poison regions so correct / wrong / halted-early / never-ran are four "
           "separable observations). `60 01` as TWO bytes was correct at 0 of 7 boundaries; "
           "`60 XX` as two bytes at 0 of 254 values; `60 01 00 00` as FOUR bytes was correct at "
           "7 of 7 boundaries, and `60 XX 00 00` at 253/254 and 254/254 at the two densely swept "
           "boundaries. The detection-power control `00 00 00 00` was correct at only 2 of 7. In "
           "the 4-byte form byte+3 is inert over its full range (256/256) and byte+2 is "
           "constrained to exactly 40 of 256 values; byte0 is NOT the declared full-byte match "
           "0x60 -- 12 of a 16-value control set are accepted, including 0x20,0x30,0x40,0x50, "
           "0x70,0xa0,0xc0,0xe0. SCOPE: this is insertion into straight-line compute carriers. "
           "The corpus occurrences of `60 00 <nonzero>` are in threadgroup-atomic and "
           "divergent-control-flow contexts that were NOT re-tested, so the 2-byte reading is "
           "refuted IN THE TESTED ENVELOPE, not proven impossible everywhere. THE `length` FIELD "
           "IS NOT CHANGED HERE: `isadb.py` chooses between this and the 4-byte "
           "spill_frame_marker on byte+2 -- a byte outside the claimed 2-byte instruction -- and "
           "EXP-0212 measured the corpus cost of the 4-byte reading; see its RESULTS.md."
           % (TAG, E01))
    n += 1

    return n


# ===========================================================================
# GROUP B -- span-moving corrections
# ===========================================================================
def group_b_spans(db):
    M = by_m(db)
    n = 0

    # ---- B1: half_alu_fma12.ext splits ------------------------------------
    ins = M["half_alu_fma12"]
    ext = fld(ins, "ext")
    assert (ext["start"], ext["width"]) == (32, 64), (ext["start"], ext["width"])
    ext["start"], ext["width"] = 48, 48
    ext["note"] = (
        "%s SPAN NARROWED by %s from (start 32, width 64) to (start 48, width 48). Bits 32..47 "
        "are now the three separate fields `lensel`, `mods` and `srcC` below. What REMAINS here "
        "is the genuinely unmodelled residue, bytes +6..+11, and its measured PER-BYTE LIVENESS "
        "MAP is: byte+6 (bits 48..55) live at bits 2..7 depending on carrier; byte+7 (56..63) "
        "live at bit 4; byte+8 (64..71) and byte+9 (72..79) live at bit 1 only; byte+10 (80..87) "
        "live at bit 0; byte+11 (88..95) showed a single payload on all three arms. NOTHING HERE "
        "IS DECLARED INERT -- byte+10 is the demonstration: a single payload over all 256 values "
        "on carrier A and TWO payloads on carriers B and C in the same runs. byte+11's correct "
        "status is `inert in this exact tested envelope (opsel 6, length selector 3, three "
        "compute carriers, 16-GPR readback); global role unknown`. Evidence: "
        "analysis/ext_bytes.json, 2048 values x 3 arms x 2 runs, 0 cross-run disagreements "
        "except 1 on F12_EXT_C byte+7. DEF-0166-2 NOTICE: this name now denotes DIFFERENT BITS "
        "than it did before this edit; any verdict keyed to `half_alu_fma12.ext` and measured "
        "before 2026-08-30 is a claim about bits 32..95." % (TAG, E05))

    idx = ins["fields"].index(ext)
    new = [
        {"name": "lensel", "start": 32, "width": 2, "type": "mod",
         "note": "%s SPLIT OUT OF `ext` by %s. The LENGTH SELECTOR, already measured by "
                 "EXP-0180 and re-derived by EXP-0183: this 12-byte form is reachable only at "
                 "(opsel 6, lensel 3). Not a new observation -- a new field for a bit pair the "
                 "descriptor already documented inside a 64-bit raw blob." % (TAG, E05)},
        {"name": "mods", "start": 34, "width": 6, "type": "mod",
         "note": "%s SPLIT OUT OF `ext` by %s (G17P, byte+4 sweeps in raw/g17p_run31..32 plus "
                 "the offline re-derivation from EXP-0180's committed raw in "
                 "analysis/fit_model_offline.py). byte+4 is a MODIFIER BYTE, not opaque residue. "
                 "Measured at lensel 3: byte+4 values 0x03/0x07/0x0b/0x0f give |a|*b + c; "
                 "0x13/0x17/0x1b/0x1f give |a|*b - c, i.e. BIT 4 OF byte+4 (instruction bit 36) "
                 "NEGATES THE THIRD OPERAND; BIT 7 (instruction bit 39) additionally RELEASES "
                 "(zeroes) the byte+5 source lane; the 0x20..0x3f family produces a coherent but "
                 "UNMODELLED result. Within this 6-bit span the live bits are 3,4,5,6,7 of "
                 "byte+4 and bit 2 of byte+4 (instruction bit 34) showed no effect on any of the "
                 "three arms. PARTIAL: reported as a liveness + partial-semantic map, not as a "
                 "complete modifier decode." % (TAG, E05)},
        {"name": "srcC", "start": 40, "width": 8, "type": "reg",
         "note": "%s SPLIT OUT OF `ext` by %s (G17P). THE THIRD fp16 SOURCE. Half-register "
                 "descriptor h = (reg<<1)|is_high, with bit 7 a DON'T-CARE (128/128). This is "
                 "the strongest single measurement in that experiment: byte+5 has 256/256 "
                 "hardware identity preserved AND 256/256 FULL-VECTOR HOST-ORACLE MATCH on every "
                 "one of the three arms, in both runs, 29 distinct payloads. Naming it `srcC` "
                 "matches the 8-byte anchor's arithmetic "
                 "`r[byte0>>4].lo = fp16(h[byte+1] * h[byte+3] + h[byte+5])` already committed "
                 "in this descriptor's semantics. Evidence: analysis/ext_bytes.json."
                 % (TAG, E05)},
    ]
    ins["fields"][idx:idx] = new
    addsem(ins,
           "%s `ext` IS NO LONGER ONE 64-BIT FIELD (%s). Bits 32..47 are split out as `lensel` "
           "(32..33), `mods` (34..39) and `srcC` (40..47); `ext` retains only bits 48..95, the "
           "genuinely unmodelled residue. The `DO NOT EMIT until bits 34..95 are modelled` rule "
           "and `emit_unsafe` both STAND -- bits 48..95 are still unmodelled. Gate A for that "
           "experiment reports 2048 dispatched cases -> 2041 distinct ACTUAL encodings per arm; "
           "the seven collisions are exactly the eight identity mutations (setting a byte to the "
           "value the anchor already has; bytes +4..+11 are `13 12 00 00 00 80 01 00`), which "
           "all reproduce the anchor encoding. Benign self-collision, NOT a match-bit collision; "
           "`dst`, `dstlo` and `b3` have no collisions at all." % (TAG, E05))
    n += 4

    # ---- B3: simd_reduce.op narrows 8 -> 3 --------------------------------
    ins = M["simd_reduce"]
    op = fld(ins, "op")
    assert (op["start"], op["width"]) == (8, 8)
    op["width"] = 3
    op["note"] = (
        "%s WIDTH NARROWED by %s from 8 to 3 (start unchanged at 8). Measured, not assumed: "
        "analysis/report.py compares the observed 32-lane vector at every value v against the "
        "vector at v XOR (1<<b), in BOTH runs, on ALL FOUR reduce carriers -- live bits [2:0], "
        "inert-within-field bits [7:3], and the observation repeats with PERIOD 8 across the "
        "full 256-value sweep. `op` is a 3-bit opcode occupying an 8-bit byte; bits 11..15 are "
        "now the separate field `op_hi`. SEMANTIC BOUND: the {0,1,2,3} -> {ior,isum,smax,umax} "
        "map is established at opcls=1 with dtype=3 and does NOT generalise -- see the "
        "descriptor's field-dependency note. DEF-0166-2 NOTICE: this name now denotes bits "
        "8..10; any verdict keyed to `simd_reduce.op` and measured before 2026-08-30 is a claim "
        "about bits 8..15." % (TAG, E07))
    idx = ins["fields"].index(op)
    ins["fields"].insert(idx + 1, {
        "name": "op_hi", "start": 11, "width": 5, "type": "mod",
        "note": "%s SPLIT OUT OF `op` by %s. INERT-WITHIN-FIELD on all four reduce carriers over "
                "the full 256-value byte sweep in both gated runs (the period-8 repeat IS this "
                "field being ignored). Per RE_EXPERIMENT_PROCESS_CORRECTIONS section 7 the "
                "bounded wording is `inert in this exact tested envelope (four simd/quad reduce "
                "carriers, opcls 1, dtype in {3,7,9,18}); global role unknown` -- it is NOT "
                "declared reserved." % (TAG, E07)})
    n += 2

    # ---- B4: irotate.operands splits --------------------------------------
    ins = M["irotate"]
    ops = fld(ins, "operands")
    assert (ops["start"], ops["width"]) == (24, 40)
    ops["start"], ops["width"] = 48, 8
    ops["type"] = "imm"
    ops["note"] = (
        "%s SPAN NARROWED by %s from (start 24, width 40) to (start 48, width 8) -- byte+6 "
        "alone. THIS IS THE IMMEDIATE ROTATE AMOUNT and it is the one byte of the five that "
        "this row's existing label was earned on: `byte+6 = 4*(32-K)` gives rotate-LEFT-by-K, "
        "matched against an EXACT host-computed 32-word vector at all 33 modelled values on "
        "four carriers in two runs -- 264 exact vector matches, zero misses -- and, "
        "independently, by searching all 32 amounts for one that reproduces each observation: a "
        "single rotate-left amount is recovered at exactly those 33 values, 32 DISTINCT amounts, "
        "with no formula disagreements. Bounded negative: values with byte+6 >> 2 > 32 are "
        "reproduced by NO rotate amount, 0 of 31, role unknown. THE NAME IS NOW A MISNOMER -- it "
        "should be `amount`; the rename is left to the orchestrator because renaming it here "
        "would move this row's label onto a new name as well as new bits. DEF-0166-2 NOTICE: "
        "this name now denotes bits 48..55; any verdict keyed to `irotate.operands` and measured "
        "before 2026-08-30 is a claim about bits 24..63." % (TAG, E04))
    idx = ins["fields"].index(ops)
    common = ("%s SPLIT OUT OF `operands` by %s: the 40-bit raw blob is FIVE one-byte "
              "sub-fields with the same meanings EXP-0139 established for the identical blob in "
              "`iunary` (DEF-0139-1), plus the rotate amount that descriptor does not have. "
              "Byte-wise dense 0..255 on two carriers plus the first joint 40-bit arm, two gated "
              "runs in OPPOSITE case order, 0 disagreements of 3212. " % (TAG, E04))
    ins["fields"][idx:idx] = [
        {"name": "rot_dst", "start": 24, "width": 8, "type": "reg",
         "note": common + "byte+3 = DESTINATION: reproduces at {0,1}, faults 192..255."},
        {"name": "op_enable", "start": 32, "width": 8, "type": "mod",
         "note": common + "byte+4 = OP-ENABLE GATE: 128 of 256 values reproduce."},
        {"name": "rot_src", "start": 40, "width": 8, "type": "reg",
         "note": common + "byte+5 = SOURCE: reproduces at 0..3."},
    ]
    ins["fields"].insert(idx + 4, {
        "name": "amt_tail", "start": 56, "width": 8, "type": "mod",
        "note": common + "byte+7 = tail: reproduces at the 8 EVEN values 0..14."})
    addsem(ins,
           "%s `operands` WAS NOT ONE FIELD (%s, G17P). Its five bytes are `rot_dst` (byte+3), "
           "`op_enable` (byte+4), `rot_src` (byte+5), the rotate amount (byte+6, still carrying "
           "the legacy name `operands`) and `amt_tail` (byte+7). The joint 40-bit arm -- the "
           "first this field has ever had -- dispatched 70 values ({0,1,2,max-1,max}, all 40 "
           "powers of two, compiled +/-1, and 24 fixed asymmetric interiors) and reproduces at "
           "exactly {compiled, compiled+1}, with 11-15 contained faults, 0 hangs, and the abort "
           "budget never reached. EXP-0189's `UNSTABLE` refusal does NOT reproduce: 0 of 3212 "
           "(arm, value) pairs disagree." % (TAG, E04))
    n += 5

    # ---- B5: pop_reconverge.reserved splits -------------------------------
    ins = M["pop_reconverge"]
    r = fld(ins, "reserved")
    assert (r["start"], r["width"]) == (32, 16)
    r["width"] = 8
    r["note"] = (
        "%s SPAN NARROWED by %s from (start 32, width 16) to (start 32, width 8) -- byte+4 "
        "alone -- and THE NAME `reserved` IS WRONG FOR THIS BYTE. byte+4 is LOAD-BEARING AND "
        "MUST BE ZERO on the tested envelope. At cf_ifnl+184 (the 0x24 bank, an if/else on the "
        "LANE ID) the 9 correct values are exactly the 9 sampled values whose LOW BYTE IS ZERO "
        "-- {0x0000,0x0100,0x0200,0x0400,0x0800,0x1000,0x2000,0x4000,0x8000}, spanning 9 "
        "distinct high-byte values -- and the 43 values with a non-zero low byte all produce ONE "
        "IDENTICAL WRONG PAYLOAD, with no exceptions in the sampled set. Confirmed on a QUIET "
        "machine: the pair run05 <-> run07 both ran with 0-2 foreign GPU processes and agree on "
        "52 of 52 values. The model (`low byte must be zero`) is POST-HOC -- no pre-registered "
        "model survived. The two null arms (cf_nl2, cl_atomic) are `carrier-undecidable`, not "
        "evidence of inertness: their divergence is largely uniform across the threadgroup and "
        "cannot express a reconvergence error, which cf_ifnl's lane-id branch can. The rename to "
        "`reserved_lo` is left to the orchestrator. DEF-0166-2 NOTICE: this name now denotes "
        "bits 32..39; any verdict keyed to `pop_reconverge.reserved` and measured before "
        "2026-08-30 is a claim about bits 32..47." % (TAG, E06b))
    idx = ins["fields"].index(r)
    ins["fields"].insert(idx + 1, {
        "name": "reserved_hi", "start": 40, "width": 8, "type": "mod",
        "note": "%s SPLIT OUT OF `reserved` by %s: byte+5 is INERT over the 9 high-byte values "
                "tested ({0,1,2,4,8,16,32,64,128}) while byte+4 is load-bearing in the same "
                "sweep -- a clean separation with no exceptions in the sampled set. Bounded "
                "wording: `inert over 9 sampled values on the cf_ifnl carrier; global role "
                "unknown`. It is NOT declared reserved." % (TAG, E06b)})
    addsem(ins,
           "%s db.json MODELLED BITS 32..47 AS ONE 16-BIT `reserved` FIELD OF TYPE `mod`; %s "
           "refutes that: byte+4 is load-bearing and byte+5 is inert over the tested set. See "
           "the two field notes." % (TAG, E06b))
    n += 3

    return n


# ===========================================================================
# GROUP D -- match-bit corrections (tokenization-affecting)
# ===========================================================================
def group_d_match(db):
    M = by_m(db)
    n = 0

    # ---- half_pack byte0: 8 pinned bits -> 4 ------------------------------
    ins = M["half_pack"]
    assert ins["match"] == [[0, 8, 24]], ins["match"]
    ins["match"] = [[0, 4, 8]]
    ins["fields"].insert(0, {
        "name": "dst", "start": 4, "width": 4, "type": "reg",
        "note": "%s ADDED by %s. db.json pinned ALL EIGHT bits of byte0 in `match` (0x18), so "
                "EVERY db-EXPRESSIBLE ENCODING WROTE r1 and the instruction had to be built byte "
                "by byte to express any other destination. byte0's HIGH NIBBLE is the "
                "destination GPR and its LOW nibble (8) is the family tag -- the same defect "
                "class as DEF-0180-1 one family over, and consistent with this descriptor's own "
                "committed semantics (`the SAME op appears as 0x08/0x18/0x28/0x38 for dst "
                "r0/r1/r2/r3`). Arms HP_C/HP_D run the same instruction at destination nibble 7 "
                "(`78 0d 18 11`) and the host oracle matches 256/256 there as well, so the "
                "nibble is a REAL DESTINATION SELECTOR and not a fixed opcode bit."
                % (TAG, E05)})
    addsem(ins,
           "%s THE byte0 MATCH IS RELAXED from 8 pinned bits (0x18) to 4 (low nibble 0x8) by %s; "
           "byte0's high nibble is now the `dst` field. Before this edit no db-expressible "
           "half_pack could write any register but r1." % (TAG, E05))
    n += 2

    # ---- sfu_marker byte0: (b0 & 0x07) == 6 -> (b0 & 0x1f) == 6 -----------
    ins = M["sfu_marker"]
    assert ins["match"] == [[0, 3, 6], [8, 2, 2]], ins["match"]
    ins["match"] = [[0, 5, 6], [8, 2, 2]]
    b0hi = fld(ins, "b0_hi")
    b0hi["start"], b0hi["width"] = 5, 3
    b0hi["note"] = ((b0hi.get("note", "") + " ") if b0hi.get("note") else "") + (
        "%s SPAN NARROWED by %s from (start 3, width 5) to (start 5, width 3), and the "
        "descriptor's byte0 match TIGHTENED from (b0 & 0x07) == 6 to (b0 & 0x1f) == 6. "
        "Of the 32 values the declared match admits, EXACTLY 8 ARE ACCEPTED, and they are "
        "exactly (b0 & 0x1f) == 0x06 -- {0x06,0x26,0x46,0x66,0x86,0xa6,0xc6,0xe6}: bits 5-7 "
        "free, bits 3-4 MUST BE 0. byte0 = 0x0e also satisfies the OLD declared match but is "
        "`stop` -- it halts the program (poison in the output, sentinel present). 36 byte0 "
        "values are accepted in total at each swept site; the other 28 have (b0 & 0x07) == 4, "
        "the get_sr/mov_imm low-3-bits-100 family, a DIFFERENT descriptor, and are not evidence "
        "about this one. The 2-byte length is confirmed in the same arm by insertion at seven "
        "instruction boundaries the compiler did not choose: `06 02` correct at 7 of 7, while "
        "`00 00`, `ff ff` and deleting two bytes were each correct at 0 of 7. DEF-0166-2 "
        "NOTICE: this name now denotes bits 5..7; any verdict keyed to `sfu_marker.b0_hi` and "
        "measured before 2026-08-30 is a claim about bits 3..7." % (TAG, E01))
    addnote(ins, "b1_hi",
            "%s %s adds a FRAMING result that does not contradict the semantic one already "
            "recorded here: byte+1 is UNCONSTRAINED FOR FRAMING -- 256 of 256 accepted at "
            "insertion boundary 94 and 255 of 256 at boundary 74 (the single exception is a lone "
            "fault against a clean observation on a measured-busy machine). EXP-0146/EXP-0157 "
            "measured byte+1 in a REPLACEMENT context inside an SFU carrier, where a wrong value "
            "produced a wrong `fast::sin`: that is a SEMANTIC constraint on the SFU control "
            "word, this is a FRAMING constraint. Both hold and the two axes must not be "
            "collapsed." % (TAG, E01))
    n += 2

    # ---- frag_depth_store: byte+1 needs 2 bits; byte+2's match unenforced --
    ins = M["frag_depth_store"]
    assert ins["match"] == [[0, 8, 215], [8, 8, 20], [16, 8, 84]], ins["match"]
    ins["match"] = [[0, 8, 215], [9, 2, 2]]
    ins.setdefault("match_notes", []).append({
        "name": "b1_declared", "start": 8, "width": 8, "type": "raw", "value": 20,
        "note": "%s the previous full-byte pin, kept for provenance. %s measured the accepted "
                "set as exactly (v & 0x06) == 0x04, 64 of 256, on two carriers in two captures."
                % (TAG, E01)})
    # Relaxing the match FREES 14 bits that would otherwise carry neither a match
    # nor a field -- a modelling hole is strictly worse for an emitter than an
    # over-declared match. Give the freed bits fields with the compiler's canonical
    # value and the measured accepted set recorded.
    ins["fields"][0:0] = [
        {"name": "b1_lo", "start": 8, "width": 1, "type": "mod",
         "note": "%s FREED by %s's match correction (byte+1 bit 0). The declared full-byte "
                 "match 0x14 needs only bits 1-2; this bit is free. CANONICAL EMIT VALUE 0 "
                 "(0x14 & 0x01). Accepted set for the whole byte: (v & 0x06) == 0x04, 64 of "
                 "256, two carriers, two captures." % (TAG, E01)},
        {"name": "b1_hi", "start": 11, "width": 5, "type": "mod",
         "note": "%s FREED by %s's match correction (byte+1 bits 3-7). CANONICAL EMIT VALUE "
                 "2 (0x14 >> 3). Accepted set for the whole byte: (v & 0x06) == 0x04, 64 of "
                 "256, two carriers, two captures." % (TAG, E01)},
        {"name": "b2", "start": 16, "width": 8, "type": "mod",
         "note": "%s FREED by %s's match correction. byte+2 was declared a full-byte match "
                 "0x54 and the HARDWARE DOES NOT ENFORCE IT AT ALL: all 256 values leave both "
                 "the colour and the depth surface byte-identical on both carriers in both "
                 "captures (512 dispatched, 512 ok), while b5/b3/b4/byte+1 all move on the same "
                 "instruction, so the arm's detection power is proven. CANONICAL EMIT VALUE "
                 "0x54. Bounded wording: `inert over 0..255 in the c_depth and c_depth2 "
                 "fragment carriers with a depth attachment; global role unknown`."
                 % (TAG, E01)},
    ]
    ins["match_notes"].append({
        "name": "b2_declared", "start": 16, "width": 8, "type": "raw", "value": 84,
        "note": "%s the previous full-byte pin, kept for provenance. %s measured that the "
                "hardware DOES NOT ENFORCE IT AT ALL: all 256 values leave both surfaces "
                "byte-identical on both carriers in both captures (512 dispatched, 512 ok)."
                % (TAG, E01)})
    addsem(ins,
           "%s MATCH CORRECTED BY %s (G17P, the first experiment ever to read the "
           "Depth32Float attachment back per pixel). The descriptor's ROLE is now OBSERVED, not "
           "inferred: unmutated, the depth attachment holds the shader's [[depth]] output "
           "exactly at three probe pixels with three DISTINCT values on TWO independent carriers "
           "with DIFFERENT depth functions, matching the host oracle in both; clearing byte+5 "
           "bit 1 makes the depth attachment receive 0.0 at every covered pixel while the colour "
           "value at every covered pixel is unchanged (128 of 256 b5 values, identically on both "
           "carriers and in both captures); 0 of 2304 mutations of this instruction's own bytes "
           "moved the COLOUR surface while leaving the depth surface unchanged; and with the "
           "instruction REPLACED the tile is discarded entirely and the depth attachment keeps "
           "the clear value 1.0. TWO MATCH BYTES WERE OVER-DECLARED: byte+1 was pinned to the "
           "whole byte 0x14 but only two bits are required -- the accepted set is exactly "
           "(v & 0x06) == 0x04, 64 of 256 -- and byte+2 was pinned to 0x54 but IS NOT ENFORCED "
           "AT ALL, 256 of 256 accepted on both carriers in both captures. The arm's detection "
           "power is proven on the same instruction by b5, b3, b4 and byte+1. Accepted sets for "
           "the operand bytes, same arm: b3 4 of 256, (v & 0xfc) == 0x00; b4 8 of 256, "
           "(v & 0x1f) == 0x00; b5 128 of 256, (v & 0x02) == 0x02. Bounded wording for the "
           "byte+2 result: `inert over 0..255 in the c_depth and c_depth2 fragment carriers with "
           "a depth attachment; global role unknown`." % (TAG, E01))
    n += 1

    return n


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    src, dst = sys.argv[1], sys.argv[2]
    only = GROUPS
    for i, a in enumerate(sys.argv):
        if a == "--only":
            only = sys.argv[i + 1].split(",")
    db = json.load(open(src))
    total = 0
    for g in GROUPS:
        if g in only:
            k = {"a_notes": group_a_notes, "b_spans": group_b_spans,
                 "d_match": group_d_match}[g](db)
            print("  %-10s %3d edits" % (g, k))
            total += k
    json.dump(db, open(dst, "w"), indent=1)
    print("wrote %s (%d edits)" % (dst, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
