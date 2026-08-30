#!/usr/bin/env python3
"""EXP-0183 -- build analysis/validation_updates.json for the orchestrator.

Covers EVERY row whose field moved, was renamed, was created, was deleted, or whose
`range` text this experiment refuted. Each `replace`/`create` row is in the schema
work/merge_verdicts.py consumes and carries `start`/`width`, so its DEF-0166-2 guard can
refuse it if db.json moves again.

  python3 analysis/make_validation_updates.py
"""
import hashlib, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
DB = os.path.join(REPO, "tools", "agx-isa", "db.json")
VAL = os.path.join(REPO, "tools", "agx-isa", "validation.json")
OLD_DB = os.path.join(EXP, "work", "base_live", "db.json")

E = ["EXP-0180", "EXP-0183"]
E69 = ["EXP-0169", "EXP-0183"]

G17P = "G17P"


def row(label, rng, evidence, note="", **kw):
    d = {"label": label, "range": rng, "target": G17P, "evidence": evidence, "note": note}
    d.update(kw)
    return d


DST_RANGE_EXT8 = (
    "0..15 dense: all 16 values of byte0's high nibble dispatched on two carriers in both "
    "gated runs, 16/16 per-value records identical across runs. 15 of 16 CONFIRMED (the "
    "result lands in r[n]'s low 16 bits with r[n]'s high 16 bits preserved); n=15 is "
    "UNDECIDABLE in this harness because r15 is its device_store index register, re-seeded "
    "to 0 before every store -- a carrier limit, not a hardware property, and the same one "
    "EXP-0168 recorded for falu2.dst. Control: r15 is never non-zero in any of the 16,335 "
    "observed cases, and r14 is non-zero in exactly ONE of 11,115 C_HI cases -- the DSTNIB "
    "n=14 case itself.")

DST_RANGE_HALF = (
    "0..15 dense on the family's shared byte0 (EXP-0180 DSTNIB arm, two carriers, both gated "
    "runs, 16/16 identical), and 14 of 16 exercised IN THIS SIX-BYTE FORM in every one of "
    "33,470 gated cases: the seed program's own half-adds are `[j<<4][h_B][opsel4][h_A][00]"
    "[C0]` and nothing but byte0 names register j, so the per-case identity "
    "r_j.lo == fp16(h[byte+1] + h[byte+3]) re-proves the destination each time -- 228,690 "
    "checks per run, ZERO mismatches, both runs, j = 0..13. Values 14 and 15 are unobservable "
    "in that harness (R_ZERO pad register and R_IDX store index).")

