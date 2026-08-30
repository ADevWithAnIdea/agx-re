#!/usr/bin/env python3
"""EXP-0174 -> analysis/field_verdicts.json (FIELD-SWEEP-PROTOCOL section 5).

Flat "<mnemonic>.<field>" keys, the eight labels from
docs/evidence-classification.md and nothing else. Every number is read from
analysis/gate.json, which is itself recomputed from the committed raw by
analysis/analyze.py. `raw/prefreeze/**` contributes to NO verdict.

  python3 analysis/analyze.py --runs g17p_20260830_run01,g17p_20260830_run02
  python3 analysis/verdicts.py
"""
import json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
G = json.load(open(EXP / "analysis" / "gate.json"))
M = json.load(open(EXP / "analysis" / "maps.json"))
C = json.load(open(EXP / "analysis" / "grid_census.json"))

EV = ["EXP-0174"]
TGT = "G17P"


def row(field, label, rng, semantics, note="", extra=None):
    g = G.get(field, {})
    d = {"label": label, "range": rng, "target": TGT, "evidence": EV,
         "semantics": semantics, "note": note,
         "values_dispatched": g.get("values_dispatched"),
         "distinct_bytes": g.get("distinct_bytes"),
         "encodable_range": g.get("encodable_range"),
         "start": g.get("start"), "width": g.get("width"),
         "cross_run_agreement_pct": g.get("cross_run_agreement_pct"),
         "moved": g.get("moved"), "disagreements": g.get("disagreements"),
         "n_carriers": g.get("n_carriers"), "carriers": g.get("carriers"),
         "outcomes": g.get("outcomes"),
         "gate_agreement_pass": g.get("gate_agreement_pass"),
         "gate_movement_pass": g.get("gate_movement_pass")}
    if extra:
        d.update(extra)
    return d


MOVE_FORM = ("byte+2 & 0x03 == 1 and byte+2 & 0xC0 == 0 (16 of 256 values), "
             "byte+3 & 0x1E == 0 (16 of 256 values)")

V = {}

V["n3_mov.dst"] = row(
    "n3_mov.dst", "hardware-run",
    "0..15 dense (all 16 values), both register plans, at the move form; "
    "additionally exercised as the destination of all 240 generated 32-bit "
    "copies, which is what covers dst == 5 (undecidable in A/dstmap because "
    "that arm's source IS r5)",
    "byte0 bits 4..7 = the destination GPR. r0..r15 all confirmed WRITTEN on "
    "hardware against a host-computed 16-register prediction.",
    note=("CORRECTS EXP-0168, which reported 'a write whose 4-bit destination "
          "nibble is 15 is discarded, and the slot reads 0'. That experiment's "
          "read-back path used r15 as its device_store index register and "
          "emitted mov_imm(15, 0) immediately before EVERY store, including the "
          "one whose data_reg was 15, so r15 was zeroed one instruction before "
          "it was read and could not read anything else. Here, in the register "
          "plan whose index register is r7, r15 both holds its mov_imm seed "
          "(121) and is written correctly by dst = 15. "
          "The blind slot of each plan is excluded explicitly and is covered by "
          "the other plan."))

V["n3_mov.srcA_reg"] = row(
    "n3_mov.srcA_reg", "hardware-run",
    "byte+1 dense 0..255 (all 256 values) x 2 register plans; covers source "
    "registers 0..127 and both source halves, and spans two aliasing bands",
    "MEASURED: byte+1 = 2*S + hs. S = byte+1 bits 1..7 is the SOURCE REGISTER "
    "and aliases with period 64 (byte+1 = 2k and byte+1 = 128 + 2k select the "
    "same register: 256 of 256 pairs identical, both plans, both runs). "
    "hs = byte+1 bit 0 selects which 16-bit HALF of the source is read "
    "(0 = low, 1 = high).",
    note=("DB DEFECT DEF-0174-1. db.json declares srcA_reg = bits 0..6 of "
          "byte+1 (instruction bits 8..14) and srcA_uni = bit 7. Measured, the "
          "register field is byte+1 bits 1..7 and bit 0 is the source-half "
          "select -- the modelled field is shifted by one bit, so an emitter "
          "following db.json writes the register number into the wrong bits and "
          "gets r[S/2] with a half-select it did not intend. Source registers "
          "16..63 read as 0 in this carrier (192 of 192 cases, both plans, both "
          "runs); that is a property of a carrier that allocates 16 GPRs, not a "
          "property of the field."))

