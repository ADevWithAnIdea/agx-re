#!/usr/bin/env python3
"""EXP-0203 -- assemble the final analysis/field_verdicts.json.

Runs the gate twice (hardware G7 and the literal frozen G7), attaches the per-field notes,
and appends the `db_defects` block that FIELD-SWEEP-PROTOCOL section 6 asks for when a sweep
shows the modelled boundaries do not match the hardware.

Usage:  python3 analysis/finalize.py
"""
import json
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
R1, R2, R3 = "raw/g17p_run21", "raw/g17p_run22", "raw/g17p_run23"


def run_gate(mode, out):
    subprocess.run([sys.executable, str(EXP / "analysis" / "verdicts.py"), R1, R2,
                    "--g7", mode, "--out", str(EXP / out)], cwd=str(EXP), check=True,
                   stdout=subprocess.DEVNULL)
    return json.loads((EXP / out).read_text())


def run_gate_pair(r_a, r_b, out):
    subprocess.run([sys.executable, str(EXP / "analysis" / "verdicts.py"), r_a, r_b,
                    "--g7", "hardware", "--out", str(EXP / out)], cwd=str(EXP), check=True,
                   stdout=subprocess.DEVNULL)
    return json.loads((EXP / out).read_text())


NOTES = {
 "half_alu_fma12.dst": (
  "**THE 12-BYTE FORM'S DESTINATION NIBBLE HAD NEVER BEEN SWEPT.** `validation.json`'s "
  "previous note (EXP-0196) reported '768 records over 256 distinct values' for this row; "
  "those records carry `fstart: 8, fwidth: 8` and are the field EXP-0183 RENAMED to `srcA`. "
  "A 4-bit field cannot have 256 distinct values. EXP-0180's only bits-4..7 arm is `DSTNIB` "
  "(32 records) and it runs on `half_alu_ext8`, the 8-byte form. EXP-0196's other two "
  "findings were correct and are what this experiment fixed: no host oracle existed, and the "
  "read-back was not isolated.\n"
  "SEMANTICS (host-oracle verified, 100% of decidable values in both gated runs): the nibble "
  "selects GPR n; the fp16 result lands in **r[n]'s LOW 16 bits** with **r[n]'s HIGH 16 bits "
  "preserved**; no other architectural register changes. Model "
  "`r[n].lo = fp16_rn(|h(byte+1)| * h(byte+3) - h(byte+5))` at byte+2 = 0x06, byte+4 = 0x13.\n"
  "COVERAGE: all 16 values dispatched in each of 4 arms. Five values per arm are overwritten "
  "by that arm's own infrastructure (the dump index register and the four length markers) and "
  "are recorded `undecidable_layout`, never `inert`; the two infrastructure layouts are "
  "complementary, so every one of the 16 is decidable in at least one arm and six are "
  "decidable in both."),
 "half_pack.dstlo": (
  "**MISNAMED IN db.json: this is a SOURCE half-register descriptor, not a destination.** "
  "`half_pack` (byte0 = 0x18) is the high-lane sibling of the byte0-low-nibble-0 half-ALU "
  "family and has the same operand shape; byte+1 is its first source descriptor "
  "h = (reg<<1)|is_high with **bit 7 a don't-care**. Measured model, 256/256 in both gated "
  "runs, on two carriers: `r[byte0>>4].hi = fp16_rn(h(byte+1) + h(byte+3))`, the destination's "
  "LOW half preserved, and **both named source half-lanes zeroed** (the byte+2 = 0x18 "
  "opflags-3 source release).\n"
  "DETECTION POWER: 256 values produce 29 distinct payloads per arm, which is the PREDICTED "
  "number, not a weakness -- 16 GPRs x 2 halves reachable, bit 7 ignored, and every descriptor "
  "naming an unseeded GPR reading 0. The oracle predicts which of the 29 each value gives, and "
  "was right every time.\n"
  "OPERAND ORDER IS NOT ESTABLISHED: the measured operation is commutative, so this sweep "
  "cannot tell byte+1 from byte+3 by role. The proposed name follows the family's positional "
  "convention (byte+1 = srcA), not an observation."),
 "half_pack.b3": (
  "**TYPED `raw` IN db.json: it is the second SOURCE half-register descriptor.** Same "
  "measured model, coverage and caveats as `half_pack.dstlo` (see that note); 256/256 oracle "
  "match in both gated runs on two carriers, 0 identity changes, cross-run agreement 100%."),
 "half_alu_fma12.ext": (
  "FORCED to `untested` by PRE_REGISTRATION section 6: `ext` is 64 bits wide, so 2048 sampled "
  "values is 0.0% of its encodable range and no sweep can promote it. That is a statement "
  "about the DESCRIPTOR, not about the hardware -- the sweep did establish the region's "
  "internal structure, and it is reported under `db_defects` as a proposed split. The "
  "headline: **bits 40..47 (byte+5) are a third fp16 SOURCE half-register descriptor**, dense "
  "over 0..255 with 256/256 full-vector oracle match on both carriers in both gated runs and "
  "bit 7 a measured don't-care (128/128 pairs identical). The 54.4%/47.5% oracle rates on this "
  "row are expected and are not a failure: mutating byte+4 selects arithmetic modifiers the "
  "frozen model deliberately does not predict."),
}