UPD = {
    # ---------------------------------------------------------------- half_alu
    "half_alu": {
        "replace": {
            "dst": row("hardware-run", DST_RANGE_HALF, E,
                       note="MOVED: bits 8..15 -> bits 4..7 (DEF-0180-1). The old row "
                            "described byte+1, which is a SOURCE; its evidence is carried "
                            "over to the new `srcA` row below, NOT to this one. "
                            "COUNT CAVEAT, stated so the owner can choose: the 16-of-16 "
                            "figure is from the DSTNIB arm, which varied this same byte0 on "
                            "an 8-byte instance of the family; only 14 of 16 were dispatched "
                            "in the 6-byte form itself. A conservative owner may prefer "
                            "14/14/16, which would set the THIN flag.",
                       values_dispatched=16, distinct_bytes=16, encodable_range=16,
                       start=4, width=4),
            "srcA": row("hardware-run",
                        "0..255 dense (all 256 values), 256 distinct encodings, 1 carrier, "
                        "two gated runs, 256/256 identical; 28 of 256 moved (carrier-limited "
                        "-- EXP-0169's seeds had zero low halves, so only the 28 odd/high "
                        "descriptors could reach a non-zero lane; DEF-0180-A). Additionally "
                        "exercised as a live source with a HOST-COMPUTED ORACLE at 14 "
                        "distinct values in the 6-byte form itself: r_j.lo == fp16(h[byte+1] "
                        "+ h[byte+3]) held in 228,690 per-case checks per run with zero "
                        "mismatches, in both of EXP-0180's runs.",
                        ["EXP-0169", "EXP-0180", "EXP-0183"],
                        note="RENAMED + RE-ROLED, span unchanged (bits 8..15). This is the "
                             "row formerly filed as `half_alu.dst`; byte+1 is a SOURCE "
                             "half-register descriptor h=(reg<<1)|is_high, not the "
                             "destination. Its `untested` label was a DEFERRAL ('another "
                             "experiment owns this field's verdict -> EXP-0168'), and "
                             "EXP-0168's committed field_verdicts.json contains no such row, "
                             "so the ruling was never made. Re-derived from EXP-0169's raw "
                             "by EXP-0183.",
                        values_dispatched=256, distinct_bytes=256, encodable_range=256,
                        start=8, width=8),
            "srcB": row("hardware-run",
                        "0..255 dense (all 256 values), 256 distinct encodings, 1 carrier",
                        E69,
                        note="RENAMED, span unchanged (bits 24..31). This is the row "
                             "formerly filed as `half_alu.srcA`; the name `srcA` moved to "
                             "byte+1 to match the low-nibble-8 sibling `h_alu_hi`. Evidence "
                             "and label are EXP-0169's, unchanged.",
                        values_dispatched=256, distinct_bytes=256, encodable_range=256,
                        start=24, width=8),
            "src_modifier": row("hardware-run",
                                "0..255 dense (all 256 values), 256 distinct encodings, "
                                "1 carrier", ["EXP-0169"],
                                note="unchanged span; start/width added so merge_verdicts' "
                                     "DEF-0166-2 span guard can see this row.",
                                values_dispatched=256, distinct_bytes=256,
                                encodable_range=256, start=40, width=8),
        },
        "create": {
            "ctrl": row("hardware-run",
                        "0..255 dense (all 256 values), 256 distinct encodings, 1 carrier",
                        E69,
                        note="RENAMED FROM `srcB`, span unchanged (bits 32..39). The label "
                             "and counts are EXP-0169's. The NAME changed because the "
                             "operand role is REFUTED: EXP-0180's seed instructions carry "
                             "byte+4 = 0x00 = h0 = r0's LOW half, which is non-zero in all "
                             "32,670 observed pre-vectors, and the observed result is "
                             "exactly fp16(h[byte+1] + h[byte+3]) in 228,690 checks per run "
                             "with zero mismatches -- byte+4 does not enter the arithmetic. "
                             "Its low two bits are the measured LENGTH selector.",
                        values_dispatched=256, distinct_bytes=256, encodable_range=256,
                        start=32, width=8),
        },
        "delete": [],
    },
    # ----------------------------------------------------------- half_alu_ext8
    "half_alu_ext8": {
        "replace": {
            "dst": row("hardware-run", DST_RANGE_EXT8, E,
                       note="MOVED: bits 8..15 -> bits 4..7 (DEF-0180-1). The old `dst` "
                            "row's evidence describes byte+1 and is carried to `srcA`.",
                       values_dispatched=16, distinct_bytes=16, encodable_range=16,
                       start=4, width=4),
            "srcA": row("hardware-run",
                        "256 of 256 encodable values after gate_identity (100.0%), 256 "
                        "distinct encodings, 2 ladder-passing carriers, both gated runs; "
                        "254 of 256 moved. Additionally identified as an OPERAND by a "
                        "host-computed oracle: r[byte0>>4].lo == fp16(h[byte+1] * h[byte+3] "
                        "+ h[byte+5]) on both carriers in both runs.",
                        E,
                        note="RENAMED + RE-ROLED, span unchanged (bits 8..15). Formerly "
                             "`half_alu_ext8.dst`; byte+1 is a SOURCE, not the destination.",
                        values_dispatched=256, distinct_bytes=256, encodable_range=256,
                        start=8, width=8),
            "opsel": row("isolated-byte-diff",
                         "3 of 8 values keep the 8-byte framing (opsel 4 hadd / 5 hmul / "
                         "6 hfma); the other five length the instruction to 10 or 8 bytes "
                         "at this byte+4 and therefore encode a DIFFERENT instruction. "
                         "8 of 8 dispatched, 7 of 8 moved, 2 carriers, both gated runs, "
                         "identical.", E,
                         note="ENCODABLE RANGE CORRECTED from 8 to 3 (DEF-0180-2, "
                              "re-derived EXP-0183 over the measured 32-cell length map).",
                         values_dispatched=8, distinct_bytes=8, encodable_range=3,
                         start=16, width=3),
            "opflags": row("hardware-run",
                           "32 of 32 dispatched, 30 moved, 2 carriers, both gated runs, "
                           "identical. EXACT FAULT WALL: opflags bit 4 (instruction bit 23) "
                           "set together with opsel 4 or 5 faults the command buffer "
                           "unconditionally -- 128 LEN-arm cases, zero counterexamples, "
                           "reproduced independently in the field sweeps.", E,
                           note="range text extended with the measured fault wall.",
                           values_dispatched=32, distinct_bytes=32, encodable_range=32,
                           start=19, width=5),
            "rsv6": row("hardware-run",
                        "256 of 256 dispatched, 2 carriers, both gated runs, identical. "
                        "LIVE: moves the observation on 252 of 256 values (C_HI) and 248 of "
                        "256 (C_LO), and on the lifted anchor.", E,
                        note="RANGE TEXT WITHDRAWN AND REPLACED. The committed text -- "
                             "'byte+6 swept 0x00..0xc0, every value kept the result, fully "
                             "INERT/reserved' (EXP-M4-14, which has no committed raw tree at "
                             "all) -- is REFUTED. Its role is UNKNOWN; it reads inert only "
                             "on the E8_ADD arm, whose base writes nothing at all and which "
                             "therefore has no detection power.",
                        values_dispatched=256, distinct_bytes=256, encodable_range=256,
                        start=48, width=8),
            "b7_lo": row("hardware-run",
                         "2 of 2 dispatched, 1 moved, 2 carriers, both gated runs, "
                         "identical. Role UNKNOWN.", E, note="",
                         values_dispatched=2, distinct_bytes=2, encodable_range=2,
                         start=56, width=1),
            "b7_mid": row("hardware-run",
                          "32 of 32 dispatched, 28 moved, 2 carriers, both gated runs, "
                          "identical. **Bit 2 of this field (instruction bit 60, byte+7 bit "
                          "4) NULLS THE WRITE**: all sixteen values with bit 2 set leave the "
                          "destination untouched and all sixteen without it write -- 16/16 "
                          "both ways, both carriers, both runs.", E,
                          note="RANGE TEXT EXTENDED with the op-nulling rule. This is the "
                               "control that `op_valid_marker` (bit 63) was wrongly believed "
                               "to be.",
                          values_dispatched=32, distinct_bytes=32, encodable_range=32,
                          start=58, width=5),
        },
        "create": {
            "srcB": row("hardware-run",
                        "256 of 256 encodable values after gate_identity (100.0%), 256 "
                        "distinct encodings, 2 ladder-passing carriers; 254 of 256 moved.",
                        E,
                        note="RENAMED FROM `srcA`, span unchanged (bits 24..31). Label and "
                             "counts are EXP-0180's, unchanged; only the name moved, because "
                             "byte+1 took the name `srcA` to match `h_alu_hi`.",
                        values_dispatched=256, distinct_bytes=256, encodable_range=256,
                        start=24, width=8),
            "b4": row("isolated-byte-diff",
                      "256 of 256 dispatched, 2 carriers, both gated runs, identical. "
                      "ENCODABLE RANGE 64, not 256: byte+4's low two bits are the measured "
                      "length selector, so at this descriptor's op-selects 4 and 6 only the "
                      "64 values with (v & 3) == 1 keep the 8-byte framing (at op-select 5, "
                      "128 values do -- both m=1 and m=3 give 8 bytes). Inside that subset "
                      "the pre-registered same-length step (byte+4 += 4) does NOT move the "
                      "observation on any arm, so no operand role is detectable in bits "
                      "34..39.", E,
                      note="RENAMED FROM `srcB_desc`, span unchanged (bits 32..39), and its "
                           "RANGE TEXT WITHDRAWN. The committed text -- '0x01 required in "
                           "the add+saturate instance; carries the fma srcA-negate (byte+7 "
                           "0xc0 -> 0xc8)' -- is refuted twice over: '0x01 required' is a "
                           "LENGTH requirement, and byte+7 is a different field entirely "
                           "(DEF-0180-6, citation defect).",
                      values_dispatched=256, distinct_bytes=256, encodable_range=64,
                      start=32, width=8),
            "srcC": row("hardware-run",
                        "256 of 256 dispatched, 254 moved, 2 carriers, both gated runs, "
                        "identical. Identified as the fma's THIRD OPERAND (the addend) by a "
                        "host-computed oracle: r[byte0>>4].lo == fp16(h[byte+1] * h[byte+3] "
                        "+ h[byte+5]) reproduces the observed result exactly on both "
                        "carriers, with the anchor's operand triple recovered by brute force "
                        "over all 32 half-registers. Corroborated independently: with "
                        "instruction bit 57 set the result becomes exactly h[byte+5].", E,
                        note="RENAMED FROM `b5`, span unchanged (bits 40..47), and RETYPED "
                             "mod -> reg. The committed text 'largely inert (bits3/4 null in "
                             "this instance)' is withdrawn.",
                        values_dispatched=256, distinct_bytes=256, encodable_range=256,
                        start=40, width=8),
            "mul_suppress": row("hardware-run",
                                "2 of 2 dispatched, 1 moved, 2 carriers, both gated runs, "
                                "identical. Setting the bit makes the result EXACTLY the "
                                "third operand h[byte+5]: 2.84375 on C_HI (unmodified "
                                "result 7.0586) and 0.46875 on C_LO (unmodified result "
                                "0.125). BOUND: measured on the fma instance (opsel 6) "
                                "only.", E,
                                note="RENAMED FROM `saturate`, span unchanged (bit 57), and "
                                     "its ENUM DELETED. The committed enum -- '1 = "
                                     "output-clamp/saturate ON (clamps to [0,1])' -- is "
                                     "REFUTED at value level: a clamp to [0,1] cannot change "
                                     "0.125, and this bit changes it to 0.46875. The bit "
                                     "suppresses the multiply term of the fma.",
                                values_dispatched=2, distinct_bytes=2, encodable_range=2,
                                start=57, width=1),
            "b7_hi": row("hardware-run",
                         "2 of 2 dispatched, 0 moved -- INERT on two carriers, three arms "
                         "and both gated runs. byte+7 0x40 (bit clear) and 0xc0 (bit set) "
                         "both write the destination.", E,
                         note="RENAMED FROM `op_valid_marker`, span unchanged (bit 63), and "
                              "its ENUM DELETED. The committed claim -- 'every byte+7 value "
                              "without bit7 set nulls the op; required op-valid marker' -- "
                              "is REFUTED. The op IS nullable from byte+7, but by "
                              "instruction bit 60 (b7_mid bit 2), not bit 63.",
                         values_dispatched=2, distinct_bytes=2, encodable_range=2,
                         start=63, width=1),
        },
        "delete": ["srcB_desc", "b5", "saturate", "op_valid_marker"],
    },
    # ---------------------------------------------------------- half_alu_fma12
    "half_alu_fma12": {
        "replace": {
            "dst": row("hardware-run", DST_RANGE_EXT8, E,
                       note="MOVED: bits 8..15 -> bits 4..7 (DEF-0180-1). byte0 is shared "
                            "across the whole low-nibble-0 family and the DSTNIB arm varied "
                            "exactly these bits.",
                       values_dispatched=16, distinct_bytes=16, encodable_range=16,
                       start=4, width=4),
            "srcA": row("hardware-run",
                        "256 of 256 encodable values after gate_identity (100.0%), 256 "
                        "distinct encodings, 2 ladder-passing carriers; 254 of 256 moved.",
                        E,
                        note="RENAMED + RE-ROLED, span unchanged (bits 8..15). Formerly "
                             "`half_alu_fma12.dst`.",
                        values_dispatched=256, distinct_bytes=256, encodable_range=256,
                        start=8, width=8),
            "opsel": row("isolated-byte-diff",
                         "8 of 8 dispatched, 7 moved, 2 carriers, both gated runs, "
                         "identical. ENCODABLE RANGE 1: exactly one op-select value (6, "
                         "hfma) yields a 12-byte instruction under the measured length map, "
                         "at byte+4 & 3 == 3.", E,
                         note="ENCODABLE RANGE CORRECTED from 8 to 1. NOT folded into "
                              "`match` even though one legal value normally means it should "
                              "be (falu2_uni.uni_mode, EXP-0175): folding [16,3,6] "
                              "MEASURABLY REGRESSES the corpus -- 841 -> 835 clean files, "
                              "+748 leftover bytes, half_alu_fma12 firings 7 -> 0. That is "
                              "the same G17P-measurement-versus-M4-corpus disagreement "
                              "EXP-0182 measured for the length rule, and it sits inside "
                              "EXP-0180's own stated bound. The folded variant is committed "
                              "as EXP-0183 work/cand_final_plus_fold; the decision is the "
                              "db owner's.",
                         values_dispatched=8, distinct_bytes=8, encodable_range=1,
                         start=16, width=3),
            "ext": row("untested",
                       "1856 of 18446744073709551616 encodable values after gate_identity "
                       "(0.0%), 2041 distinct encodings, 2 ladder-passing carriers. NOT A "
                       "FIELD: 64 bits wide, so no sampled set can establish it.", E,
                       note="RANGE TEXT CORRECTED. What its first byte does is MEASURED: "
                            "byte+4's low two bits are the length selector and this 12-byte "
                            "form is reachable only at (opsel 6, m 3), re-derived by "
                            "EXP-0183 over 32 of 32 cells with zero ambiguity. EXP-0180 "
                            "REFUTED ITS OWN DEF-0180-3: half_alu_fma12 really is 12 bytes "
                            "there, so the earlier 'this descriptor OVER-CONSUMES the "
                            "following instruction's leader' claim is WITHDRAWN. The "
                            "residue is that bits 34..95 are unmodelled, which is why the "
                            "descriptor keeps `emit_unsafe`.",
                       values_dispatched=2048, distinct_bytes=2041,
                       encodable_range=18446744073709551616, start=32, width=64),
        },
        "create": {
            "srcB": row("hardware-run",
                        "256 of 256 encodable values after gate_identity (100.0%), 256 "
                        "distinct encodings, 2 ladder-passing carriers; 254 of 256 moved.",
                        E,
                        note="RENAMED FROM `srcA`, span unchanged (bits 24..31).",
                        values_dispatched=256, distinct_bytes=256, encodable_range=256,
                        start=24, width=8),
        },
        "delete": [],
    },
    # ----------------------------------------------------------------- cvt_bf16
    "cvt_bf16": {
        "replace": {},
        "create": {
            "fmt": row("isolated-byte-diff",
                       "0..255 dense (all 256 values), one gated run, majority-of-3 per "
                       "case; 52 values accepted (`ok`). EVERY accepted value has bit 0 set "
                       "and none of the bit-0-clear values is accepted, which is why bit 32 "
                       "is all that remains pinned in `match`. Encodable range 128 (bit 32 "
                       "pinned).", ["EXP-0162", "EXP-0183"],
                       note="CREATED by EXP-0183 when the 8-bit `match` pin [32,8,1] was "
                            "narrowed to [32,1,1]. The old pin demanded byte+4 == 0x01, and "
                            "**0x01 is a value the hardware REJECTS** (`wrong_value` in "
                            "EXP-0162's dense sweep) -- so the HW-validated anchor "
                            "`01 01 14 81 05 02 40 00`, which our own GPU executed "
                            "correctly, did not decode as cvt_bf16 at all; it fell through "
                            "to the least-specific `bf_alu8_var`. Single gated run, hence "
                            "`isolated-byte-diff` rather than `hardware-run`.",
                       values_dispatched=256, distinct_bytes=256, encodable_range=128,
                       start=32, width=8),
        },
        "delete": [],
    },
    # ------------------------- the two `dst` rows EXP-0169 deferred and nobody ruled
    "falu2_uni": {
        "replace": {
            "dst": row("hardware-run",
                       "0..15 dense (all 16 values), 16 distinct encodings, 1 carrier "
                       "(C3_uni), two gated runs, 16/16 per-value records IDENTICAL across "
                       "runs; 15 of 16 moved. Outcomes identical in both runs: "
                       "1 ok / 1 silent_zero / 14 wrong_value.", E69,
                       note="RULING SUPPLIED. The row read `untested` only because EXP-0169 "
                            "deferred it by coordinator directive ('`dst` -> EXP-0168'), and "
                            "EXP-0168's committed field_verdicts.json contains NO "
                            "falu2_uni.dst row -- the ruling was never made, and it is one "
                            "of the 22 one-field-away blockers. Re-derived by EXP-0183 from "
                            "EXP-0169's raw sweep.jsonl directly, not from its analysis. "
                            "EXP-0169's ladder and falsifier both passed on this arm. "
                            "CAVEAT: one carrier only, and the `__falsifier_byte0` step "
                            "(byte0 -> 0x00) changes the opcode nibble as well as the field, "
                            "so it is a weak falsifier here -- as it was for the half family "
                            "(DEF-0180-B).",
                       values_dispatched=16, distinct_bytes=16, encodable_range=16,
                       start=4, width=4),
        },
        "create": {}, "delete": [],
    },
    "reg_move_cb": {
        "replace": {
            "dst": row("hardware-run",
                       "0..15 dense (all 16 values), 16 distinct encodings, TWO carriers "
                       "(C1_alu and C3_uni, which differ in the kernel buffer signature -- "
                       "the dimension EXP-0087 showed this instruction's read-back depends "
                       "on), two gated runs, 16/16 identical in all four; 14 of 16 moved on "
                       "each carrier.", E69,
                       note="RULING SUPPLIED, same reason as falu2_uni.dst: deferred to "
                            "EXP-0168, which never filed a row. Re-derived by EXP-0183 from "
                            "EXP-0169's raw.",
                       values_dispatched=16, distinct_bytes=16, encodable_range=16,
                       start=4, width=4),
            "form": row("hardware-run",
                        "0..15 dense (all 16 values of the free high nibble; the encoded "
                        "byte is (form << 4) | 0x0b), 2 carriers x 2 gated runs, identical "
                        "in all four: form 0..3 (0x0b/0x1b/0x2b/0x3b) `ok`, form 4..15 "
                        "`wrong_value`.", ["EXP-0169", "EXP-0181", "EXP-0183"],
                        note="RE-SPANNED by EXP-0181 (bits 16..23 -> 20..23) and RE-DERIVED "
                             "from EXP-0169's raw by EXP-0183. The old row's counts (256 "
                             "dispatched / 256 distinct / encodable 256) counted 240 values "
                             "that encode a DIFFERENT instruction, because this descriptor's "
                             "own match pins byte+2's low nibble to 0xb. Honest counts are "
                             "16/16/16. The corpus emits only form 1, 2 and 3.",
                        values_dispatched=16, distinct_bytes=16, encodable_range=16,
                        start=20, width=4),
        },
        "create": {}, "delete": [],
    },
    "iter_at": {
        "replace": {
            "grp": row("isolated-byte-diff",
                       "0..1 dense (both legal values of the narrowed field; byte0 0x2f and "
                       "0xaf), three gated runs (rclean07/08/09), two carriers, identical in "
                       "all three: grp=1 (0xaf) is `ok` on both carriers; grp=0 (0x2f) is "
                       "`wrong_value` on r_i8 (1 sample) and `ok` on r_i8s (4 samples).",
                       ["EXP-0168", "EXP-0181", "EXP-0183"],
                       note="RE-SPANNED by EXP-0181 (bits 0..7 -> bit 7) and RE-DERIVED from "
                            "EXP-0168's raw by EXP-0183. EXP-0168 filed `untested` on a "
                            "'5 of 256' sweep; against the field's REAL encodable range of "
                            "2 the same raw is a DENSE 2-of-2 sweep reproducible in three "
                            "runs. NOT recommended for `hardware-run`: r_i8s's own baseline "
                            "record says 'baseline vs HOST oracle: MISMATCH', so only one of "
                            "the two carriers has a valid oracle, and EXP-0168's ladder "
                            "clause (`iter_at.loc`) was not met. The two out-of-descriptor "
                            "byte0 values dispatched (0x00, 0x01) HUNG the device on both "
                            "carriers in all three runs -- a hardware fact about the 254 "
                            "illegal byte0 values, not about this field.",
                       values_dispatched=2, distinct_bytes=2, encodable_range=2,
                       start=7, width=1),
        },
        "create": {}, "delete": [],
    },
    # NOT re-derived by EXP-0183 -- carried through from EXP-0181 so it is not lost.
    "shift_amt_move": {
        "replace": {
            "kind": row("hardware-run",
                        "0..15 dense (all 16 values of the free high nibble; the encoded "
                        "byte is (kind << 4) | 0x0c), both targets, 2 gated runs each. G17P "
                        "(EXP-0154 k_rot_var): `ok` at kind 1 and 3, `wrong_value` at every "
                        "EVEN kind, `silent_zero` at every other ODD kind. M4 (EXP-0146 "
                        "run01/run02): `ok` at kind 0,1,2,3 and `silent_zero` at 4..15.",
                        ["EXP-0146", "EXP-0154", "EXP-0181"],
                        note="**NOT RE-DERIVED BY EXP-0183** -- carried through verbatim "
                             "from EXP-0181's analysis/orphaned_validation_rows.json so the "
                             "re-span is not lost, and flagged as such. Its span moved "
                             "(16..23 -> 20..23) and the CURRENT row carries no start/width, "
                             "so merge_verdicts' span guard CANNOT protect it: its recorded "
                             "'ok at {0x14, 0x1c, 0x34, 0x3c}' mixes two value spaces (0x14 "
                             "and 0x34 are not legal under this descriptor's match at all). "
                             "Target should be G16G+G17P, and G17P's accept set is a strict "
                             "SUBSET of M4's -- worth stating rather than merging.",
                        values_dispatched=16, distinct_bytes=16, encodable_range=16,
                        start=20, width=4),
        },
        "create": {}, "delete": [],
    },
}


