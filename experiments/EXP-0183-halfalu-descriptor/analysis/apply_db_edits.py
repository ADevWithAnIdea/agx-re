#!/usr/bin/env python3
"""EXP-0183 -- apply the SURVIVING defects to a db.json.

Every edit below is keyed to a hypothesis in PRE_REGISTRATION.md that
analysis/rederive.py re-derived from committed raw. Nothing is applied on
EXP-0180's or EXP-0181's authority alone.

  python3 analysis/apply_db_edits.py <in_db.json> <out_db.json> [--only NAME,...]

Edit groups (--only selects a subset, for A/B isolation):
  half_match   relax the byte0 pin on the three native-half descriptors + add `dst`
  half_fields  the operand retype (byte+1/+3/+5) and the byte+7 withdrawals
  fma12_opsel  fold half_alu_fma12.opsel into `match` (one legal value)
  bf16_match   cvt_bf16 [32,8,1] -> [32,1,1]
  lengthdoc    length_rule.byte0_table['0x10'] documentation only (no decode effect)
"""
import json, sys

GROUPS = ["half_match", "half_fields", "fma12_opsel", "bf16_match", "lengthdoc"]

E183 = "EXP-0183"

# ---------------------------------------------------------------------------
HALF_SEM_COMMON = (
    " [CORRECTED 2026-08-30, EXP-0183 from EXP-0180's committed raw] "
    "**THE DESTINATION IS byte0's HIGH NIBBLE** (bits 4..7); the low nibble 0x0 is the "
    "family tag. The previous descriptor pinned the WHOLE of byte0 in `match`, so an "
    "emitter following it could only ever write r1, and the field it called `dst` "
    "(bits 8..15) is in fact a SOURCE half-register descriptor. Re-derived on G17P three "
    "independent ways, all cross-checked over EXP-0180's two gated runs (16,735 cases "
    "each, byte-identical): (1) the DSTNIB arm ran byte0 = n<<4 for n = 0..15 on two "
    "carriers -- the result lands in r[n]'s LOW 16 bits with r[n]'s HIGH 16 bits "
    "preserved for n = 0..14, and n = 15 is UNOBSERVABLE because the harness's own store "
    "index register is r15 (r15 is never non-zero in any of the 16,335 observed cases, so "
    "this is a carrier limit, not a hardware property -- the same limit EXP-0168 recorded "
    "for falu2.dst); (2) STRUCTURALLY, the seed program's fourteen SIX-BYTE half-adds are "
    "`[j<<4] [h_B] [(opflags<<3)|4] [h_A] [0x00] [0xC0]` and nothing but byte0 names "
    "register j -- the per-case identity `r_j.lo == fp16(h[byte+1] + h[byte+3])` holds in "
    "**228,690 checks per run with zero mismatches, in both runs**, for j = 0..13; "
    "(3) ARITHMETICALLY, the 8-byte fma anchor computes "
    "`r[byte0>>4].lo = fp16(h[byte+1] * h[byte+3] + h[byte+5])` on both carriers. "
    "Operand bytes are the ODD bytes (+1, +3, and +5 in the 8-byte form); the final byte "
    "of the instruction is the modifier byte. Half-register descriptor h = (reg<<1)|is_high. "
    "Same class as cvt_f2h_dst / bf_add_dst / n3_mov, which db.json already models this way, "
    "and identical in shape to the low-nibble-8 sibling `h_alu_hi`."
)

LEN_SEM = (
    " INSTRUCTION LENGTH, MEASURED (EXP-0180 LEN arm; re-derived independently by EXP-0183 "
    "from the same raw, 32 of 32 cells, ZERO ambiguous cells and ZERO cross-run "
    "disagreements) as a function of (opsel = byte+2 & 7, m = byte+4 & 3): "
    "opsel 0-3 and 7 -> 10/10/10/8; opsel 4 (hadd) -> 6/8/10/6; opsel 5 (hmul) -> 6/8/10/8; "
    "opsel 6 (hfma) -> 6/8/10/12. **BOUND: bytes +6.. carry the marker chain in every LEN "
    "case, so a length dependence on byte +6 or later is UNTESTED.** This measured table "
    "is NOT the rule the tokenizer implements: EXP-0182 measured that adopting it verbatim "
    "costs 17 clean corpus files and 3,220 leftover bytes, because the G17P measurement and "
    "the M4 corpus disagree exactly on the compact forms -- precisely where the bound above "
    "says the measurement is silent. `isadb.instr_length` therefore implements only the nine "
    "(opsel, m) cells where BOTH sources agree. Recorded here so the disagreement is visible "
    "rather than smoothed away."
)

