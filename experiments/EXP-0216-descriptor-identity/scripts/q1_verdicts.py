#!/usr/bin/env python3
"""EXP-0216 — assemble the 26-row verdict table for Q1/Q3.

Every row records, separately:
  * `bits_moved`     which bits the sweep physically moved (Test G, mechanical);
  * `frozen_db`      the span the experiment's OWN frozen db.json gave that name;
  * `what_the_bits_are` the hardware role established from the committed
                     register dumps / oracles, with the evidence locator;
  * `verdict`        one of CURRENT-CONFIRMED / CURRENT-REFUTED / FROZEN-REFUTED
                     / UNDECIDABLE-NO-DETECTION-POWER / UNDECIDABLE-GEOMETRY;
  * `scope`          what the verdict does and does NOT license.

The verdict strings are authored here from the analyses in this directory; the
numbers beside them are re-read from those analysis files so the table cannot
drift from its evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import EXP, REPO, dump, span_of  # noqa

A = EXP / "analysis"
GEO = {(g["mnem"], g["field"], g["exp"]): g
       for g in json.loads((A / "q1_geometry.json").read_text())["geometry"]}

V = [
 # (row, exp, verdict, role, evidence)
 ("imad.srcB", "EXP-0154-g17p-emit-alu", "CURRENT-REFUTED",
  "byte 5 is a MULTIPLICAND register selector, reg = value>>2.  The destination "
  "equals SEED[reg]*10+1 on every in-domain case (10 = the seed of the register "
  "byte 6 selects); an addend would give 340+SEED[reg].  Host oracle "
  "M_mulmul 64/64, M_b5addend 0/64, M_b6addend 0/64.",
  "analysis/q1_arith_oracle.json (imad.srcB); "
  "experiments/EXP-0154-g17p-emit-alu/raw/g17p_20260829_run02/sweep.jsonl:12598",
  "db.json now calls byte 5 `srcC_lo`.  Byte 5 is not an addend, so that name is "
  "wrong at its current span.  EXP-0165's swap did not remove the wrong name, it "
  "moved it from byte 6 to byte 5."),

 ("imad.srcC_lo", "EXP-0154-g17p-emit-alu", "FROZEN-REFUTED",
  "byte 6 is the OTHER MULTIPLICAND, reg = value>>3, bit0 kills the product.  "
  "dest = SEED[b5>>2]*SEED[b6>>3] + 1 on 68/128 in-domain cases and the other 60 "
  "are the bit0-killed cases; M_b6addend 0/128.",
  "analysis/q1_arith_oracle.json (imad.srcC_lo); "
  "experiments/EXP-0154-g17p-emit-alu/raw/g17p_20260829_run02/sweep.jsonl:12854",
  "The frozen name `srcC_lo` at byte 6 is refuted.  Which multiplicand is A and "
  "which is B is NOT decidable here -- multiplication is commutative and this "
  "carrier has no non-commutative probe."),

 ("falu3.srcA", "EXP-0154-g17p-emit-alu", "CURRENT-CONFIRMED",
  "dest = A*B + C with A from byte1, B from byte3, C from byte5, reg = byte>>1 "
  "and bit0 = operand width.  The model is exact on every in-domain case of every "
  "arm (srcA 32/32, srcC 32/32, dst 13/13, dst_lo 13/14).  The frozen model "
  "(B from byte4) is out of domain on every record: byte4's baseline is 0x81, "
  "register 64.",
  "analysis/q1_arith_oracle.json (falu3.*); "
  "experiments/EXP-0154-g17p-emit-alu/raw/g17p_20260829_run02/sweep.jsonl:17886",
  "byte 3 IS an operand, so the committed verdict is not void -- but it is a "
  "verdict about the row db.json now calls `falu3.srcB`.  A vs B is undecidable "
  "(commutative multiply)."),

 ("falu3_ext.srcA", "EXP-0154-g17p-emit-alu", "FROZEN-REFUTED",
  "byte 3 selects a source register (release-on-read: value 3 -> r1, value 7 -> "
  "r3, value 5 -> r2), same law as falu3.  The value channel is BLIND here: "
  "k_sat_fma saturates and the destination is 1.0 on every case.",
  "experiments/EXP-0154-g17p-emit-alu/raw/g17p_20260829_run02/sweep.jsonl:17886",
  "Source-vs-not is decided; the operand SLOT is not, because the carrier "
  "saturates.  `carrier-undecidable` for the slot."),

 ("iminmax.srcA", "EXP-0154-g17p-emit-alu", "CURRENT-CONFIRMED",
  "byte 3 is a source register selector, reg = value>>1, release-on-read law "
  "56/56; min(SEED[b1>>1], SEED[b3>>1]) reproduces the destination on 32/32 "
  "in-domain cases.  The frozen model (B from byte5) scores 2/32.",
  "analysis/q1_roles.json; analysis/q1_arith_oracle.json (iminmax)",
  "db.json's `srcB` at byte 3 is confirmed as A SOURCE.  A vs B undecidable "
  "(min is commutative)."),

 ("iminmax.srcB", "EXP-0154-g17p-emit-alu", "FROZEN-REFUTED",
  "byte 5 is NOT a source register selector: over all 256 values no register "
  "other than the two baseline sources is ever released, and the destination "
  "never takes another seed.  Only values 0 and 8 keep the instruction correct.",
  "analysis/q1_roles.json (iminmax srcB, LIVE-NOT-SELECTOR, 4 distinct vectors "
  "over 256 cases)",
  "The frozen name `srcB` is refuted.  db.json's current `dst_full` is NOT "
  "confirmed -- nothing here shows byte 5 is destination-related."),

 ("iminmax.srcB", "EXP-0160-g17p-last-field", "FROZEN-REFUTED",
  "Independent repetition of the row above on a second experiment: identical "
  "counts (M_current 80/256, M_frozen 2/32, 4 distinct register vectors).",
  "analysis/q1_arith_oracle.json (EXP-0160 iminmax srcB)",
  "Same scope as the EXP-0154 row."),

 ("half_alu.srcA", "EXP-0169-g17p-rerecord", "CURRENT-CONFIRMED",
  "byte 3 is a source register selector, release-on-read law reg = value>>1, "
  "26/26; byte 1 is a source too by the same law, 26/26.",
  "analysis/q1_roles.json (half_alu srcA / dst arms)",
  "Confirms db.json's srcA=(8,8), srcB=(24,8) as SOURCES.  A vs B not separated "
  "by this carrier."),

 ("half_alu.srcB", "EXP-0169-g17p-rerecord", "FROZEN-REFUTED",
  "byte 4 is live (5 distinct register vectors over 256 values, incl. whole-"
  "program poison at v in {2,6,10,...}) but selects no register: no release map, "
  "no seed ever reaches the destination.",
  "analysis/q1_roles.json (half_alu srcB, LIVE-NOT-SELECTOR)",
  "Frozen `srcB` at byte 4 refuted; current `ctrl` not confirmed."),

 ("half_alu_ext8.dst", "EXP-0180-g17p-halfalu-rerecord", "CURRENT-CONFIRMED",
  "The destination is byte0's HIGH NIBBLE, not byte 1: in EXP-0180's own "
  "`__dst_nibble` arm the register whose index equals the nibble is the one that "
  "changes in 60 of 64 cases (C_HI; the written low half is the single constant "
  "7.05859375) and 56 of 64 (C_LO).  Byte 1 itself is inert or law-free in every "
  "arm of this carrier.",
  "analysis/q1_roles.json (half_alu_ext8 __dst_nibble)",
  "The repair (8,8)->(4,4) is confirmed for the NAME `dst`.  What byte 1 is "
  "remains undecided in this carrier (current db calls it `srcA`)."),

 ("half_alu_ext8.srcA", "EXP-0180-g17p-halfalu-rerecord",
  "UNDECIDABLE-NO-DETECTION-POWER",
  "Two of five arm/run slices produce ONE identical register vector across all "
  "136-256 values; the others move but follow no index law.  Gate B: the arm has "
  "no detection power for operand identity.",
  "analysis/q1_roles.json (half_alu_ext8 srcA)",
  "Neither the frozen nor the current name is decided by these records.  The "
  "sibling instruction half_alu_fma12 IS decided (next row) and the layout is "
  "shared, but that is INFERRED, not measured, for ext8."),

 ("half_alu_fma12.srcA", "EXP-0180-g17p-halfalu-rerecord", "FROZEN-REFUTED",
  "EXP-0203 committed a host oracle (a, b, c, dst) beside 51 220 cases.  With "
  "operand = (reg = byte>>1, half = byte&1) read out of the committed `pre` "
  "dump, a/b/c come from bytes 1/3/5 on 47 030 cases and from bytes 3/4/5 on "
  "ZERO.  oracle.dst == byte0>>4 on 51 096.",
  "analysis/q1_fma12_oracle.json; "
  "experiments/EXP-0203-g17p-half-oracle/raw/g17p_run21/sweep.jsonl:16",
  "srcA=(8,8), srcB=(24,8), srcC=(40,8), dst=(4,4) are confirmed as a SET.  The "
  "frozen srcA=(24,8) is refuted.  This is a second experiment and a second "
  "method relative to EXP-0180."),

 ("half_alu_fma12.ext", "EXP-0203-g17p-half-oracle", "PARTITIONED",
  "The declared span (32,64) is bytes 4..11; the current span (48,48) is bytes "
  "6..11.  EXP-0203 swept `ext` byte-wise, so the records partition exactly: "
  "byte4 6 630 and byte5 6 120 records now belong to `lensel`/`mods` and `srcC`; "
  "bytes 6..11 36 720 records are still `ext`.",
  "analysis/q1_partition.json",
  "Nothing is lost and nothing is misattributed once the records are split by "
  "byte index.  The 12 750 byte-4/5 records are a sweep of the fields EXP-0212 "
  "carved out, and byte 5 is srcC -- confirmed by the oracle row above."),

 ("fspecial.dst", "EXP-0161-g17p-carry-fspecial", "FROZEN-REFUTED",
  "(12,4) is INERT: all 16 values give one identical register vector.  The "
  "destination is byte 3 (next row), so the frozen name `dst` at (12,4) is "
  "refuted by elimination.",
  "analysis/q1_roles.json (fspecial dst, INERT-IN-CARRIER)",
  "Current name `src_ext` is neither confirmed nor refuted; "
  "`inert in the EXP-0161 rsqrt carrier; global role unknown`."),

 ("fspecial.src", "EXP-0161-g17p-carry-fspecial", "CURRENT-CONFIRMED",
  "byte 3 RELOCATES THE DESTINATION: index == value>>1, 26/26.  value 0/1 -> the "
  "result stays in r0; 2/3 -> r1; 4/5 -> r2; 6/7 -> r3 ... with the source "
  "register unchanged.",
  "analysis/q1_roles.json (fspecial src, DST-SELECTOR); "
  "experiments/EXP-0161-g17p-carry-fspecial/raw/g17p_20260829_run01/sweep.jsonl:6365",
  "db.json's `dst` at (24,8) is confirmed.  The frozen name `src` is refuted."),

 ("fspecial.src_ext", "EXP-0161-g17p-carry-fspecial", "CURRENT-CONFIRMED",
  "byte 5 SELECTS THE SOURCE: release-on-read index == value>>2, 56/56, and the "
  "result tracks rsqrt of the selected register's seed (v=4..7 -> rsqrt(9)=1/3; "
  "v=8,9 -> rsqrt(0.25)=2).",
  "analysis/q1_roles.json (fspecial src_ext, SRC-SELECTOR); "
  "experiments/EXP-0161-g17p-carry-fspecial/raw/g17p_20260829_run01/sweep.jsonl:7069",
  "db.json's `src` at (40,8) is confirmed.  The frozen name `src_ext` is refuted. "
  "Together with the two rows above, EXP-0165's three-way rotation of fspecial is "
  "CORRECT on two of its three legs and unfalsified on the third."),

 ("mov_zext16.src_reg", "EXP-0161-g17p-carry-fspecial", "CURRENT-CONFIRMED",
  "byte0's HIGH NIBBLE is the register the instruction both reads and writes.  "
  "For byte0 = 0xN3, register N receives zext16 of ITS OWN pre-value, verified "
  "against the committed `pre` dump for N = 0..10 (e.g. N=2: 0x0A2C51E7 -> "
  "0x000051E7; N=3: 0xA7D50B49 -> 0x00000B49); N >= 11 writes nothing.  The "
  "frozen span (8,7) is INERT: 128 values, one identical register vector, in TWO "
  "independent experiments.",
  "experiments/EXP-0161-g17p-carry-fspecial/raw/g17p_20260829_run01/sweep.jsonl:3371; "
  "analysis/q1_roles.json (mov_zext16 src_reg INERT, __raw_b0)",
  "Confirms EXP-0197 section 4.1 independently, from bytes and registers rather "
  "than from prose.  NOTE: the same nibble is also the DESTINATION, and db.json "
  "gives mov_zext16 no dst field -- recorded as a proposal, not an edit."),

 ("mov_zext16.src_flag", "EXP-0161-g17p-carry-fspecial", "UNDECIDABLE-GEOMETRY",
  "This is a WIDENING, not a narrowing: declared (15,1) is one bit inside the "
  "current (8,8).  The 14 committed records are a 2-point sample of a 256-value "
  "field.  Byte 1 is inert in this carrier (see the row above).",
  "analysis/q1_geometry.json (mov_zext16.src_flag)",
  "Evidence survives as a 2/256 partial sweep; no role is decided."),

 ("mov_zext16.extend", "EXP-0161-g17p-carry-fspecial", "UNDECIDABLE-GEOMETRY",
  "Narrowing (24,8) -> (27,5).  Of 1 792 records only 224 preserve the "
  "instruction's match; bits 24..26 are match bits, so the match bits and the "
  "field TILE the swept byte and exactly ONE encoding exists per sub-span value. "
  "A single-byte sweep cannot separate them.",
  "analysis/q1_subspan.json",
  "The narrowing is neither confirmed nor refuted.  All 32 match-preserving "
  "values of the 5-bit field WERE dispatched, so the liveness evidence stands at "
  "the new span."),

 ("reg_move_cb.form", "EXP-0169-g17p-rerecord", "UNDECIDABLE-GEOMETRY",
  "Narrowing (16,8) -> (20,4); 64 of 1 024 records preserve match; one encoding "
  "per sub-span value in both carriers.",
  "analysis/q1_subspan.json", "As above."),

 ("shift_amt_move.kind", "EXP-0154-g17p-emit-alu", "UNDECIDABLE-GEOMETRY",
  "Narrowing (16,8) -> (20,4); 32 of 512 records preserve match; one encoding "
  "per sub-span value.",
  "analysis/q1_subspan.json", "As above."),

 ("iter_at.grp", "EXP-0168-g17p-dst-resweep", "UNDECIDABLE-GEOMETRY",
  "Narrowing (0,8) -> (7,1); 14 of 71 records preserve match; 2 sub-span groups, "
  "one encoding each.",
  "analysis/q1_subspan.json", "As above."),

 ("cvt_f2h.b1", "EXP-0144-m4-emit-pack", "DESCRIPTOR-MATCH-OVERFIT",
  "1 280 of 1 280 records fail cvt_f2h's match and 1 280 of 1 280 satisfy "
  "cvt_f2h_dst's.  The ONLY failing constraint is byte0: its LOW nibble (the "
  "opcode group) is 1 on all 1 280; only the HIGH nibble differs, and that "
  "nibble is a destination register in every dst-parameterised sibling.",
  "analysis/q2_sibling.json; "
  "experiments/EXP-0144-m4-emit-pack/raw/m4_20260828_run03/sweep.jsonl:1855",
  "cvt_f2h.b1 and cvt_f2h_dst.srcfmt are the SAME bits (8,8); re-pointing cannot "
  "move an operand."),

 ("cvt_f2h.src", "EXP-0144-m4-emit-pack", "DESCRIPTOR-MATCH-OVERFIT",
  "Same byte0 story, but note the asymmetry: only 80 of these 1 280 records "
  "satisfy cvt_f2h_dst, because that descriptor additionally pins byte3's high "
  "nibble ((28,4)==8) and this arm sweeps byte 3 through all 256 values.",
  "analysis/q2_sibling.json",
  "cvt_f2h.src and cvt_f2h_dst.src are the same (24,8).  1 200 of the 1 280 "
  "cases lie outside cvt_f2h_dst's match, so a re-point would carry an "
  "out-of-descriptor majority with it."),

 ("cvt_f2h.b4", "EXP-0144-m4-emit-pack", "DESCRIPTOR-MATCH-OVERFIT",
  "1 280/1 280 fail cvt_f2h, 1 280/1 280 satisfy cvt_f2h_dst.",
  "analysis/q2_sibling.json",
  "cvt_f2h.b4 and cvt_f2h_dst.dhalf are the same (32,8)."),

 ("cvt_f2h.tail", "EXP-0144-m4-emit-pack", "DESCRIPTOR-MATCH-OVERFIT",
  "1 280/1 280 fail cvt_f2h, 1 280/1 280 satisfy cvt_f2h_dst.",
  "analysis/q2_sibling.json",
  "cvt_f2h.tail and cvt_f2h_dst.tail are the same (40,8)."),
]


if __name__ == "__main__":
    rows = []
    for row, exp, verdict, role, ev, scope in V:
        mnem, field = row.split(".", 1)
        g = GEO.get((mnem, field, exp), {})
        rows.append({
            "row": row, "exp": exp,
            "declared_span_in_the_records": list(g.get("declared_spans", {})),
            "current_span_in_db_json": span_of(mnem, field),
            "gateA_agree_at_declared": g.get("gateA_agree_at_declared"),
            "gateA_agree_at_current": g.get("gateA_agree_at_current"),
            "n_records": g.get("n_records_with_value_and_bytes"),
            "verdict": verdict,
            "what_the_bits_are": role,
            "evidence": ev,
            "scope": scope,
        })
    dump(rows, "q1_verdicts.json")
    tally = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print(json.dumps(tally, indent=1))
    for r in rows:
        print(f"{r['row']:24s} {r['exp'][:26]:26s} {r['verdict']}")