def main():
    db = json.load(open(DB))
    dbf = {i["mnemonic"]: {f["name"]: (f["start"], f["width"])
                           for f in i.get("fields", [])} for i in db["instructions"]}
    val = json.load(open(VAL))
    old = json.load(open(OLD_DB))
    oldf = {i["mnemonic"]: {f["name"]: (f["start"], f["width"])
                            for f in i.get("fields", [])} for i in old["instructions"]}

    problems = []
    for m, spec in UPD.items():
        for kind in ("replace", "create"):
            for f, r in spec[kind].items():
                if f not in dbf.get(m, {}):
                    problems.append("%s.%s is not a field of db.json" % (m, f))
                    continue
                if (r["start"], r["width"]) != dbf[m][f]:
                    problems.append("%s.%s row says start=%s width=%s but db.json has %s"
                                    % (m, f, r["start"], r["width"], dbf[m][f]))
                if kind == "create" and f in val["instructions"].get(m, {}):
                    problems.append("%s.%s marked `create` but validation.json already "
                                    "has it" % (m, f))
                if kind == "replace" and f not in val["instructions"].get(m, {}):
                    problems.append("%s.%s marked `replace` but validation.json has no "
                                    "such row" % (m, f))
        for f in spec["delete"]:
            if f in dbf.get(m, {}):
                problems.append("%s.%s marked for deletion but db.json still has it" % (m, f))
            if f not in val["instructions"].get(m, {}):
                problems.append("%s.%s marked for deletion but validation.json has no "
                                "such row" % (m, f))

    # every db.json field that has no validation row, and every validation row with no field
    missing, stale = [], []
    for i in db["instructions"]:
        m = i["mnemonic"]
        for f in i.get("fields", []):
            if f["name"] not in val["instructions"].get(m, {}):
                missing.append("%s.%s" % (m, f["name"]))
    for m, e in val["instructions"].items():
        for f in e:
            if f == "_instruction":
                continue
            if f not in dbf.get(m, {}):
                stale.append("%s.%s" % (m, f))
    covered = set()
    for m, spec in UPD.items():
        covered |= {"%s.%s" % (m, f) for f in spec["create"]}
        covered |= {"%s.%s" % (m, f) for f in spec["delete"]}

    # rows whose NAME survives but whose SPAN moved -- the silent-merge hazard
    hazard = []
    for m in dbf:
        for f, span in dbf[m].items():
            if f in oldf.get(m, {}) and oldf[m][f] != span:
                hazard.append({"key": "%s.%s" % (m, f), "old_span": list(oldf[m][f]),
                               "new_span": list(span),
                               "current_row_start_width": [
                                   val["instructions"].get(m, {}).get(f, {}).get("start"),
                                   val["instructions"].get(m, {}).get(f, {}).get("width")]})

    doc = {
        "_meta": {
            "experiment": "EXP-0183-halfalu-descriptor",
            "for": "the orchestrator, who owns tools/agx-isa/validation.json",
            "db_sha256_before": hashlib.sha256(open(OLD_DB, "rb").read()).hexdigest(),
            "db_sha256_after": hashlib.sha256(open(DB, "rb").read()).hexdigest(),
            "schema": "per mnemonic: `replace` (row exists, take this one), `create` (row "
                      "does not exist yet), `delete` (row must be removed -- merge_verdicts "
                      "does NOT delete, so these are by hand). Every row carries start/width "
                      "so merge_verdicts' DEF-0166-2 span guard can check it.",
            "READ_THIS_FIRST": hazard and (
                "SILENT-MERGE HAZARD. %d field NAMES survive at a DIFFERENT SPAN. "
                "validate_labels.py cannot see this -- it only checks that the name exists -- "
                "so if these `replace` rows are not applied, validation.json will keep "
                "describing the wrong bits under a name that still resolves. This is exactly "
                "DEF-0166-2 (EXP-0161's carry_gen rename). Apply the whole file or none of "
                "it." % len(hazard)) or "no span-reuse hazard",
            "self_check": {"problems": problems,
                           "db_fields_with_no_validation_row": missing,
                           "db_fields_with_no_row_not_covered_here":
                               sorted(set(missing) - covered),
                           "validation_rows_with_no_db_field": stale,
                           "validation_rows_with_no_db_field_not_covered_here":
                               sorted(set(stale) - covered)},
        },
        "span_reuse_hazard": hazard,
        "updates": UPD,
    }
    out = os.path.join(HERE, "validation_updates.json")
    json.dump(doc, open(out, "w"), indent=1)
    print("wrote", out)
    print("problems:", len(problems))
    for p in problems:
        print("  -", p)
    print("db fields with no row, not covered here:",
          doc["_meta"]["self_check"]["db_fields_with_no_row_not_covered_here"])
    print("validation rows with no db field, not covered here:",
          doc["_meta"]["self_check"]["validation_rows_with_no_db_field_not_covered_here"])
    print("span-reuse hazard rows:", [h["key"] for h in hazard])


main()
