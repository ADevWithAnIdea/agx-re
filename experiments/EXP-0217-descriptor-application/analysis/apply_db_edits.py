#!/usr/bin/env python3
"""EXP-0217 -- apply EXP-0216's descriptor proposals to tools/agx-isa/db.json.

Usage:  apply_db_edits.py <in.json> <out.json> [--only GROUP,GROUP,...]

Groups
------
APPLIED (prose / field metadata only; tokenization-neutral by construction --
`note`, `semantics` and `type` are not read by isadb.decode_one):

  p1_imad          imad byte+5 role, the absent `srcA`, A-vs-B undecidable
  p2_cvt_f2h       cvt_f2h match over-fit, with the exact counts
  p3_bf_alu        bf_alu match over-fit, with the exact counts
  p4_bf_alias      the eight accepted byte+2 bfloat-add encodings, bounded
  p5_zext_second   mov_zext16 byte+1 inertness re-derived in a 2nd experiment

MEASURE-ONLY (match-bit candidates; each one is a TOKENIZATION change and is
built into an isolated variant tree by mkvariant.sh, never applied to the live
tree by this experiment):

  m1_cvt_f2h_match   cvt_f2h  match [[0,8,17]] -> [[0,4,1]] + dst (4,4)
  m2_bf_alu_match    bf_alu   match [[0,8,17],[8,8,2]] -> [[0,4,1]]
  m3_bf_dst_match    bf_add_dst [16,8,28] -> [16,3,4]+[22,2,0]
                     bf_mul_dst [16,8,29] -> [16,3,5]+[22,2,0]

CLEAN-ROOM: reads and writes only this repository's own committed artifacts.
"""
import json
import sys

TAG = "[EXP-0217]"

APPLIED = ("p1_imad", "p2_cvt_f2h", "p3_bf_alu", "p4_bf_alias", "p5_zext_second")
MEASURE = ("m1_cvt_f2h_match", "m2_bf_alu_match", "m3_bf_dst_match")


# --------------------------------------------------------------------- helpers
def instr(db, mnem):
    for d in db["instructions"]:
        if d["mnemonic"] == mnem:
            return d
    raise KeyError(mnem)


def field(db, mnem, name):
    for f in instr(db, mnem)["fields"]:
        if f["name"] == name:
            return f
    raise KeyError("%s.%s" % (mnem, name))


def append_note(obj, key, text):
    old = obj.get(key, "")
    obj[key] = (old + "  " if old else "") + text


def replace_once(obj, key, old, new):
    s = obj[key]
    if old not in s:
        raise AssertionError("expected substring not found in %r: %r" % (key, old[:60]))
    if s.count(old) != 1:
        raise AssertionError("substring is not unique in %r" % key)
    obj[key] = s.replace(old, new)


# ----------------------------------------------------------- P1  imad operands
IMAD_B5 = (
    TAG + " ROLE RESOLVED, and the previous sentence was doubly wrong. Re-derived "
    "from EXP-0154's OWN COMMITTED RAW by EXP-0216 (desk re-analysis, no new "
    "dispatch; G17P records): byte+5 IS a MULTIPLICAND REGISTER SELECTOR, "
    "reg = value >> 2. In k_imad's lifted block with SEED_I = {r0:10, r1:21, "
    "r2:34, r3:47, ...}, byte+5 = 0..3 -> r0 = 101, 4..7 -> 211, 8..11 -> 341 "
    "(the anchor), 12..15 -> 471, i.e. exactly SEED[value>>2] * 10 + 1, with the "
    "named register RELEASED TO ZERO on read. The host oracle "
    "`dest = SEED[b5>>2] * SEED[b6>>3] + 1` scores 64/64 in-domain on this byte; "
    "BOTH addend models score 0/64 (an addend at byte+5 would have given "
    "340 + SEED[reg] = 350/361/374/387, and the observation is 101/211/341/471). "
    "It was NOT `never swept`: EXP-0154 swept it dense 0..255 (512 records), "
    "which validation.json's own `range` for this row already stated. "
    "PACKING WARNING: the packing here is reg = v >> 2, NOT the project-standard "
    "(reg<<1)|size and NOT byte+6's reg = v >> 3. "
    "NAME: `srcC_lo` is REFUTED and is retained ONLY so this field's "
    "validation.json evidence row survives -- the same disposition db.json "
    "already applies to iminmax `dst_full` and mov_zext16 `src_flag`. It is a "
    "multiplicand selector, not the low half of an addend. WHICH multiplicand "
    "is A and which is B is UNDECIDABLE from this evidence: multiplication is "
    "commutative and EXP-0154's carrier has no non-commutative probe, so no "
    "srcA/srcB assignment may be read into byte+5 vs byte+6."
)

