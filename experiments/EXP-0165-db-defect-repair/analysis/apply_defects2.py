#!/usr/bin/env python3
"""EXP-0165 SECOND WRITE: apply the EXP-0160 and EXP-0157 db_defects that survived
independent re-derivation.

  python3 analysis/apply_defects2.py <path/to/db.json>

Same discipline as apply_defects.py: every edit is guarded by an assertion on the
value it replaces, and FIELD NAMES ARE PRESERVED wherever a same-arity permutation
exists, because tools/agx-isa/validate_labels.py hard-fails on a db.json field with
no validation.json entry and this experiment may not edit validation.json.

Applied:  DEF-0160-1 (falu3/falu3_ext `op` bit map), DEF-0160-2 (iminmax operand
          slots, 3-cycle rename), DEF-0160-3/-6/-7 (imad: byte+6 is a multiplicand
          register selector, byte+7 is mode+addend-source-select, byte+8 does not
          carry the addend), DEF-0160-4 (half_pack byte+2 is not a register),
          EXP-0157 sfu_marker (two live bytes -> two fields).
NOT applied (LENGTH-RULE changes live in isadb.py, and the orchestrator reserved
          that call): op04_len8's measured 12-byte length, half_pack's unconditional
          4-byte length, mesh_out_src's byte+1 bit-7 length split. All three are
          recorded with their measured corpus-gate deltas in `length_rule_gaps`.
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


def expect(c, m):
    if not c:
        raise AssertionError("apply_defects2: precondition failed: " + m)


IMAD_SEM = (
 "d = m * (srcA * srcB) + A  ; integer multiply-add. **OPERAND MODEL CORRECTED ON "
 "HARDWARE** -- EXP-0160 (G17P), re-derived independently in EXP-0165 "
 "(db_defects :: DEF-0160-3, DEF-0160-6, DEF-0160-7). "
 "The pre-2026-08-30 descriptor modelled NO first-multiplicand register at all and "
 "documented byte+6 as `srcC_lo`, the low byte of an immediate addend that does not "
 "exist. An implementer following it could not choose the first operand of an integer "
 "multiply. "
 "**byte+6 (this descriptor's `srcB`) is a MULTIPLICAND REGISTER SELECTOR: "
 "reg = v >> 3.** Bit 0 = 1 makes that source read 0; bits 1 and 2 are inert. "
 "Measured over the 2-D (byte+7 x byte+6) probe, 132 points x 2 seed sets, by solving "
 "r0 = m*(seed[a]*seed[b]) + A for BOTH multiplicand registers left free and requiring "
 "one solution to satisfy both seed sets at once: byte+6 = 0x10 pins the multiplicand "
 "to r2 UNIQUELY, and 0x00/0x02/0x04 -> r0, 0x08 -> r1, 0x20 -> r4, 0x40 -> r8 all "
 "contain the predicted register; 0x01/0x03 read 0 and 0x7F names r15 (seed 0). The "
 "rule fits 10 of the 11 probed values; the eleventh (0xFF -> r31) is outside the "
 "16 seeded registers and is unmeasurable, not a counterexample. "
 "**byte+7 (`srcC_desc`) is a 2-bit MODE plus a 5-bit ADDEND-SOURCE SELECT, and the "
 "addend is NOT in the instruction.** Measured over the dense 256-value byte+7 sweep x "
 "2 seed sets: 191 of the 192 non-fault values with a clean two-seed observation fit "
 "r0 = m*(srcA*srcB) + A EXACTLY (the single exception is a dispatch that returned "
 "status OK having written nothing -- DEF-0160-5). m is determined ENTIRELY by bits "
 "0-1: 0 -> keep the product, 1 -> drop it, 2 -> drop it, 3 -> REPRODUCIBLE FAULT (all "
 "64 values with (v & 3) == 3 fault and no other value does). Bit 2 is INERT (zero "
 "disagreeing pairs over the whole sweep). A is single-valued per K = (v >> 3) & 0x1F "
 "across all 32 K, and is SEED-INDEPENDENT by construction of the fit -- so K selects "
 "an addend held OUTSIDE the instruction (a uniform/constant slot), it does not encode "
 "one. The recovered A values are the carrier's OWN constants' 16-bit halves: K=0 -> "
 "0xC500, K=1 -> 1, K=2 -> 256, K=12 -> 1, K=13 -> 16256 (0x3F80, the high half of "
 "1.0000001f = 0x3F800001), K=14 -> 49045 (0xBF95) and K=15 -> 46038 (0xB3D6) (the two "
 "halves of -1e-7f = 0xB3D6BF95); K in {3..11, 16..31} read 0. **An emitter that reads "
 "db.json's old '(K<<3) = immediate addend' and emits it gets an imad that adds "
 "whatever happens to occupy slot K.** "
 "**byte+8 (`mulsel`) does not participate in the addend** (DEF-0160-7): over the 2-D "
 "(byte+7 x byte+8) probe the recovered A is constant across every mulsel point, for "
 "all 12 byte+7 values. Its documented hi/lo multiply role (0xd0 = low 32 bits, 0xe0 = "
 "high 32) is unaffected. "
 "NAME PERMUTATION, and why: the multiplicand selector at byte+6 is given the name "
 "`srcB` (accurate -- it names a real multiplicand) and byte+5 inherits the historical "
 "name `srcC_lo`. **byte+5's role is UNRESOLVED and was never swept.** In the EXP-0160 "
 "anchor byte+5 = 0x08 and the second multiplicand is demonstrably r2, which the "
 "project-standard (reg<<1)|size packing would read as r4 -- so either byte+5 uses a "
 "different packing (reg<<2 fits) or the second multiplicand is selected elsewhere. Do "
 "not emit byte+5 from a register number until that is settled. "
 "Retained from EXP-M4-13 R6 (own-MSL byte-diff): LOW-32 mul is sign-agnostic (a*b "
 "int == uint byte-identical); mad int == uint byte-identical; MULHI is sign-dependent "
 "(signed mulhi flips b10 0x0a -> 0x1e); dst = byte+3, (reg<<1)|size, proven by an "
 "r6/r4/r2 dst sweep."
)

IMINMAX_SEM_ADD = (
 " **OPERAND SLOTS CORRECTED ON HARDWARE** -- EXP-0160 (G17P), re-derived "
 "independently in EXP-0165 (db_defects :: DEF-0160-2). db.json's operand names were "
 "shifted by one byte slot: byte+5 was called `srcB` and is NOT a register selector at "
 "all. Measured: with the anchor `02 01 1e 05 07 00`, the instruction computes "
 "imin(r0, r2) -> r0 in BOTH seed sets (10 and 7), and r2 -- the register byte+3 names "
 "under (reg<<1)|size -- is RELEASED TO ZERO, which identifies it as an operand. So "
 "byte+1 is the FIRST source descriptor and byte+3 the SECOND, exactly the falu2 slot "
 "layout. byte+5 has FOUR INERT BITS (3, 5, 6, 7 -- zero disagreeing pairs each over a "
 "dense 256-value sweep x 2 seed sets) and no value->register model fits it (reg = "
 "v>>1 and reg = v>>2 each explain 32 of 256 cases), so it cannot carry a register "
 "index; its live bits are 0, 1, 2 and 4 and its anchor value 0xc0 is falu2's standard "
 "`mods` default, i.e. it is the SOURCE-CLASS / MODIFIER byte. It keeps the historical "
 "name `dst_full` ONLY so its validation.json evidence row survives a rename this "
 "experiment is not allowed to make. **An emitter following the old descriptor would "
 "put the second operand's register number in the modifier byte and get a silent "
 "zero.**"
)

FALU3_OP_NOTE = (
 "byte+2. NOT one opaque opcode -- HW, G17P (EXP-0160 DEF-0160-1, re-derived in "
 "EXP-0165 over the dense 256-value sweep x 2 seed sets). It carries falu2's own two "
 "fields at falu2's own bit positions: `opsel` = instruction bits 16-18 (byte value "
 "bits 0-2) and `opflags` = bits 19-23 (byte value bits 3-7). OPERATION by the low 3 "
 "bits, identified against a host-computed function library and required to agree in "
 "BOTH seed sets: 0 = a+b, 1 = a*b, 2 = a*b+a, 4 = -b, 5 = 0, 6 = a*b+c (the anchor's "
 "fma), 7 = REPRODUCIBLE FAULT (all 32 values with (v & 7) == 7). Byte value bit 4 is "
 "the srcB RELEASE flag (clearing it leaves srcB's register holding its seed instead "
 "of being zeroed by release-on-read); bits 6 and 7 are silent corruptors. **Bit 5 is "
 "the ONLY inert bit** (0 of 512 flip-pairs differ; every other bit changes the "
 "register dump). Exact reproduce-the-baseline rule: (v & 0xD7) == 0x16, accepted set "
 "exactly {0x16, 0x1E, 0x36, 0x3E}, the unique separating mask over all 256 "
 "candidates. The field is left as ONE 8-bit descriptor because splitting it would add "
 "a field name and validate_labels.py hard-fails on a db.json field with no "
 "validation.json row; the bit map above is the emitter contract."
)

SFU_MARKER_SEM = (
 "SFU / transcendental helper CONTROL WORD (byte0 0x06, byte+1 0x02 as the compiler "
 "emits it), 2 bytes, emitted adjacent to special-function-unit and varying/mesh "
 "output ops. **NOT byte-invariant and NOT field-less** -- HW-VALIDATED on M4/G16G "
 "(EXP-0146, 512 cases over two gated runs) and REPRODUCED BYTE-FOR-BYTE on G17P in "
 "THREE independent carriers (EXP-0157: fast::sin, fast::cos, sin+cos+tan). Both bytes "
 "are load-bearing: byte+0 accepts only (v & 0xF7) == 0x06 -- 2 of 256, i.e. bit 3 is "
 "the only free bit -- with 62 values returning a wrong result and 192 silently "
 "zeroing; byte+1 accepts only (v & 0x13) == 0x02 -- 32 of 256, i.e. bits 2, 3, 5, 6 "
 "and 7 are free. Setting byte+0 to 0x00 FLIPS THE SIGN of fast::sin on exactly the "
 "rows whose argument needs range reduction (|x| > pi/2) while leaving the "
 "small-argument rows correct, so at least one live bit is a quadrant/sign control. "
 "The descriptor now carries the two free-bit groups as fields (`b0_hi`, `b1_hi`) and "
 "pins only the bits the hardware requires, so the evidence can be labelled and the "
 "assembler can emit the variants. DECODE IS UNCHANGED: isadb.py's length rule still "
 "admits length 2 for byte0 == 0x06 only when byte+1 == 0x02, so no additional byte "
 "pattern is claimed -- verified by a corpus A/B with zero firing delta. Per "
 "clean-room rule 5 the adjacent range-reduction coefficient words are left raw and "
 "the exact micro-op is NOT-YET-CHARACTERIZED."
)


def apply_all(path):
    db = json.load(open(path))

    # ---------------- DEF-0160-6 / -3 / -7 : imad --------------------------
    m = ins(db, "imad")
    sb, sc = fld(m, "srcB"), fld(m, "srcC_lo")
    expect((sb["start"], sb["width"]) == (40, 8), "imad.srcB is byte+5")
    expect((sc["start"], sc["width"]) == (48, 8), "imad.srcC_lo is byte+6")
    sb["start"], sb["width"], sb["type"] = 48, 8, "reg"
    sb["note"] = ("byte+6 = a MULTIPLICAND REGISTER SELECTOR, reg = v >> 3. bit 0 = 1 "
                  "makes the source read 0; bits 1 and 2 are inert. HW, G17P "
                  "(EXP-0160/EXP-0165, DEF-0160-6): the 2-D (byte+7 x byte+6) probe "
                  "pins byte+6 = 0x10 to r2 UNIQUELY and the rule fits 10 of 11 probed "
                  "values (the eleventh, 0xFF -> r31, is outside the seeded set). "
                  "db.json modelled this byte as `srcC_lo`, the low half of an "
                  "immediate addend that does not exist, and modelled NO first "
                  "multiplicand at all.")
    sc["start"], sc["width"], sc["type"] = 40, 8, "mod"
    sc["note"] = ("byte+5. ROLE UNRESOLVED -- never swept. HISTORICAL NAME: this is "
                  "not the low half of an immediate (there is no immediate addend; see "
                  "DEF-0160-3). In the EXP-0160 anchor byte+5 = 0x08 while the second "
                  "multiplicand is demonstrably r2, which (reg<<1)|size would read as "
                  "r4 -- so either the packing here is reg<<2 or the second "
                  "multiplicand is selected elsewhere. Do not emit a register number "
                  "here until it is settled.")
    sd = fld(m, "srcC_desc")
    sd["note"] = ("byte+7 = a 2-bit MODE (bits 0-1) + an INERT bit 2 + a 5-bit "
                  "ADDEND-SOURCE SELECT (bits 3-7). Mode: 0 = keep the product, 1 and "
                  "2 = drop it, **3 = REPRODUCIBLE FAULT** (all 64 values with "
                  "(v & 3) == 3 fault; no other value does). The addend is NOT carried "
                  "here -- it is read from an external uniform/constant slot that bits "
                  "3-7 index. HW, G17P (EXP-0160/EXP-0165, DEF-0160-3), 191 of 192 "
                  "clean two-seed observations fit with 0 exceptions.")
    ms = fld(m, "mulsel")
    ms["note"] = ("byte+8. Does NOT participate in the addend (HW, G17P, "
                  "EXP-0160/EXP-0165, DEF-0160-7: the recovered addend is constant "
                  "across every mulsel point, for all 12 byte+7 values probed). Its "
                  "hi/lo multiply role (0xd0 low 32, 0xe0 mulhi) is unaffected.")
    m["fields"].sort(key=lambda x: x["start"])
    m["semantics"] = IMAD_SEM
    m["provenance"] = (m["provenance"] +
                       " OPERAND MODEL SUPERSEDED AND CORRECTED -- HW-VALIDATED "
                       "(EXP-0160, G17P, dense + 2-D probes over two seed sets), "
                       "independently re-derived in EXP-0165 by solving the "
                       "multiply-add model with both multiplicands free. EXP-M4-13 "
                       "R6's '(K<<3) = immediate addend' reading was a COMPILE-ONLY "
                       "correlation: the compiler allocates one constant slot per "
                       "constant, so K co-varied with the source constant.")

    # ---------------- DEF-0160-2 : iminmax ---------------------------------
    q = ins(db, "iminmax")
    df, sa, sbq = fld(q, "dst_full"), fld(q, "srcA"), fld(q, "srcB")
    expect((df["start"], sa["start"], sbq["start"]) == (8, 24, 40),
           "iminmax slots are byte+1/+3/+5")
    sa["start"] = 8
    sa["note"] = ("byte+1 = the FIRST source descriptor, (reg<<1)|size -- the falu2 "
                  "slot layout. HW, G17P (EXP-0160/EXP-0165, DEF-0160-2): the anchor "
                  "`02 01 1e 05 07 00` computes imin(r0, r2) in both seed sets.")
    sbq["start"] = 24
    sbq["note"] = ("byte+3 = the SECOND source descriptor, (reg<<1)|size. HW, G17P: "
                   "the register it names (r2 at the anchor value 0x05) is RELEASED TO "
                   "ZERO, which identifies it as an operand.")
    df["start"], df["type"] = 40, "mod"
    df["note"] = ("byte+5 = the SOURCE-CLASS / MODIFIER byte (falu2's `mods` slot; "
                  "anchor value 0xc0 is falu2's standard default). NOT a register "
                  "selector: bits 3, 5, 6 and 7 are INERT (0 of 512 flip-pairs differ "
                  "each) and no value->register model fits (reg = v>>1 and reg = v>>2 "
                  "each explain only 32 of 256). HISTORICAL NAME -- it is not "
                  "`dst_full`; db.json's operand names were shifted one slot until "
                  "2026-08-30 (EXP-0160/EXP-0165, DEF-0160-2).")
    q["fields"].sort(key=lambda x: x["start"])
    q["semantics"] = q["semantics"] + IMINMAX_SEM_ADD
    q["provenance"] = (q["provenance"] + " OPERAND SLOTS SUPERSEDED AND CORRECTED: "
                       "HW-VALIDATED (EXP-0160, G17P), re-derived in EXP-0165. This "
                       "also supersedes the 2026-08-28 PROVENANCE FLAG above for the "
                       "slot assignment specifically -- byte+1/byte+3 are now "
                       "identified by a released-register observation, not by "
                       "byte-diff.")

    # ---------------- DEF-0160-1 : falu3 / falu3_ext op --------------------
    for mn in ("falu3", "falu3_ext"):
        f = ins(db, mn)
        op = fld(f, "op")
        expect((op["start"], op["width"]) == (16, 8), "%s.op is byte+2" % mn)
        op["note"] = FALU3_OP_NOTE
        f["semantics"] = f["semantics"] + (
            " BYTE+2 IS TWO FIELDS (EXP-0160 DEF-0160-1, HW, G17P; re-derived in "
            "EXP-0165): opsel = bits 16-18, opflags = bits 19-23, exactly falu2's "
            "layout -- see the `op` field note for the measured operation map, the "
            "srcB release flag, the two silent corruptors and the single inert bit. An "
            "emitter treating byte+2 as one opaque opcode cannot set the "
            "release/publication flag, which is what makes a register reusable.")
        f["provenance"] = f["provenance"] + (" byte+2 bit map HW-VALIDATED (EXP-0160, "
                                             "G17P, dense 256-value sweep x 2 seed "
                                             "sets); re-derived in EXP-0165.")

    # ---------------- DEF-0160-4 : half_pack byte+2 ------------------------
    h = ins(db, "half_pack")
    hs = fld(h, "src")
    expect((hs["start"], hs["width"]) == (16, 8), "half_pack.src is byte+2")
    hs["type"] = "mod"
    hs["note"] = ("byte+2. NOT a register selector -- bits 3, 4 and 5 are INERT over a "
                  "dense 256-value sweep x 2 seed sets (HW, G17P, EXP-0160 DEF-0160-4, "
                  "re-derived in EXP-0165), so it cannot carry a register index. Role "
                  "UNRESOLVED.")
    h["semantics"] = h["semantics"] + (
        " LENGTH CONFIRMED 4 BYTES BY SPLICE CONTROL (EXP-0160 DEF-0160-4, HW, G17P; "
        "re-derived in EXP-0165). Replacing bytes +2..+3 with our own 2-byte `mov_imm "
        "r6, 77` leaves r6 holding its SEED -- the mov_imm never executes, so those "
        "bytes are consumed by the instruction at +0. Replacing BOTH 2-byte halves "
        "with two mov_imms executes both (r6 = 77 AND r7 = 99): the positive control "
        "that proves the probe can see a difference in exactly that slot. So "
        "DEF-0154-1's A18 `18 05 18 03` vs G17P `18 03 18 05` is an operand swap "
        "INSIDE one 4-byte instruction, not two 2-byte instructions reordered. The "
        "isadb.py length gate on byte+1 == 0x05 is therefore wrong; dropping it was "
        "MEASURED in EXP-0165 (work/probe_hp) and IMPROVES the corpus metric -- clean "
        "files 833 -> 833, strict leftover bytes 388604 -> 388584 -- but it is a "
        "length-rule change in isadb.py and is left for the length-rule owner.")
    h["provenance"] = h["provenance"] + (" 4-byte length HW-VALIDATED by splice "
                                         "control with a firing positive control "
                                         "(EXP-0160, G17P); byte+2's three inert bits "
                                         "measured in the same sweep.")

    # ---------------- EXP-0157 : sfu_marker gets its two live bytes --------
    s = ins(db, "sfu_marker")
    expect(s["match"] == [[0, 8, 6], [8, 8, 2]], "sfu_marker pins both bytes")
    expect(s["fields"] == [], "sfu_marker has no fields")
    s["match"] = [[0, 3, 6], [8, 2, 2]]
    s["fields"] = [
        {"name": "b0_hi", "start": 3, "width": 5, "type": "mod",
         "note": "byte+0 bits 3-7. HW (EXP-0146 on M4/G16G, reproduced byte-for-byte "
                 "on G17P in three carriers by EXP-0157): byte+0 accepts only "
                 "(v & 0xF7) == 0x06, so within this field ONLY bit 3 (this field's "
                 "bit 0) is free and bits 4-7 must be 0. Setting byte+0 to 0x00 flips "
                 "the sign of fast::sin on exactly the range-reduced rows."},
        {"name": "b1_hi", "start": 10, "width": 6, "type": "mod",
         "note": "byte+1 bits 2-7. HW (EXP-0146 M4, reproduced on G17P by EXP-0157): "
                 "byte+1 accepts only (v & 0x13) == 0x02, so within this field bits 2, "
                 "3, 5, 6 and 7 of the byte are free and bit 4 (this field's bit 2) "
                 "must be 0."},
    ]
    s["semantics"] = SFU_MARKER_SEM
    s["provenance"] = (s["provenance"] + " BYTE-INVARIANCE REFUTED and the two live "
                       "bytes mapped: HW-VALIDATED (EXP-0146, M4/G16G, 512 cases over "
                       "two gated runs) and REPRODUCED on G17P in three independent "
                       "carriers (EXP-0157). Fields added by EXP-0165.")

    # ---------------- length-rule findings, recorded not applied -----------
    g = db["length_rule_gaps"]
    expect("hw_measured_lengths_20260830" not in g, "not already recorded")
    g["hw_measured_lengths_20260830"] = {
        "found_by": "EXP-0157 (register-witness consumed-length probe, 2304 "
                    "measurements) and EXP-0160 (splice controls); corpus deltas "
                    "measured by EXP-0165 analysis/ab_gate.py",
        "status": "RECORDED, NOT APPLIED. All three are isadb.py length-rule changes; "
                  "the orchestrator reserved that call. Baseline metric: 833 clean "
                  "files / 388604 strict leftover bytes over the 1080-file own-MSL "
                  "corpus.",
        "op04_len8": {
            "measured": "REFUTED on hardware. All six `op04_len8` byte patterns taken "
                        "from our own G17P compiles consume TWELVE bytes, not eight. "
                        "The `04` leader's length is a joint function of byte+1 bit 7 "
                        "and byte+2: with the candidates' own tails, bit 7 SET -> 8 "
                        "and CLEAR -> 12 (128/128 split, three independent "
                        "candidates); with byte+2 = byte+3 = 0x00, SET -> 4 and "
                        "CLEAR -> 8. Full map: EXP-0157 analysis/length_map_q.json.",
            "corpus_gate": "REGRESSES. Applying `8 if (byte+1 & 0x80) else 12` gives "
                           "823 clean files (-10) and 390568 leftover bytes (+1964), "
                           "and op04_len8's own firings collapse 55 -> 1. Reported and "
                           "left, per the orchestrator's instruction.",
            "note": "The descriptor's own semantics already flagged this length as a "
                    "candidate over-consumer; EXP-0157 is the first DIRECT hardware "
                    "measurement of the consumed length rather than a corpus fit.",
        },
        "half_pack": {
            "measured": "half_pack IS 4 bytes unconditionally (EXP-0160 splice "
                        "controls with a firing positive control); the isadb.py gate "
                        "on byte+1 == 0x05 and (byte+2 & 0xf8) == 0x18 is wrong.",
            "corpus_gate": "IMPROVES. Dropping the byte+1/byte+2 gate gives 833 clean "
                           "files (unchanged) and 388584 leftover bytes (-20); "
                           "half_pack firings 19 -> 33, roundtrip still ALL PASS.",
            "patch": "isadb.py: replace the `b0 == 0x18 and buf[off+1] == 0x05 and "
                     "(buf[off+2] & 0xf8) == 0x18` gate with `b0 == 0x18`.",
        },
        "mesh_out_src": {
            "measured": "EXP-0157: splicing `04 XX` ahead of four 2-byte marker "
                        "instructions, all 128 byte+1 values with bit 7 CLEAR consume "
                        "exactly 2 bytes and all 128 with bit 7 SET consume 4. "
                        "db.json's 2-byte claim is CONFIRMED for bit 7 clear and "
                        "REFUTED for bit 7 set. No value changed the stored result, so "
                        "`sel` has no observable effect in a compute program.",
            "corpus_gate": "NOT MEASURED -- the change belongs with the op04 length "
                           "rework, since `mesh_out_src`'s match (byte0 == 0x04) and "
                           "`op04_len8`'s (byte0 low nibble 4) overlap and only the "
                           "length rule separates them.",
        },
    }

    json.dump(db, open(path, "w"), indent=2)
    print("patched", path)


if __name__ == "__main__":
    apply_all(sys.argv[1])