V["n3_mov.srcA_uni"] = row(
    "n3_mov.srcA_uni", "hardware-run",
    "both values, at all 128 byte+1 low-bit combinations, in both plans "
    "(the dense byte+1 sweep covers this bit exhaustively)",
    "byte+1 bit 7 (instruction bit 15) is SOURCE-REGISTER BIT 6, not a "
    "uniform-file selector. Because the register file aliases with period 64, "
    "setting it selects r[S+64], which reads identically to r[S]: all 128 "
    "(byte+1, byte+1+128) pairs produced byte-identical 16-register dumps in "
    "both plans and both runs.",
    note=("DB DEFECT DEF-0174-1 (same defect). db.json's enum "
          "{0: 'gpr', 1: 'uniform/hi'} is wrong on the 'uniform' reading: no "
          "uniform-file value was ever observed through this bit. The 'hi' "
          "reading is right but belongs to byte+1 BIT 0, not bit 7. An emitter "
          "should emit 0 and put the half-select in bit 0."))

V["n3_mov.subform"] = row(
    "n3_mov.subform", "hardware-run",
    "0..255 dense x byte+3 in {0x00, 0x01} x 2 register plans in the gated "
    "sweep, PLUS the complete 256 x 256 byte+2 x byte+3 cross-product "
    "(65536 encodings) run three times",
    "byte+2 is an OPERATION selector, not a 'source-class / size sub-form'. "
    "MEASURED on the full cross-product: the MOVE is byte+2 & 0x03 == 1 with "
    "byte+2 & 0xC0 == 0 -- exactly the 16 values {1,5,9,...,61} reach the "
    "destination's HIGH half, and those same 16 plus the 24 two-source-logic "
    "values reach the LOW half. byte+2 & 0x07 == 0 is the IN-PLACE NARROW "
    "(r[dst] &= 0xFFFF, byte+1 inert), which is the member db.json splits out "
    "as mov_zext16 and EXP-0161 validated. byte+2 & 0x07 == 3 behaves as XOR "
    "and == 4 as OR of the byte+1 and byte+3 operands. "
    "BYTE+2 BIT 3 (0x08) RELEASES THE SOURCE, and the release is HALF-GRANULAR: "
    "it zeroes exactly the 16-bit half that was read and leaves the other half "
    "intact (post-freeze adversarial probe, raw/prefreeze/adv01).",
    note=("PARTIAL REFUTATION OF THIS EXPERIMENT'S OWN FROZEN MODEL, recorded "
          "rather than smoothed: PRE_REGISTRATION.md H3 froze the move mask as "
          "(b2 & 0x03) == 1 and (b2 & 0xE0) == 0, i.e. 8 values. The 65536-case "
          "cross-product shows bit 5 is FREE, so the mask is (b2 & 0xC0) == 0 "
          "and there are 16 move values. The X/b2hi falsifier caught it "
          "independently: byte+2 = 0x21 moves, and it was pre-registered as a "
          "value that must not. Bits 2 and 4 are don't-care for the move. "
          "The generation arms used byte+2 = 0x01, which is inside both the "
          "frozen and the corrected mask, so no generated result depends on "
          "this correction."))

V["n3_mov.companion"] = row(
    "n3_mov.companion", "hardware-run",
    "0..255 dense x byte+2 in {0x01, 0x09} x 2 register plans, PLUS the "
    "complete 256 x 256 cross-product run three times",
    "byte+3 bit 0 selects the DESTINATION HALF (0 = write the destination's "
    "low 16 bits, 1 = write its high 16 bits) and THE OTHER HALF IS PRESERVED "
    "in both directions. The write happens iff byte+3 & 0x1E == 0; bits 5..7 "
    "are don't-care (byte+3 in {0x00,0x20,0x40,...,0xE0} all write the low half "
    "and {0x01,0x21,...,0xE1} all write the high half). byte+3 bits 1 and 2 "
    "suppress the write; bits 3 and 4 make it write zero.",
    note=("db.json calls this a 'companion / second-operand descriptor' whose "
          "value 0x01 with subform 0x00 is 'the ZERO-EXTEND high-half-zero "
          "companion'. That reading is superseded for the MOVE sub-form: 0x01 "
          "does not zero anything, it selects the high half as the destination. "
          "PARTIAL REFUTATION of this experiment's frozen H4, recorded: H4 said "
          "byte+3 >= 2 must not write; measured, 0x20/0x40/0x80 write exactly "
          "like 0x00 and 0x08/0x10 write zero. The X/b3hi falsifier caught it."))