IMAD_B6 = (
    TAG + " Byte+6 is the OTHER multiplicand; both bytes select multiplicands and "
    "`imad` has NO `srcA` field at all. EXP-0216 (desk re-analysis of EXP-0154's "
    "committed G17P raw): `dest = SEED[b5>>2] * SEED[b6>>3] + 1` fits 68 of 128 "
    "in-domain cases here and the other 60 are exactly the bit0-killed cases; "
    "the byte+6-addend model scores 0/128. Worked points: byte+6 = 8 -> "
    "r0 = 715 = 34*21 + 1 (r1 AND r2 both released), byte+6 = 16 -> "
    "r0 = 1157 = 34*34 + 1. The letter `B` in this name is POSITIONAL AND "
    "ARBITRARY: A-vs-B is undecidable under a commutative operation, and no "
    "field named `srcA` exists to pair with it."
)

IMAD_SEM = (
    TAG + " OPERAND MODEL, THIRD CORRECTION (EXP-0216, desk re-analysis of "
    "EXP-0154's committed G17P raw; NO new dispatch). **BOTH byte+5 and byte+6 "
    "are multiplicand register selectors, and this descriptor has no field "
    "named `srcA`** -- so the semantics line `d = m * (srcA * srcB) + A` above "
    "names an operand the field table does not contain. byte+5: reg = v >> 2 "
    "(host oracle 64/64 in-domain, both addend models 0/64). byte+6: reg = v >> 3 "
    "(68/128 in-domain, the other 60 bit0-killed, addend model 0/128). "
    "**EXP-0165's byte+5<->byte+6 swap therefore fixed nothing: it moved the "
    "wrong name `srcC_lo` from byte+6 to byte+5 rather than removing it.** "
    "WHICH multiplicand is A and which is B is UNDECIDABLE from this carrier -- "
    "multiply commutes and EXP-0154 has no non-commutative probe -- so neither "
    "byte is named `srcA` here and the `B` in `srcB` carries no ordering claim. "
    "WHERE THE ADDEND ACTUALLY LIVES IS STILL OPEN, and byte+7/byte+8 are the "
    "two bytes that move it: byte+7 shifts the destination by {0, 1, 256, 16256, "
    "46038, 49045} above an UNCHANGED product of 340 (none of them a GPR seed), "
    "and byte+8 gates the addend between 1 (12 of 256 values, all with low "
    "nibble 0) and 0 (240 of 256; 4 values give a non-integer result). "
    "SUCCESSOR NEEDED for (a) A-vs-B via a non-commutative op or a "
    "differing-width probe and (b) the addend's real location. "
    "PROPOSED-AND-REFUSED HERE: renaming byte+5 to a multiplicand name. EXP-0216 "
    "proposes it; EXP-0217 refuses it, because any name placed opposite `srcB` "
    "re-asserts the A/B ordering the same experiment calls undecidable, and "
    "because a rename carries this row's `hardware-run` label onto a new name "
    "(the DEF-0166-2 / tex_write.rsv10 hazard). The correction is in the field "
    "notes instead."
)