# EXP-0180 field-by-field withdrawals, re-derived by EXP-0183 (moved counts recomputed
# from pre/post digests against the arm's own once-captured anchor).
NOTE_RSV6 = (
    "WITHDRAWAL (EXP-0180, re-derived EXP-0183). The committed claim \"byte+6 swept "
    "0x00..0xc0, every value kept the result -- fully INERT/reserved\" is REFUTED: on the "
    "fma instance rsv6 moves the observation on **252 of 256 values (C_HI) and 248 of 256 "
    "(C_LO)**, identically in both gated runs and on the lifted anchor. It is LIVE and its "
    "role is UNKNOWN. It reads inert only on the E8_ADD arm, whose base writes nothing at "
    "all (0 of 4 ladder steps and 0 of 3 falsifiers moved), so that arm has no detection "
    "power and its nulls are not evidence."
)
NOTE_B7HI = (
    "WITHDRAWAL (EXP-0180, re-derived EXP-0183). Formerly `op_valid_marker`, on the claim "
    "that \"every byte+7 value without bit7 set nulls the op\". REFUTED: byte+7 0x40 "
    "(bit 63 clear) and 0xc0 (bit 63 set) BOTH write the destination -- 0 of 2 values moved "
    "on two carriers, three arms and both runs. Bit 63 is INERT here. The op IS nullable "
    "from byte+7, but by **instruction bit 60** (= `b7_mid` bit 2 = byte+7 bit 4): all "
    "sixteen `b7_mid` values with bit 2 set leave the destination untouched and all sixteen "
    "without it write, 16/16 both ways, both carriers, both runs."
)
NOTE_MULSUP = (
    "WITHDRAWAL (EXP-0180, re-derived EXP-0183). Formerly `saturate`, enumerated as "
    "\"output-clamp, clamps to [0,1]\". REFUTED as a clamp, at value level: with the bit "
    "set the result becomes **exactly the third operand h[byte+5]** -- 2.84375 on C_HI "
    "(where the unmodified result is 7.0586) and 0.46875 on C_LO (where the unmodified "
    "result is 0.125). A clamp to [0,1] CANNOT change 0.125. The bit suppresses the "
    "multiply term of the fma, leaving the addend. BOUND: measured on the fma instance "
    "(opsel 6) only; its effect on hadd/hmul is untested."
)
NOTE_B4_EXT8 = (
    "RETYPED (EXP-0180, re-derived EXP-0183). Formerly `srcB_desc`, on the claim that "
    "byte+4 is the srcB operand descriptor with \"0x01 required\". Both halves are refuted: "
    "\"0x01 required\" is a LENGTH requirement, not an operand one -- byte+4's low two bits "
    "are the measured length selector, so at opsel 4 or 6 only the 64 values with "
    "(v & 3) == 1 keep the 8-byte framing (at opsel 5 both m=1 and m=3 give 8 bytes, i.e. "
    "128 values); and inside that subset the pre-registered same-length step (byte+4 += 4, a "
    "different half-register at the same length) does not move the observation on ANY arm. "
    "No operand role is detectable in bits 34..39. The cited byte+7 0xc0->0xc8 example "
    "belongs to a different field entirely (DEF-0180-6)."
)
NOTE_SRCC = (
    "RETYPED (EXP-0183, from EXP-0180's committed raw). Formerly `b5`, typed `mod` and "
    "described as \"largely inert\". It is the fma's THIRD OPERAND (the addend): the anchor "
    "identity `r[byte0>>4].lo = fp16(h[byte+1] * h[byte+3] + h[byte+5])` reproduces the "
    "observed result exactly on both carriers in both runs, and the anchor's own operand "
    "triple is recovered by brute force over all 32 half-registers. Corroborated "
    "independently: with instruction bit 57 set the result becomes exactly h[byte+5]. "
    "It moves the observation on 254 of 256 values."
)
NOTE_SRCA = (
    "RETYPED (EXP-0183). Formerly `dst`. This is a SOURCE half-register descriptor "
    "h = (reg<<1)|is_high, not the destination -- see the descriptor semantics. Its span is "
    "unchanged (bits 8..15), so evidence recorded against those bits still applies; only the "
    "name and role change. Named `srcA` to match the low-nibble-8 sibling `h_alu_hi`, whose "
    "byte+1 is already `srcA`."
)
NOTE_SRCB = (
    "RENAMED (EXP-0183). Formerly `srcA`; span unchanged (bits 8..15 took the name `srcA` "
    "because byte+1 is the first source, matching `h_alu_hi`). Evidence recorded against "
    "bits 24..31 still applies."
)
NOTE_CTRL = (
    "RETYPED (EXP-0183). Formerly `srcB`, on EXP-M4-14's claim that byte+4 is the second "
    "source of the 6-byte form. REFUTED from EXP-0180's raw: the seed program's own 6-byte "
    "hadds carry byte+4 = 0x00 = h0 = r0's LOW half, which is NON-ZERO in all 32,670 "
    "observed pre-vectors, yet the observed result is exactly fp16(h[byte+1] + h[byte+3]) in "
    "228,690 checks per run with zero mismatches. byte+4 does not enter the arithmetic. Its "
    "low two bits are the measured LENGTH selector."
)