V["n3_mov._instruction"] = row(
    "n3_mov._instruction", "hardware-run",
    "the whole 4-byte instruction GENERATED from db.json's declared bit "
    "geometry, with zero bytes copied from any compiled shader, and executed "
    "on G17P: 1680 generated half-moves and 840 generated 32-bit copies passed "
    "a host-computed 16-register prediction with 0 failures, twice",
    "n3_mov is a 16-BIT HALF-REGISTER MOVE with independent source-half and "
    "destination-half selection, an optional source release, and a two-source "
    "logic mode. A full 32-bit GPR-to-GPR copy r[i] = r[j] is TWO of them, in "
    "either order: `i3 (2j+1) 01 01` then `i3 (2j+0) 01 00`.",
    extra={"generated_32bit_copy": {
        "run01": M["gen32_run01"]["ok"], "run02": M["gen32_run02"]["ok"],
        "failures_run01": M["gen32_run01"]["failed"],
        "failures_run02": M["gen32_run02"]["failed"],
        "undecidable": M["gen32_run01"]["undecidable"],
        "pairs": 240, "destinations_covered": "all 16, union of both plans"},
        "generated_half_move": {
        "run01": M["genhalf_run01"]["ok"], "run02": M["genhalf_run02"]["ok"],
        "failures": M["genhalf_run01"]["failed"] + M["genhalf_run02"]["failed"]}})

V["mov_zext16._corroboration"] = {
    "label": "hardware-run", "target": TGT, "evidence": EV,
    "range": "byte+2 & 0x07 == 0 across the 65536-case cross-product, three runs",
    "semantics": "EXP-0161's in-place narrow r[dst] = r[dst] & 0xFFFF is "
                 "reproduced here as the byte+2 & 0x07 == 0 member of the same "
                 "instruction, and it is confirmed NOT to be a move: `93 0a 00 01` "
                 "leaves r5 untouched and sets r9 to r9 & 0xFFFF.",
    "note": "This is corroboration of an existing verdict, not a new field. "
            "mov_zext16 is a SUB-FORM of n3_mov, not a separate opcode: byte+2's "
            "low 3 bits select between narrow (0) and move (1).",
}