def p1_imad(db):
    f5 = field(db, "imad", "srcC_lo")
    replace_once(f5, "note",
                 "byte+5. ROLE UNRESOLVED -- never swept. HISTORICAL NAME:",
                 "byte+5. HISTORICAL NAME:")
    append_note(f5, "note", IMAD_B5)
    # byte+5 is a register selector, not a modifier. `type` is documentation
    # metadata only (isadb.decode_one never reads it); no name, span, match or
    # label moves.
    assert f5["type"] == "mod", f5["type"]
    f5["type"] = "reg"
    append_note(field(db, "imad", "srcB"), "note", IMAD_B6)
    append_note(instr(db, "imad"), "semantics", IMAD_SEM)


# ------------------------------------------------------- P2  cvt_f2h over-fit
CVT_SEM = (
    TAG + " MATCH OVER-FIT, MEASURED (EXP-0216, from EXP-0144's committed "
    "M4/G16G raw -- **G16G-direct, NOT promoted to G17P**). This descriptor "
    "spends all eight bits of byte0 on `match`, and **6 550 of the 6 555 "
    "committed encodings keyed to it FAIL that match**. The ONLY failing "
    "constraint is byte0, and its LOW nibble -- the opcode group -- holds on "
    "6 515 of the 6 555; the dominant observed byte0 is 0x01 (6 440 records), "
    "i.e. the same convert with dst = r0. The high nibble is a DESTINATION "
    "REGISTER in every dst-parameterised sibling in this database "
    "(cvt_f2h_dst, cvt_bf16, bf_add_dst, bf_fma_dst all pin only [0,4,1]), so "
    "this is the DEF-0171-1 dst-nibble over-fit: **the descriptor is pinned to "
    "destination register r1.** EXP-0144's own byte0 sweep demonstrates it "
    "rather than inferring it: the carrier `c_f2h` anchor 010114810402 is "
    "`ok` with word0 = 15872 (0x3E00, the packed half), 110114810402 is "
    "`wrong_value` (the half is no longer in that slot), a10114810402 is "
    "`wrong_value` with the half MOVED to word2, and ff0114810402 is a silent "
    "zero. 5 315 of the 6 555 satisfy `cvt_f2h_dst` instead. "
    "NOT REPAIRED HERE, and why: narrowing this match to [[0,4,1]] and adding "
    "`dst` (4,4) makes cvt_f2h a 4-match-bit near-duplicate of the 8-match-bit "
    "cvt_f2h_dst, i.e. a catch-all for the whole length-6 low-nibble-1 group. "
    "EXP-0217 built and measured that variant against the 1 080-file own-MSL "
    "corpus and REFUSED it as a measured regression -- see "
    "experiments/EXP-0217-descriptor-application/RESULTS.md and work/var_m1. "
    "The four field rows b1/src/b4/tail need no move regardless: their spans "
    "are byte-for-byte cvt_f2h_dst's srcfmt/src/dhalf/tail. One row is NOT "
    "freely re-pointable even so -- `cvt_f2h.src` sweeps byte+3 and "
    "cvt_f2h_dst pins (28,4) == 8, so 1 200 of its 1 280 records fall OUTSIDE "
    "the sibling's match."
)


def p2_cvt_f2h(db):
    append_note(instr(db, "cvt_f2h"), "semantics", CVT_SEM)