DB_DEFECTS = {
 "half_pack.byte0": {
  "claim": "db.json pins ALL EIGHT bits of byte0 in `match` (0x18), so every db-expressible "
           "encoding writes r1. byte0's HIGH nibble is the destination GPR and its LOW nibble "
           "(8) is the family tag -- the same defect class as DEF-0180-1 one family over.",
  "evidence": "EXP-0203: the instruction had to be built byte by byte to express any other "
              "destination; the anchor at dst nibble 1 writes r1's HIGH half and preserves "
              "its LOW half, 256/256 under the host oracle in both gated runs.",
  "status": "REPORTED, not applied -- db.json is the orchestrator's file."},
 "half_pack.write_target": {
  "claim": "`half_pack` writes the destination's HIGH 16 bits and preserves its LOW 16 bits. "
           "The byte0-low-nibble-0 sibling writes the LOW half. The db semantics string calls "
           "this instruction a 'pack'; what was measured is a per-lane ALU op on the HIGH lane.",
  "evidence": "EXP-0203 raw/g17p_run21..23, 1568 half_pack field records, oracle match 100%."},
 "half_pack.source_release": {
  "claim": "At byte+2 = 0x18 the instruction ZEROES both named source half-lanes (opflags 3 "
           "source release). Which lane is zeroed follows the descriptor's value.",
  "evidence": "EXP-0203 pilot01: every release-free candidate model scored 2/80; with the "
              "release the model scores 80/80, and 512/512 over the gated field sweeps."},
 "half_pack.length_gate": {
  "claim": "Independent HARDWARE confirmation of DEF-0154-1. `isadb.instr_length` accepts "
           "byte0 == 0x18 as a 4-byte `half_pack` only when byte+1 == 0x05, so our own "
           "tokenizer returned `<unknown>` for the anchor `18 0d 18 11` and disagreed with "
           "itself on 11 of the 256 byte+1 values -- while the HARDWARE consumed exactly four "
           "bytes for ALL 256 (all four 2-byte length markers survived in every case, in three "
           "gated runs). The byte+1 gate is wrong and is not a length condition.",
  "evidence": "EXP-0203 raw/g17p_run21..23, `hw_markers == 4` for 256/256 values x 2 arms x 3 "
              "runs; `tok_instr` recorded alongside and NEVER gated on."},
 "half_alu_fma12.ext": {
  "claim": "`ext` is not one 64-bit field. Proposed split, with what each part was measured to "
           "do at (opsel 6, length selector 3): "
           "bits 32..33 = LENGTH SELECTOR (already known); "
           "bits 34..39 = arithmetic/modifier bits -- live bits measured at 3,4,5,6,7 "
           "(bit 2 showed no effect on either carrier); "
           "**bits 40..47 = `srcC`, the third fp16 source half-register descriptor** "
           "h = (reg<<1)|is_high, bit 7 a DON'T-CARE; "
           "bits 48..55 (byte+6) live at bits 3..7; bits 56..63 (byte+7) live at bit 4; "
           "bits 64..71 (byte+8) and 72..79 (byte+9) live at bit 1 only; "
           "bits 80..87 (byte+10) live at bit 0 -- **visible on carrier B and INVISIBLE on "
           "carrier A**; bits 88..95 (byte+11) showed no effect on either carrier.",
  "inertness_caveat": "NOTHING here is declared inert. byte+10 is the demonstration: it read "
                      "as a single payload over all 256 values on carrier A and moved on "
                      "carrier B in the same run. Per FIELD-SWEEP-PROTOCOL section 9 an inert "
                      "claim needs a positive control in the dimension the bit would control, "
                      "and this experiment has none for byte+11.",
  "evidence": "EXP-0203 analysis/ext_bytes.json, 2048 values x 2 carriers x 3 runs; "
              "byte+5: 256/256 hardware identity preserved AND 256/256 full-vector oracle "
              "match; bit-7 don't-care 128/128."},
}