def _f(name, start, width, typ, **kw):
    d = {"name": name, "start": start, "width": width, "type": typ}
    d.update(kw)
    return d


def edit(db, groups):
    by = {i["mnemonic"]: i for i in db["instructions"]}
    changed = []

    # ---------------------------------------------------------------- half family
    if "half_match" in groups:
        for m in ("half_alu", "half_alu_ext8", "half_alu_fma12"):
            d = by[m]
            assert d["match"] == [[0, 8, 16]], (m, d["match"])
            d["match"] = [[0, 4, 0]]
            changed.append("%s.match [[0,8,16]] -> [[0,4,0]]" % m)

    if "half_fields" in groups:
        # ---- half_alu (6 bytes)
        d = by["half_alu"]
        d["fields"] = [
            _f("dst", 4, 4, "reg",
               note="DEF-0180-1, HW-VALIDATED on G17P, re-derived by " + E183 +
                    ". The destination GPR (r0..r15). Directly exercised at 14 of 16 values "
                    "in EVERY one of EXP-0180's 33,470 gated cases (the seed program's own "
                    "six-byte half-adds) and at 15 of 16 by the DSTNIB arm on the 8-byte "
                    "sibling; value 15 is unobservable in that harness (r15 is its store "
                    "index register), a carrier limit, not a hardware property."),
            _f("srcA", 8, 8, "reg", note=NOTE_SRCA),
            _f("opsel", 16, 3, "opcode", enum={"4": "hadd", "5": "hmul"}),
            _f("opflags", 19, 5, "mod"),
            _f("srcB", 24, 8, "reg", note=NOTE_SRCB),
            _f("ctrl", 32, 8, "mod", note=NOTE_CTRL),
            _f("src_modifier", 40, 8, "mod"),
        ]
        d["semantics"] = (
            "d(half) = op(h[byte+1], h[byte+3])  ; NATIVE half-precision (fp16) float ALU, "
            "6-byte form. byte0 low nibble 0x0 is the family tag and byte0 HIGH nibble is the "
            "destination GPR. Operands are half-register descriptors h = (reg<<1)|is_high. "
            "byte+2 = op-select (low 3 bits: 4 = hadd, 5 = hmul) + opflags. byte+5 is the "
            "source/control modifier byte. A half2 (packed 2xfp16) op executes BOTH 16-bit "
            "lanes in ONE op, then a 0x18 pack assembles the 32-bit result; the HIGH-half "
            "sibling is `h_alu_hi` (byte0 low nibble 8)." + HALF_SEM_COMMON + LEN_SEM +
            " SUPERSEDED HERE: the EXP-M4-14 reading in which byte+3 was `srcA` and byte+4 "
            "`srcB` -- byte+4 is refuted as an operand (see the `ctrl` field note) and the "
            "two sources are byte+1 and byte+3."
        )
        d["provenance"] = (
            d["provenance"] +
            "  [SUPERSEDED IN PART 2026-08-30] EXP-0183 re-derived EXP-0180's DEF-0180-1 and "
            "DEF-0180-2 from that experiment's committed raw (raw/g17p_run02, raw/g17p_run03; "
            "PURE ANALYSIS, no new hardware run) and both survived. The destination moves to "
            "byte0's high nibble; byte+1 and byte+3 are the two sources; byte+4 is not an "
            "operand. EXP-M4-14, which supplied the superseded reading, has NO committed raw "
            "tree at all (EXP-0164), and EXP-0180 refuted six of its nine claims on hardware."
        )
        changed.append("half_alu.fields: +dst(4..7); dst->srcA, srcA->srcB, srcB->ctrl")

        # ---- half_alu_ext8 (8 bytes)
        d = by["half_alu_ext8"]
        d["fields"] = [
            _f("dst", 4, 4, "reg",
               note="DEF-0180-1, HW-VALIDATED on G17P, re-derived by " + E183 + ". "
                    "DSTNIB arm: byte0 = n<<4, two carriers, both gated runs, 16/16 values "
                    "identical across runs; n = 0..14 land in r[n]'s low half with the high "
                    "half preserved, n = 15 unobservable (harness store-index register)."),
            _f("srcA", 8, 8, "reg", note=NOTE_SRCA),
            _f("opsel", 16, 3, "opcode", enum={"4": "hadd", "5": "hmul", "6": "hfma"}),
            _f("opflags", 19, 5, "mod",
               note="EXACT FAULT WALL, measured (EXP-0180 LEN arm, 128 cases, zero "
                    "counterexamples; independently reproduced in the field sweeps): "
                    "opflags bit 4 (instruction bit 23) set together with opsel 4 or 5 "
                    "faults the command buffer unconditionally."),
            _f("srcB", 24, 8, "reg", note=NOTE_SRCB),
            _f("b4", 32, 8, "mod", note=NOTE_B4_EXT8),
            _f("srcC", 40, 8, "reg", note=NOTE_SRCC),
            _f("rsv6", 48, 8, "mod", note=NOTE_RSV6),
            _f("b7_lo", 56, 1, "mod"),
            _f("mul_suppress", 57, 1, "mod", note=NOTE_MULSUP),
            _f("b7_mid", 58, 5, "mod",
               note="LIVE, 28 of 32 values move the observation. **Bit 2 of this field "
                    "(instruction bit 60, byte+7 bit 4) NULLS THE WRITE**: all sixteen "
                    "values with bit 2 set leave the destination untouched and all sixteen "
                    "without it write, on two carriers and in both gated runs. This is the "
                    "op-nulling control that `op_valid_marker` was wrongly believed to be."),
            _f("b7_hi", 63, 1, "mod", note=NOTE_B7HI),
        ]
        d["semantics"] = (
            "8-byte EXTENDED native-half (fp16) float ALU, the length-polymorphic sibling of "
            "the 6-byte `half_alu`. At opsel 6 it is a genuine three-source fma: "
            "`r[byte0>>4].lo = fp16(h[byte+1] * h[byte+3] + h[byte+5])`, re-derived by "
            "EXP-0183 on both of EXP-0180's carriers in both gated runs (C_HI: 1.625 x "
            "2.59375 + 2.84375 = 7.0586 = 0x470f; C_LO: -0.0625 x 5.5 + 0.46875 = 0.125 = "
            "0x3000), with the anchor's operand triple recovered by brute force over all 32 "
            "half-registers. byte+4 is the length selector, NOT an operand; byte+6 is LIVE "
            "and unexplained; byte+7 is the modifier byte, in which bit 1 suppresses the "
            "multiply term and bit 4 nulls the write." + HALF_SEM_COMMON + LEN_SEM
        )
        d["provenance"] = (
            d["provenance"] +
            "  [SUPERSEDED IN PART 2026-08-30] EXP-0183 re-derived DEF-0180-1, DEF-0180-2, "
            "DEF-0180-5/6 and the three EXP-M4-14 semantic refutations from EXP-0180's "
            "committed raw (PURE ANALYSIS). All survived. Withdrawn from this descriptor: "
            "\"rsv6 fully INERT\" (it moves on 252/256), \"byte+7 bit7 is a required op-valid "
            "marker\" (bit 63 is inert; bit 60 nulls), \"byte+7 bit1 clamps to [0,1]\" (it "
            "yields the third operand, including on a sub-unit result a clamp cannot touch), "
            "and \"byte+4 0x01 required as an operand\" (it is the length selector)."
        )
        changed.append("half_alu_ext8.fields: +dst(4..7); dst->srcA, srcA->srcB, "
                       "srcB_desc->b4, b5->srcC, saturate->mul_suppress, "
                       "op_valid_marker->b7_hi")

        # ---- half_alu_fma12 (12 bytes)
        d = by["half_alu_fma12"]
        d["fields"] = [
            _f("dst", 4, 4, "reg",
               note="DEF-0180-1, HW-VALIDATED on G17P, re-derived by " + E183 + "."),
            _f("srcA", 8, 8, "reg", note=NOTE_SRCA),
            _f("opsel", 16, 3, "opcode", enum={"6": "hfma"},
               note="ONE LEGAL VALUE, DELIBERATELY NOT FOLDED INTO `match`. EXP-0180's "
                    "measured length map (re-derived by EXP-0183: 32 of 32 cells, zero "
                    "ambiguity) reaches 12 bytes at exactly one op-select, 6, so under that "
                    "rule this row is vacuous and the falu2_uni.uni_mode disposition "
                    "(EXP-0175) would apply. It is NOT folded because folding it MEASURABLY "
                    "REGRESSES the corpus: pinning [16,3,6] costs 6 clean files "
                    "(841 -> 835), adds 748 leftover bytes and drops half_alu_fma12 from 7 "
                    "corpus firings to 0. That is the same G17P-measurement-versus-M4-corpus "
                    "disagreement EXP-0182 measured for the length rule itself, and it sits "
                    "inside EXP-0180's own stated bound (a length dependence on byte +6 or "
                    "later is UNTESTED). The enum lists only the value the hardware was "
                    "measured to length at 12; whether to pin it is the db owner's call, "
                    "not a consequence of this measurement. EXP-0183 candidate tree "
                    "work/cand_final_plus_fold carries the folded variant and its numbers."),
            _f("opflags", 19, 5, "mod"),
            _f("srcB", 24, 8, "reg", note=NOTE_SRCB),
            _f("ext", 32, 64, "raw",
               note="NOT A FIELD (EXP-0180, re-derived EXP-0183). 64 bits wide, so its "
                    "encodable range is 2^64 and no sampled set can establish it. What its "
                    "first byte does IS measured: byte+4's low two bits are the length "
                    "selector, and this 12-byte form is reachable only at (opsel 6, m 3) -- "
                    "1 of 8 opsel values and 1 of 4 m values. EXP-0180 REFUTED its own "
                    "DEF-0180-3: half_alu_fma12 really is 12 bytes there, so it is not an "
                    "over-consumer at that encoding. The residue is that bits 34..95 are "
                    "unmodelled, which is why the descriptor keeps `emit_unsafe`."),
        ]
        d["semantics"] = (
            "12-byte fp16 fma form (byte0 low nibble 0x0). Reachable at exactly one "
            "(op-select, length-selector) pair: opsel 6 with byte+4 & 3 == 3, measured over "
            "4,096 LEN cases with zero ambiguous cells and re-derived by EXP-0183. "
            "fma(abs(a),b,c) compiles to this form. `ext` is NOT a field -- see its note. "
            "DO NOT EMIT until bits 34..95 are modelled." + HALF_SEM_COMMON + LEN_SEM +
            " WITHDRAWN: the earlier \"this fixed 12-byte length OVER-CONSUMES the following "
            "instruction's leader\" claim. EXP-0180 measured the length directly and "
            "withdrew it; at (opsel 6, m 3) twelve bytes is correct. The corpus instances "
            "that embed a real op-leader inside `ext` are instances at a DIFFERENT (opsel, m) "
            "whose true length is shorter, which is a tokenizer-side question, not evidence "
            "that this encoding over-consumes."
        )
        changed.append("half_alu_fma12.fields: +dst(4..7); dst->srcA, srcA->srcB; "
                       "opsel narrowed to 16..18")

    if "fma12_opsel" in groups:
        d = by["half_alu_fma12"]
        d["match"] = sorted(d["match"] + [[16, 3, 6]])
        d["fields"] = [f for f in d["fields"] if f["name"] != "opsel"]
        d.setdefault("match_notes", []).append({
            "name": "opsel", "start": 16, "width": 3, "type": "opcode", "value": 6,
            "enum": {"6": "hfma"},
            "note": "FOLDED INTO `match` (EXP-0183, from EXP-0180's measured length map, "
                    "re-derived here). Exactly ONE of the eight op-select values yields a "
                    "12-byte instruction, so there is no value for an emitter to choose and "
                    "an emitter-grade label on the row would be vacuous (DEF-0170-1). Same "
                    "disposition as falu2_uni.uni_mode (EXP-0175) and cvt_bf16.src/fmt. The "
                    "name, span and pinned value are preserved here."})
        changed.append("half_alu_fma12: opsel folded into match [16,3,6]")

    # ------------------------------------------------------------------- cvt_bf16
    if "bf16_match" in groups:
        d = by["cvt_bf16"]
        assert [32, 8, 1] in d["match"], d["match"]
        d["match"] = [m for m in d["match"] if m != [32, 8, 1]] + [[32, 1, 1]]
        d["match"].sort()
        d["fields"] = d["fields"] + [_f(
            "fmt", 32, 8, "mod",
            note="RE-SPANNED (EXP-0183, re-derived from EXP-0162's committed raw). This byte "
                 "was pinned to the single value 0x01 in `match`, and **0x01 is a value the "
                 "hardware REJECTS**: EXP-0162's dense 256-value byte+4 sweep on the "
                 "HW-validated cvt_bf16 carrier accepts 52 values, 0x01 is not among them "
                 "(`wrong_value`), and the anchor our own GPU executed correctly carries "
                 "0x05. Every one of the 52 accepted values has bit 0 set and none of the "
                 "204 rejected-with-bit-0-clear does, so bit 0 (instruction bit 32) is the "
                 "part that identifies the instruction and is all that stays in `match`. "
                 "Accepted set (EXP-0162, one gated run, majority-of-3 per case): "
                 "{5,13,33,37,41,45,49,53,57,61,65,69,73,77,81,85,89,93,97,101,105,109,113,"
                 "117,121,125,129,137,161,165,169,173,177,181,185,189,193,197,201,205,209,"
                 "213,217,221,225,229,233,237,241,245,249,253}.")]
        d["semantics"] = d["semantics"].replace(
            "byte+4 == 0x01 marks a bfloat operand.",
            "byte+4 BIT 0 marks a bfloat operand. [CORRECTED 2026-08-30, EXP-0183] The "
            "descriptor used to pin the whole of byte+4 to 0x01, which the hardware REJECTS "
            "-- the HW-validated anchor `01 01 14 81 05 02 40 00` carries byte+4 = 0x05 and "
            "did not decode as cvt_bf16 at all; it fell through to the least-specific "
            "`bf_alu8_var`. Only bit 0 is pinned now.")
        for mn in d.get("match_notes", []):
            if mn.get("name") == "fmt":
                mn["width"] = 1
                mn["note"] = ("RE-SPANNED (EXP-0183). Only bit 32 (byte+4 bit 0) remains "
                              "pinned; bits 33..39 are now the field `fmt`. The former "
                              "8-bit pin to 0x01 named a value the hardware rejects.")
        d["note"] = d.get("note", "") + (
            "  [EXP-0183] The `fmt` pin is narrowed from 8 bits to 1: EXP-0162's dense sweep "
            "accepts 52 byte+4 values, all with bit 0 set, and 0x01 itself is NOT accepted.")
        changed.append("cvt_bf16.match [32,8,1] -> [32,1,1]; +field fmt(32..39)")

    # -------------------------------------------------------------- length doc only
    if "lengthdoc" in groups:
        bt = db["length_rule"]["byte0_table"]
        old = bt.pop("0x10")
        bt["0x?0 (byte0 low nibble 0x0; high nibble = dst reg)"] = (
            "NATIVE-HALF (fp16) float ALU, sibling of 0x09 and of the low-nibble-8 "
            "`h_alu_hi`. MEASURED ON HARDWARE (EXP-0180 LEN arm, 4,096 cases over two gated "
            "runs; re-derived independently by EXP-0183 from the same raw -- 32 of 32 cells, "
            "ZERO cells with more than one observed length, ZERO cross-run disagreements). "
            "As a function of (opsel = byte+2 & 7, m = byte+4 & 3): "
            "opsel 0,1,2,3,7 -> 10/10/10/8 ; opsel 4 (hadd) -> 6/8/10/6 ; "
            "opsel 5 (hmul) -> 6/8/10/8 ; opsel 6 (hfma) -> 6/8/10/12. "
            "The previous entry here read %r, which is wrong in 25 of these 32 cells. "
            "BOUND: bytes +6.. carry the LEN arm's marker chain in every case, so a length "
            "dependence on byte +6 or later is UNTESTED. "
            "**THIS TABLE IS DOCUMENTATION, NOT THE IMPLEMENTED RULE.** `isadb.instr_length` "
            "is Python and is not driven by this entry. EXP-0182 measured that adopting the "
            "table above verbatim costs 17 clean corpus files and 3,220 leftover bytes (it "
            "kills half_compact4 8->0 and half_alu_fma12 7->0), because the G17P measurement "
            "and the M4 own-shader corpus genuinely disagree on the compact forms -- exactly "
            "where the bound above says the measurement is silent. The tokenizer therefore "
            "implements only the NINE (opsel, m) cells where both sources agree: opsel 4 or "
            "5 with m in {0,1,2}, and opsel 6 with m in {1,2,3}. Widening that is a "
            "deliberate decision for the db owner, not a consequence of this table. "
            "EXP-0033 / EXP-0180 / EXP-0182 / EXP-0183." % old)
        db["length_rule"]["note"] += (
            "  [2026-08-30, EXP-0183] The byte0 low-nibble-0 (native half) entry is now the "
            "hardware-MEASURED 32-cell table rather than a one-line guess, and it carries an "
            "explicit statement of where it disagrees with the corpus-anchored rule the "
            "tokenizer implements. Neither is silently preferred.")
        changed.append("length_rule.byte0_table: '0x10' -> measured 32-cell table (doc only)")

    return changed


def main():
    src, dst = sys.argv[1], sys.argv[2]
    groups = GROUPS
    for a in sys.argv[3:]:
        if a.startswith("--only"):
            groups = a.split("=", 1)[1].split(",") if "=" in a else sys.argv[sys.argv.index(a) + 1].split(",")
    db = json.load(open(src))
    changed = edit(db, groups)
    json.dump(db, open(dst, "w"), indent=1)
    print("groups:", ",".join(groups))
    for c in changed:
        print("  -", c)
    print("wrote", dst)


if __name__ == "__main__":
    main()