# -------------------------------------------------------- P3  bf_alu over-fit
BF_ALU_SEM = (
    TAG + " THE MATCH OVER-FIT ABOVE IS NOW COUNTED (EXP-0216, from EXP-0171's "
    "committed G17P raw). Of the **13 144** committed 8-byte encodings keyed to "
    "`bf_alu`, **ZERO satisfy this descriptor's match.** Both constraints fail, "
    "and they fail differently: bits[8:+8] want 2 got 0 on **all 13 144** "
    "(G17P emits byte+1 == 0x00, so the byte-1 constant is one this target "
    "never produces), and bits[0:+8] want 17 got 49 on **12 626** (byte0 = "
    "0x31 = dst r3, group 1 -- the dst-nibble over-fit, DEF-0171-1). The "
    "dst-parameterised siblings claim the same bytes correctly: 7 972 satisfy "
    "bf_add_dst and 2 652 satisfy bf_mul_dst. "
    "NO FIELD ROW MOVES, and none needs to: per SWEPT BYTE the three "
    "descriptors assign IDENTICAL spans -- byte+3 is `srcA` (24,8) in all "
    "three, byte+4 is `srcB` (32,8) in all three, bytes +5..+7 are "
    "`tail` (40,24) in all three. (The contrary impression came from summing "
    "field counts across bytes 3..7 at once.) If this descriptor is ever "
    "widened or retired, the edit is to byte 0 and byte 1 ONLY. EXP-0217 built "
    "and measured the byte-0/byte-1 widening (match -> [[0,4,1]]) against the "
    "own-MSL corpus and did not take it; see "
    "experiments/EXP-0217-descriptor-application/RESULTS.md and work/var_m2."
)


def p3_bf_alu(db):
    append_note(instr(db, "bf_alu"), "semantics", BF_ALU_SEM)


# --------------------------------- P4  the eight accepted bfloat byte+2 values
BF_ALIAS = (
    TAG + " EIGHT byte+2 ENCODINGS OF THIS ADD ARE HARDWARE-ACCEPTED, and this "
    "descriptor's match admits only one of them. EXP-0171 swept byte+2 through "
    "all 256 values in its NAT bfloat-add carrier on G17P; **0x04, 0x0c, 0x14, "
    "0x1c, 0x24, 0x2c, 0x34 and 0x3c all return `ok` with BIT-IDENTICAL output "
    "words** (first four words 1083195520, 1091584016, 1061176011, 1101021608) "
    "-- exactly the set (byte+2 & 0xc7) == 0x04. 0x1d gives a different "
    "COHERENT result (the multiply); 0x44/0x5c/0x7c (bit 6 or 7 set) give a "
    "silent zero; 0x1f and 0xff fault. Evidence: "
    "experiments/EXP-0171-g17p-ilogic-srca/raw/g17p_20260830_run01/sweep.jsonl"
    ":25540 (0x04) vs :25564 (0x1c); counted in EXP-0216 "
    "analysis/q2_lengthrule.json. "
    "BOUNDED WORDING (RE_EXPERIMENT_PROCESS_CORRECTIONS section 7): bits 3-5 of "
    "byte+2 are **accepted-inert aliases of the bfloat add IN THE EXP-0171 NAT "
    "CARRIER; global role unknown**. One carrier is not the three structurally "
    "different carriers section 7 requires for a general accepted-inert rule. "
    "TOKENIZER STATE AS OF EXP-0217: isadb._n1_len's bfloat gate was widened to "
    "(byte+2 & 0xc7) on 2026-08-30, so all eight now receive a length of 8 "
    "(they had none before -- seven raised `unknown instruction length "
    "(byte0=0x31)`). They do NOT reach this descriptor: with byte+2 pinned to "
    "the single value 0x1c here, the seven aliases fall through to the "
    "least-specific `bf_alu8_var`. Widening this match to [16,3,4]+[22,2,0] "
    "would capture them; EXP-0217 built and measured that variant and did NOT "
    "take it -- one carrier cannot license a general aliasing rule, and the "
    "change REASSIGNS tokens rather than adding them. See "
    "experiments/EXP-0217-descriptor-application/RESULTS.md and work/var_m3. "
    "CONTEXT WARNING, verified by EXP-0217 from committed bytes: **0x14 is in "
    "this alias set AND is the byte+2 of the HW-validated fp32->fp16 CONVERT "
    "anchor `010114810402`** (EXP-0144, outcome `ok`, M4/G16G). So the eight "
    "values are NOT globally `the bfloat add`: the same byte+2 carries a "
    "different operation in the single-source-convert sub-group, which the "
    "length rule separates by byte+3`s HIGH NIBBLE, not by byte+2. Bits 3-5 of "
    "byte+2 are therefore demonstrably CONTEXT-DEPENDENT, and that -- not the "
    "corpus metric -- is the strongest single reason this match was left alone. "
    "A further bound on the alias evidence itself: EXP-0171 held byte+1 == 0x00 "
    "throughout its byte+2 sweep, and NONE of the 37 own-MSL corpus tokens the "
    "widened match would have re-claimed carries byte+1 == 0x00 (they carry "
    "0x03..0x09, 0x80..0x8a, 0xa1, 0xb1, 0xc1). The alias set is established at "
    "ONE byte+1 value only."
)