def main():
    hw = run_gate("hardware", "analysis/field_verdicts.json")
    fz = run_gate("frozen", "work/field_verdicts_g7frozen.json")
    rev = run_gate_pair(R1, R3, "work/field_verdicts_21v23.json")
    ext = json.loads((EXP / "analysis" / "ext_bytes.json").read_text())
    for k, v in hw.items():
        v["note"] = NOTES.get(k, "")
        v["target"] = "G17P"
        v["evidence"] = ["EXP-0203"]
        v["cross_check_frozen_G7"] = {
            "label": fz[k]["label"], "covered_values": fz[k]["covered_values"],
            "moved": fz[k]["moved"],
            "why_it_differs": ("the literal frozen G7 also required OUR OWN tokenizer's "
                               "mnemonic to match the anchor's; every value it excluded had "
                               "hw_markers identical to the anchor AND oracle_match true, so "
                               "the correction re-admits passing values and cannot manufacture "
                               "a promotion. See PRE_REGISTRATION Amendment 03.")}
        v["cross_check_reverse_order_run"] = {
            "pair": "%s vs %s (reverse case order)" % (R1, R3),
            "label": rev[k]["label"], "covered_values": rev[k]["covered_values"],
            "moved": rev[k]["moved"], "disagree": rev[k]["disagree"]}
    hw["db_defects"] = DB_DEFECTS
    hw["_ext_byte_analysis"] = ext
    hw["_provenance"] = {
        "experiment": "EXP-0203-g17p-half-oracle", "target": "G17P",
        "gated_runs": [R1, R2, R3],
        "pilot": "raw/pilot01 (instruments only; never evidence for a field verdict)",
        "burned_run_ids": ["g17p_run01", "g17p_run11"],
        "clean_room": "OWN-SHADER + HW-PROBE; no Apple binary introspected"}
    (EXP / "analysis" / "field_verdicts.json").write_text(json.dumps(hw, indent=1, sort_keys=True))
    for k in sorted(hw):
        if k.startswith("_") or k == "db_defects":
            continue
        print("%-28s %-16s covered=%s/%s moved=%d disagree=%d  (frozen-G7: %s)"
              % (k, hw[k]["label"], hw[k]["covered_values"], hw[k]["encodable_range"],
                 hw[k]["moved"], hw[k]["disagree"], hw[k]["cross_check_frozen_G7"]["label"]))


if __name__ == "__main__":
    main()