V["db_defects"] = {
    "DEF-0174-1": {
        "instruction": "n3_mov (and its frame_marker / mov_zext16 siblings, "
                       "which db.json gives the same field layout)",
        "defect": "the byte+1 operand field is modelled one bit off",
        "db_says": "srcA_reg = bits 8..14 (byte+1 bits 0..6); "
                   "srcA_uni = bit 15 (byte+1 bit 7), enum {0: gpr, 1: uniform/hi}",
        "measured": "source register = byte+1 bits 1..7 (aliasing period 64); "
                    "byte+1 bit 0 = SOURCE HALF select (0 = low 16, 1 = high 16); "
                    "byte+1 bit 7 = source-register bit 6, observationally inert "
                    "because of the mod-64 aliasing; no uniform file was ever "
                    "reached through it",
        "consequence_for_an_emitter": "an emitter following db.json writes S "
            "into bits 0..6, which the hardware reads as register S>>1 with "
            "half-select S&1 -- a wrong register AND a wrong half, silently",
        "evidence": "raw/g17p_20260830_run01,02 arm B/srcmap, 256 values x 2 "
                    "plans x 2 runs, 100.000% cross-run agreement, 0 model "
                    "mismatches on the 64 host-known source values per plan",
    },
    "DEF-0174-2": {
        "instruction": "n3_mov.subform / n3_mov.companion",
        "defect": "modelled as a 'source-class/size sub-form' and a "
                  "'companion / second-operand descriptor'",
        "measured": "byte+2 is an OP selector (narrow / move / xor / or) with a "
                    "source-RELEASE bit at 0x08; byte+3 bit 0 is the "
                    "DESTINATION-HALF select and the other half is preserved. "
                    "The accept masks are byte+2 & 0xC0 == 0 with byte+2 & 3 == 1 "
                    "for the move, and byte+3 & 0x1E == 0.",
        "evidence": "the complete 256 x 256 cross-product, 65536 encodings, run "
                    "three times with 100.000% same-plan cross-run agreement",
    },
    "DEF-0174-3": {
        "instruction": "pad_operand (byte0 low nibble 0)",
        "defect": "db.json states 'NOT A STANDALONE HARDWARE OPCODE ... a 2-byte "
                  "low-nibble-0 slot carrying a trailing operand / immediate / "
                  "SFU-coefficient WORD of the PRECEDING instruction'",
        "measured": "the 4-byte sequence `X0 (2S) 00 01`, placed in a program "
                    "where the preceding instruction is a completed 2-byte "
                    "mov_imm, WRITES r[S]'s value into r[X]. Verified for "
                    "S in {0,1,3,5,8,10,14} and X = 2, in both register plans "
                    "(raw/prefreeze/adv01, post-freeze adversarial probe).",
        "status": "OBSERVATION, NOT A CORRECTED MODEL. This experiment did not "
                  "sweep the low-nibble-0 group and cannot say whether those "
                  "four bytes are one instruction or a 2-byte op plus its "
                  "operand word. What is established is only that they have an "
                  "architectural effect, which 'not a standalone opcode' does "
                  "not predict. Recommended follow-up experiment.",
    },
    "DEF-0174-4": {
        "instruction": "reg_move_c1 (byte0 low nibble 0xb, byte+2 = 0x01)",
        "defect": "db.json's reg_move_c0 semantics block says 'AS OF 2026-08-28 "
                  "NO VALIDATED GPR-TO-GPR MOVE EXISTS ON APPLE9', and that the "
                  "byte+2 = 0x01 / op_desc = 0x08 form is 'UNIFORM-REGISTER-"
                  "SOURCED ONLY -- it FAILS to read a GPR written by falu2/falu2i "
                  "or by device_load' (EXP-0090)",
        "measured": "`2b (2S) 01 00` writes r[S]'s value into r2 for "
                    "S in {0,1,3,5,8,10,14}, where r[S] was written by mov_imm, "
                    "in both register plans (raw/prefreeze/adv01). The same "
                    "2*S operand encoding as n3_mov. Cross-checked against the "
                    "plans: byte+1 = 0x0e reads r7, which is 83 in plan idx15 "
                    "and 0 in plan idx7 -- exactly the two plans' r7 states.",
        "status": "OBSERVATION. EXP-0090's negative used falu2/falu2i- and "
                  "device_load-written sources; device_load on G17P is now known "
                  "to be ASYNCHRONOUS (DEF-0169-1), which is a candidate "
                  "explanation for at least that half of its negative. Not swept "
                  "here. Recommended follow-up.",
    },
}

V["_meta"] = {
    "experiment": "EXP-0174",
    "target": TGT,
    "runs": ["g17p_20260830_run01 (forward)", "g17p_20260830_run02 (reverse)",
             "g17p_20260830_run03 (grid, same plan as run01, reverse)"],
    "gate": "two gated runs; >=99% per-value cross-run agreement AND movement "
            ">= 2x disagreements; falsifiers must fire; only validity == 'valid' "
            "cases counted; >=2 carriers for hardware-run",
    "gate_result": {f: {"agreement": G[f]["cross_run_agreement_pct"],
                        "moved": G[f]["moved"],
                        "disagreements": G[f]["disagreements"],
                        "carriers": G[f]["n_carriers"]}
                    for f in sorted(G)},
    "stale_pipeline_control": M["alternate_control"],
    "grid_cross_run_same_plan": C["cross_run_same_plan"],
    "rt_ok": "recorded per case in the raw and used for NO verdict "
             "(FIELD-SWEEP-PROTOCOL 3b)",
    "prefreeze": "raw/prefreeze/** is calibration and the post-freeze "
                 "adversarial probe; it contributes to no gated verdict. The "
                 "adv01 probe is cited only inside `note` fields and for the two "
                 "OBSERVATION-status db_defects.",
}

(EXP / "analysis" / "field_verdicts.json").write_text(
    json.dumps(V, indent=1, sort_keys=True))
for k in sorted(V):
    if k.startswith("_") or k == "db_defects":
        continue
    print("%-28s %s" % (k, V[k]["label"]))
print("db_defects:", ", ".join(sorted(V["db_defects"])))