BF_ALIAS_MUL = (
    TAG + " The add sibling's byte+2 alias set is recorded on `bf_add_dst`. The "
    "corresponding question for THIS descriptor -- whether (byte+2 & 0xc7) == "
    "0x05 is likewise an accepted alias set for the multiply -- is UNTESTED: "
    "EXP-0171's byte+2 sweep observed 0x1d as the single coherent multiply "
    "point and did not establish an alias family for it. Do not assume the add "
    "result carries over."
)


def p4_bf_alias(db):
    append_note(instr(db, "bf_add_dst"), "semantics", BF_ALIAS)
    append_note(instr(db, "bf_mul_dst"), "semantics", BF_ALIAS_MUL)


# ------------------------------------------- P5  mov_zext16 byte+1, 2nd source
ZEXT_SECOND = (
    TAG + " SECOND EXPERIMENT, INDEPENDENTLY RE-DERIVED: EXP-0216 re-decoded "
    "the committed register dumps of EXP-0154 AND EXP-0161 at this span and "
    "found ONE IDENTICAL 16-register vector across all 128 values of bits "
    "8..14 in BOTH experiments -- so the inertness recorded above is not a "
    "single-experiment result. (The destination claim of this instruction was "
    "already correct in this descriptor and needed no change: byte0's high "
    "nibble is both the source and the destination, and EXP-0216 re-confirmed "
    "it against the committed `pre` dump for N = 0..10.)"
)


def p5_zext_second(db):
    append_note(field(db, "mov_zext16", "src_flag"), "note", ZEXT_SECOND)


# ============================ MEASURE-ONLY match candidates ==================
def m1_cvt_f2h_match(db):
    d = instr(db, "cvt_f2h")
    assert d["match"] == [[0, 8, 17]], d["match"]
    d["match"] = [[0, 4, 1]]
    d["fields"].insert(0, {"name": "dst", "start": 4, "width": 4, "type": "reg"})


def m2_bf_alu_match(db):
    d = instr(db, "bf_alu")
    assert d["match"] == [[0, 8, 17], [8, 8, 2]], d["match"]
    d["match"] = [[0, 4, 1]]


def m3_bf_dst_match(db):
    a = instr(db, "bf_add_dst")
    assert a["match"] == [[0, 4, 1], [16, 8, 28]], a["match"]
    a["match"] = [[0, 4, 1], [16, 3, 4], [22, 2, 0]]
    m = instr(db, "bf_mul_dst")
    assert m["match"] == [[0, 4, 1], [16, 8, 29]], m["match"]
    m["match"] = [[0, 4, 1], [16, 3, 5], [22, 2, 0]]


GROUPS = {
    "p1_imad": p1_imad,
    "p2_cvt_f2h": p2_cvt_f2h,
    "p3_bf_alu": p3_bf_alu,
    "p4_bf_alias": p4_bf_alias,
    "p5_zext_second": p5_zext_second,
    "m1_cvt_f2h_match": m1_cvt_f2h_match,
    "m2_bf_alu_match": m2_bf_alu_match,
    "m3_bf_dst_match": m3_bf_dst_match,
}


def main():
    src, dst = sys.argv[1], sys.argv[2]
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].split(",")
    groups = only if only is not None else list(APPLIED)
    db = json.load(open(src))
    for g in groups:
        GROUPS[g](db)
        print("applied group:", g)
    json.dump(db, open(dst, "w"), indent=1)
    print("wrote", dst)


if __name__ == "__main__":
    main()
