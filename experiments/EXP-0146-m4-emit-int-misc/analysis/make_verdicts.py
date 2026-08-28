#!/usr/bin/env python3
"""EXP-0146: emit analysis/field_verdicts.json in the FIELD-SWEEP-PROTOCOL §5 shape.

Observation (outcome counts, ok-sets, required/free bit masks) is computed from the committed
raw runs; INTERPRETATION (`semantics`, `note`, and any label downgrade) is authored here and is
kept textually separate, per CODEX §7.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verdicts as V      # noqa: E402
import bitrule as BR      # noqa: E402

# ---------------------------------------------------------------- authored interpretation
# key -> (semantics, note, label_override_or_None)
SEM = {
 "carry_gen.dst@u64add": (
   "Predicate destination of the unsigned-overflow compare. Load-bearing: of the 16 encodable "
   "nibble values exactly one (the compiler's own, 0x3) reproduces the 64-bit sum; the other 15 "
   "drop or misplace the carry.",
   "run05/P2 crossed dst 0..15 against a 32-point sweep of each psel body byte (1536 "
   "combinations) and found NO (dst, psel-byte) pair other than dst=3 that restores the result, "
   "so 'dst names a predicate register the consumer can be re-pointed to' is NOT established. "
   "Emit dst=3-equivalent only: i.e. keep producer and consumer paired as the compiler does.", None),
 "carry_gen.subop@u64add": (
   "FIRST source-operand descriptor, in the project-standard (reg<<1)|is32 packing: 0x01 = r0, "
   "32-bit. Bit7 is a file-select flag that is INERT here (0x81 works identically).",
   "db.json types byte+1 as an opaque 8-bit 'subop' raw field and its semantics text calls "
   "byte+2 the carry-generate marker. The sweep shows byte+1 is an OPERAND, not a sub-opcode: "
   "exactly the two values {0x01,0x81} work and every other value changes the carry. "
   "This closes the operand-field half of INT-14.", None),
 "carry_gen.srcA@u64add": (
   "SECOND source-operand descriptor, same (reg<<1)|is32 packing: 0x03 = r1, 32-bit; bit7 INERT.",
   "Together with subop this establishes carry_gen's two-operand shape: "
   "`p[dst] = (r[subop] <u r[srcA])` evaluated on the low-word add's operands.", None),
 "carry_gen.cmpmode@u64add": (
   "Compare-relation selector. Exact rule: (value & 0xA7) == 0x22 -- bits 1 and 5 must be set, "
   "bits 0,2,7 clear; bits 3,4,6 are DON'T-CARE (0x58 free mask). 136 of 256 values silently "
   "zero the whole store; 112 give a different (wrong) relation.",
   "db.json declares only the single enum value 34 ('ordered'). The hardware accepts 8 encodings "
   "of that same relation.", None),
 "carry_gen.b5@u64add": (
   "Tail/operand-mode byte. Only 4 of 256 values reproduce the carry: {0x01,0x05,0x09,0x81}. "
   "There is NO clean required/free bit mask (0x0d, the bitwise OR of the working 0x05 and 0x09, "
   "does NOT work), so this byte is not a simple bit-flag set.",
   "db.json labels b5 'tokenization-only (framing only)'. It is load-bearing: 252 of 256 values "
   "break the result. Emit one of the four listed values.", None),
 "carry_gen.byte+2@u64add": (
   "db.json models byte+2 as an 8-bit MATCH constant 0x35. The hardware only requires "
   "(value & 0xCD) == 0x05: bits 1, 4 and 5 are DON'T-CARE. 8 of 256 values work.",
   "Pre-registered falsifier F1 (byte+2 = 0x00) FIRED: contained command-buffer fault, "
   "reproducing EXP-0038's A18 neutralisation result on M4 by a second method.", None),
 "carry_gen.byte+0@u64add": (
   "byte0 = (dst<<4) | 0x2. Exactly one of 256 values works (0x32). 15 values fault, 9 silently "
   "zero.", "Raw byte probe: the low nibble is a db.json match constant, the high nibble is dst.",
   None),

 "ilogic.srcA@logic_and": (
   "First source-operand descriptor, (reg<<1)|is32: 0x05 = r2, 32-bit. Bit7 INERT (0x85 "
   "identical). 248 of 256 values SILENTLY ZERO the result -- the canonical Apple9 wrong-operand "
   "failure mode.", "", None),
 "ilogic.srcB@logic_and": (
   "Second source-operand descriptor: 0x01 = r0, 32-bit. Bit7 INERT. 248/256 silently zero.",
   "", None),
 "ilogic.op_base@logic_and": (
   "Function-family base bit (byte+2 bit0). 1 = the and/or base, 0 = the xor base. With the "
   "carrier's lut_a=lut_b=0, flipping it to 0 turns AND into the constant 0.",
   "Both values are legal encodings; which functions each reaches is the joint map in "
   "analysis/ilogic_lut_table.md.", None),
 "ilogic.lut_a@logic_and": (
   "Primary LUT selector. Only bits 0 and 1 select; bits 2,3,4 are DON'T-CARE (free mask 0x1c) "
   "and bits 5,6,7 must be clear. Rule for the carrier's AND: (value & 0xE3) == 0x00.",
   "EXP-0102 (INT-12) could reach only 10 of the 16 two-input boolean functions through MSL "
   "source and left the raw field width UNKNOWN. This sweep resolves both: lut_a is 2 selector "
   "bits inside an 8-bit byte, and (op_base, lut_a&3, lut_b&0x0f) reaches ALL 16 functions with "
   "zero collisions. See analysis/ilogic_lut_table.md.", None),
 "ilogic.lut_b@logic_and": (
   "Secondary LUT selector. Load-bearing bits are 0,1,2 and 4 ((value & 0x17) == 0 for AND); "
   "bits 3,5,6,7 are DON'T-CARE for the AND function.",
   "Note bit3 (0x08) IS function-selecting in combination with lut_a (it turns AND into "
   "a_and_not_b on the xor base) -- it reads as free in the 1-D sweep only because with "
   "lut_a=0/op_base=1 it happens to leave AND unchanged. Use the joint table, not this mask.",
   None),
 "ilogic.outmod@logic_and": (
   "Output/store enable. Exactly one load-bearing bit: bit7. (value & 0x80) == 0x80 -> correct "
   "result; all 128 values with bit7 clear SILENTLY ZERO. Bits 0-6 are DON'T-CARE.",
   "db.json's 'bit7 = output/store flag' corpus claim is confirmed on hardware and the other "
   "7 bits are proven inert.", None),
 "ilogic.z6@logic_and": ("HW-TESTED INERT: all 256 values reproduce the exact result.",
   "db.json labels z6 'tokenization-only / zero tail'. Confirmed inert on hardware over the full "
   "byte range, in a carrier where the same instruction's other fields demonstrably change the "
   "output. Role UNKNOWN; do not synthesize a meaning.", None),
 "ilogic.z8@logic_and": ("HW-TESTED INERT: all 256 values reproduce the exact result.",
   "Same as z6.", None),
 "ilogic.z9@logic_and": ("HW-TESTED INERT: all 256 values reproduce the exact result.",
   "Same as z6.", None),
 "ilogic.byte+0@logic_and": (
   "Opcode byte. Exactly one value works (0x0b); 36 fault, 203 silently zero.",
   "Pre-registered falsifier F2 (byte0 = 0x0a) FIRED with a contained command-buffer fault.",
   None),

 "irotate.b1@rot_imm": (
   "Only bits 1 and 2 are load-bearing ((value & 0x06) == 0x00); the other six bits are "
   "DON'T-CARE. 64 of 256 values give the exact rotate, 170 silently zero, 22 fault.", "", None),
 "irotate.b2@rot_imm": (
   "Exactly one load-bearing bit: bit1 must be set ((value & 0x02) == 0x02). 128/256 correct, "
   "128 silently zero.",
   "db.json carries byte+2 == 0x56 as part of the match; only bit1 of it is required.", None),
 "irotate.operands@rot_imm": (
   "40-bit raw field = bytes +3..+7, swept BYTE-WISE, all 256 values each. Per-byte rules: "
   "+3 (value&0xFE)==0 (2 ok, 64 fault); +4 (value&0x02)==0x02 (128 ok); "
   "+5 (value&0xFC)==0 (4 ok); +6 (value&0xFD)==0x6C (2 ok); +7 (value&0xF1)==0 (8 ok).",
   "The ROTATE AMOUNT is not a free operand here: byte+6 admits only {0x6c,0x6e}, so the "
   "immediate rotate count is NOT independently emittable from this carrier -- a rotate by a "
   "different constant needs a differently-compiled carrier. Reported as a bounded limitation.",
   None),
 "irotate.tail@rot_imm": (
   "32-bit raw field = bytes +8..+11, swept BYTE-WISE, all 256 values each. Per-byte rules: "
   "+8 (value&0xB7)==0xB0 (4 ok, 64 fault); +9 (value&0x12)==0x10 (64 ok); "
   "+10 (value&0xFD)==0x09 (2 ok); +11 (value&0x01)==0x00 (128 ok, i.e. only bit0 matters).",
   "db.json labels the whole 32-bit tail 'tokenization-only'. Three of its four bytes are "
   "load-bearing.", None),

 "mov_zext16.src_reg@zext16": (
   "HW-TESTED INERT in this carrier: ALL 128 values reproduce the exact zero-extend.",
   "db.json (from EXP-M4-13 corpus correlation) types byte+1 bits0-6 as the SOURCE REGISTER. "
   "That is CONTRADICTED here: no value of the field changes the result. Alternative not "
   "excluded: the operand may be ALU-forwarded from the immediately preceding device_load "
   "(the known 0x56 direct-forward pattern), making the field a don't-care in this INSTANCE "
   "rather than in the encoding. run05/P3 tried to settle it with a carrier whose zext source "
   "is several instructions away, but that MSL compiled to iadd2/funary and emitted no "
   "mov_zext16 at all, so the question is OPEN. Recorded under db_defects.", None),
 "mov_zext16.src_flag@zext16": (
   "HW-TESTED INERT in this carrier: both values reproduce the exact result.",
   "Same caveat as src_reg.", None),
 "mov_zext16.subform@zext16": (
   "Source-class / size sub-form selector. Load-bearing: 80 of 256 values give the exact "
   "zero-extend, 111 give a different value, 39 silently zero and 26 FAULT. Only bit5 is free.",
   "", None),
 "mov_zext16.extend@zext16": (
   "Companion / extend-width descriptor. 252 of 256 values reproduce the result; only 4 "
   "silently zero. Bits 3 and 4 are free.",
   "db.json's '0x01 = the low-16 zero-extend companion' is far weaker than reality: almost the "
   "whole byte is a don't-care for this lowering.", None),
 "mov_zext16.byte+0@zext16": (
   "Opcode byte. 99 of 256 values still produce the exact zero-extend (the 0x?3 16-bit narrow "
   "family generalises over the dst nibble), 114 FAULT, 38 silently zero.",
   "Pre-registered falsifier F4 (byte0 = 0x12) FIRED (fault).", None),

 "shift_amt_move.dst@rot_var": (
   "Destination register nibble. Load-bearing: exactly one value (0x0) works; the other 15 "
   "silently zero.", "", None),
 "shift_amt_move.src_reg@rot_var": (
   "Source register (byte+1 bits0-6). Load-bearing: exactly ONE of 128 values works (0x01); "
   "125 give a wrong value and 2 silently zero.",
   "This is the direct contrast that makes mov_zext16.src_reg's inertness meaningful: the same "
   "'compact move byte+1 = source register' model IS confirmed here.", None),
 "shift_amt_move.src_flag@rot_var": (
   "HW-TESTED INERT: both values reproduce the result.", "", None),
 "shift_amt_move.kind@rot_var": (
   "Shift/rotate-amount kind selector. Rule (value & 0xC3) == 0x00 -- bits 0,1,6,7 must be "
   "clear, bits 2,3,4,5 DON'T-CARE. 16 of 256 values work, 176 silently zero and 64 FAULT.",
   "db.json's enum names only 0x1c 'shift_amt' and 0x3c 'rotate_amt'. The hardware accepts 16 "
   "encodings in this carrier, including 0x00, and both db values are inside the accepted set.",
   None),
 "shift_amt_move.op_desc@rot_var": (
   "Operand descriptor. Exactly {0x05, 0x85} work; bit7 INERT; 254 values wrong.",
   "db.json labels op_desc 'untested'. It is load-bearing and follows the same "
   "(reg<<1)|is32 + inert-bit7 shape as the other operand descriptors in this cluster.", None),

 "n3_mov.dst@u64eq": ("HW-TESTED INERT in this carrier: all 16 values reproduce the result.",
   "The instruction IS live here (subform faults and silently zeros), so this is an inertness "
   "observation, not a dead-code artifact. Most likely the carrier's boolean output cannot "
   "observe where the move lands. Role in this instance UNKNOWN.", None),
 "n3_mov.srcA_reg@u64eq": ("HW-TESTED INERT in this carrier: all 128 values reproduce the result.",
   "Same caveat as dst; and the same contradiction of a corpus-correlation 'source register' "
   "claim as mov_zext16.src_reg. Recorded under db_defects.", None),
 "n3_mov.srcA_uni@u64eq": ("HW-TESTED INERT in this carrier: both values reproduce the result.",
   "", None),
 "n3_mov.subform@u64eq": (
   "Source-class / size sub-form selector. Load-bearing: 90/256 ok, 118 silently zero, "
   "32 FAULT, 16 wrong. Only bit5 free.",
   "db.json labels subform 'untested'; it is the load-bearing byte of this instruction.", None),
 "n3_mov.companion@u64eq": (
   "Companion descriptor. 224 of 256 values reproduce the result; 32 silently zero. Bits 3-7 "
   "free.", "", None),

 "n2_op6.dst@u64eq": ("Destination register nibble: exactly one value works, 15 silently zero.",
   "", None),
 "n2_op6.src_desc@u64eq": ("Source descriptor: {0x00,0x01,0x80,0x81} work -- bits 0 and 7 free, "
   "bits 1-6 must be clear. 252/256 wrong.", "", None),
 "n2_op6.opsel@u64eq": ("Op/mode selector: (value & 0xD5) == 0x05, bits 1,3,5 DON'T-CARE. "
   "8/256 ok, 196 silently zero.", "", None),
 "n2_op6.opA@u64eq": ("Second operand/source descriptor: 118 of 256 values reproduce the result, "
   "138 silently zero; no clean mask rule (only bit0 free).", "", None),
 "n2_op6.opB@u64eq": ("Compare-mode / operand-mode descriptor: (value & 0xA6) == 0x26, "
   "bits 0,3,4,6 DON'T-CARE. 16/256 ok.", "", None),
 "n2_op6.imm_sel@u64eq": ("Trailing index/immediate: exactly {0x01,0x05,0x09,0x81} work "
   "(the same irregular 4-value set as carry_gen.b5, no clean mask rule).", "", None),
 "n2_op6.dst@sfu_sin": ("Destination register nibble on the SECOND carrier: exactly one value "
   "works, 15 silently zero -- same shape as the u64eq carrier.", "", None),
 "n2_op6.src_desc@sfu_sin": ("Source descriptor on the second carrier: (value & 0x7E) == 0x04, "
   "bits 0 and 7 free.", "Cross-carrier: the u64eq carrier requires 0x00 in the same bits, so "
   "the field is a genuine per-instance operand, not a constant.", None),
 "n2_op6.opsel@sfu_sin": ("Op/mode selector on the second carrier: (value & 0xC7) == 0x03, "
   "bits 3,4,5 DON'T-CARE.", "", None),
 "n2_op6.opA@sfu_sin": ("Second operand descriptor: (value & 0x82) == 0x82; 64/256 ok.", "", None),
 "n2_op6.opB@sfu_sin": ("Mode descriptor: {0x15,0x95} only; bit7 INERT; 87 values FAULT.",
   "", None),
 "n2_op6.imm_sel@sfu_sin": ("Trailing index/immediate: {0x06,0x07,0x86,0x87}-shaped; "
   "(value & 0x7E) == 0x06, bits 0 and 7 free.", "", None),

 "n2_op8.dst@sfu_sin": ("Destination nibble: {0x0,0x1} ok, 14 wrong. Bit0 free.", "", None),
 "n2_op8.srcA_desc@sfu_sin": ("Source descriptor: exactly one value (0xc2) works; 224 of 256 "
   "silently zero.", "db.json labels the whole instruction 'tokenization-only'; this byte is "
   "strictly load-bearing.", None),
 "n2_op8.opsel@sfu_sin": ("Op selector: exactly one value (0x49) works; 11 FAULT, 92 silently "
   "zero.", "", None),
 "n2_op8.body@sfu_sin": (
   "40-bit raw field = bytes +3..+7, swept BYTE-WISE, all 256 values each. Per-byte rules: "
   "+3 exactly 0x0b; +4 (value&0xDF)==0x04; +5 (value&0x7F)==0x05 (bit7 free); "
   "+6 (value&0xE3)==0x80; +7 (value&0x1F)==0x08 (bits 5,6,7 free).",
   "Every byte of the 'tokenization-only' body is load-bearing. Per clean-room rule 5 the SFU "
   "range-reduction COEFFICIENT SEQUENCE is deliberately not reconstructed; only the "
   "accept/reject envelope of each byte is documented.", None),

 "n2_op10.dst@roundmodes": ("Destination nibble: exactly one value works, 14 wrong.", "", None),
 "n2_op10.src@roundmodes": ("Source register descriptor: 254 of 256 values still reproduce the "
   "result -- effectively inert except 2 wrong values. Bit7 free.",
   "Weak: this carrier sums five conversions, so a mis-sourced operand can still produce the "
   "same sum. Treated as a bounded observation.", None),
 "n2_op10.opsel@roundmodes": ("Form selector: (value & 0xCF) == 0x01, bits 4,5 DON'T-CARE. "
   "4/256 ok, 36 FAULT, 206 wrong.",
   "db.json's enum names 33 (0x21) 'sfu_roundmode_marshal'; 0x21 is inside the accepted set.",
   None),
 "n2_op10.opdesc@roundmodes": ("Sub-op descriptor: 189 of 256 values reproduce the result, "
   "67 wrong; no clean mask rule.", "", None),
 "n2_op10.immword@roundmodes": (
   "48-bit raw field = bytes +4..+9, swept BYTE-WISE, all 256 values each. Per-byte: "
   "+4 16/256 ok (82 FAULT); +5 10/256 ok; +6 17/256 ok; +7 112/256 ok; +8 160/256 ok; "
   "+9 HW-TESTED INERT (all 256 ok).",
   "Per clean-room rule 5 the marshalling word's VALUE SEQUENCE is deliberately not "
   "reconstructed; only each byte's accept/reject envelope is documented.", None),

 "sfu_marker.byte+0@sfu_sin": (
   "NOT a byte-invariant token. Rule (value & 0xF7) == 0x06 -- only bit3 is free; 2 of 256 "
   "values work, 192 silently zero, 62 give a WRONG value. Setting it to 0x00 flips the SIGN "
   "of fast::sin on the rows whose argument needs range reduction.",
   "db.json describes sfu_marker as a 'byte-INVARIANT 2-byte token (06 02) ... fixed control "
   "token with no operand bits'. Refuted: the token carries live control. Recorded under "
   "db_defects.", None),
 "sfu_marker.byte+1@sfu_sin": (
   "Rule (value & 0x13) == 0x02 -- bits 2,3,5,6,7 are DON'T-CARE; 32 of 256 values work, "
   "128 silently zero, 96 wrong.", "Same db_defect as byte+0.", None),

 "iadd2.addsub@u64sub": (
   "THE add/subtract selector of the 64-bit form. 0 = the compiler-emitted 64-bit SUBTRACT; "
   "1 = a full, single-instruction 64-bit ADD (see I64_answers.md I64-01).",
   "This is the experiment's headline result. Classified 'wrong_value' by the sweep only "
   "because that arm's oracle is a-b; the observed words equal (a+b) mod 2^64 EXACTLY on both "
   "gated runs and on run05/P1's second, independent boundary input set (5/5 repetitions).",
   None),
 "iadd2.dst@u64sub": (
   "Destination register-PAIR base, (reg<<1)|size. Only {0x00,0x01} reproduce the result "
   "(bit0/size free); 0x02-0x03 give a wrong value; 0x04-0xBD SILENTLY ZERO; "
   "**0xBE-0xFF FAULT** -- i.e. destination register index >= 95 raises a contained "
   "GPU address fault.",
   "The 0xBE fault boundary is a hard, independently-derived confirmation of the ~96-register "
   "addressable GPR file (EXP-0020) from a different instruction family and a different method.",
   None),
 "iadd2.srcA@u64sub": (
   "Source-A descriptor of the 64-bit form: {0x50,0x54} (bit2 free). EVERY value with bits 0 "
   "and 1 both set (v & 3 == 3, 64 values) raises a contained GPU address FAULT.",
   "The 32-bit form of the same instruction in the same compiler output uses srcA=0xA8, so this "
   "byte carries the operand WIDTH as well as the register. The exact width bit is not isolated "
   "(changing srcA also changes which register is read), so it is reported as an observation.",
   None),
 "iadd2.opmode@u64sub": (
   "Exactly ONE load-bearing bit: bit1. (value & 0x02) == 0x02 -> correct; all 128 values with "
   "bit1 clear SILENTLY ZERO. Bits 0,2..7 DON'T-CARE.", "", None),
 "iadd2.srcB_imm@u64sub": ("(value & 0xFC) == 0x08; bits 0,1 DON'T-CARE. 4/256 ok, "
   "4 silently zero, 248 wrong.", "", None),
 "iadd2.srcB_imm_hi@u64sub": ("Load-bearing: must be 0.", "", None),
 "iadd2.srcB_ext@u64sub": ("(value & 0x7C) == 0x00; bits 0,1 DON'T-CARE. 4/128 ok.", "", None),
 "iadd2.srcB_reg_hi@u64sub": ("Only the LSB is load-bearing (must be 0); the remaining six bits "
   "are DON'T-CARE (64/128 ok).", "", None),
 "iadd2.opc_tail@u64sub": ("(value & 0x11) == 0x11 -- bits 0 and 4 must be set, the other six "
   "DON'T-CARE. 64/256 ok.", "", None),
 "iadd2.opc_tail2@u64sub": ("(value & 0x05) == 0x05 -- bits 0 and 2 must be set, the other six "
   "DON'T-CARE. 64/256 ok.", "", None),
 "iadd2.lenbit@u64sub": ("Instruction-length selector: 1 = the 10-byte 2-source form (correct); "
   "0 makes the hardware read a 12-byte instruction and FAULTS.", "", None),
 "iadd2.store_en@u64sub": ("Load-bearing: 1 = result published, 0 SILENTLY ZEROES the store.",
   "", None),
 "iadd2.b2_bit0@u64sub": ("HW-TESTED INERT: both values reproduce the exact 64-bit subtract.",
   "", None),
 "iadd2.b2_fmt@u64sub": ("HW-TESTED INERT: all 64 values reproduce the exact 64-bit subtract.",
   "", None),
 "iadd2.byte+0@u64sub": ("Opcode byte. Only 0x1f gives the subtract; 0x9f gives an exact 64-bit "
   "ADD (scored 'wrong_value' against this arm's subtract oracle); 50 values FAULT and 195 "
   "silently zero.",
   "Pre-registered falsifier F3 -- resolved POSITIVE. See I64_answers.md.", None),
}

# db fields that were swept byte-wise through a multi-byte raw descriptor
COMPOSITE = {
 "irotate.operands@rot_imm": ["irotate.byte+3@rot_imm", "irotate.byte+4@rot_imm",
                              "irotate.byte+5@rot_imm", "irotate.byte+6@rot_imm",
                              "irotate.byte+7@rot_imm"],
 "irotate.tail@rot_imm": ["irotate.byte+8@rot_imm", "irotate.byte+9@rot_imm",
                          "irotate.byte+10@rot_imm", "irotate.byte+11@rot_imm"],
 "n2_op8.body@sfu_sin": ["n2_op8.byte+3@sfu_sin", "n2_op8.byte+4@sfu_sin",
                         "n2_op8.byte+5@sfu_sin", "n2_op8.byte+6@sfu_sin",
                         "n2_op8.byte+7@sfu_sin"],
 "n2_op10.immword@roundmodes": ["n2_op10.byte+4@roundmodes", "n2_op10.byte+5@roundmodes",
                                "n2_op10.byte+6@roundmodes", "n2_op10.byte+7@roundmodes",
                                "n2_op10.byte+8@roundmodes", "n2_op10.byte+9@roundmodes"],
}


def main():
    v = V.build()
    rules = json.loads((HERE / "bit_rules.json").read_text())
    out = {}
    for k, d in sorted(v.items()):
        if d["instr"].startswith("_") or "+" in d["field"] and d["field"].count("+") > 1:
            continue
        sem, note, override = SEM.get(k, ("", "", None))
        r = rules.get(k) or {}
        rng = d["range"]
        if r.get("exact_mask_rule"):
            rng += "; exact rule (value & 0x%02x) == 0x%02x, free bits 0x%02x" % (
                r["required_mask"], r["required_value"], r["free_mask"])
        entry = {"label": override or d["label"], "range": rng, "target": d["target"],
                 "evidence": d["evidence"], "semantics": sem, "note": note,
                 "carrier": d["carrier"], "outcomes": d["outcomes"],
                 "full_dense": d["full_dense"], "unresolved_cases": d["unresolved"],
                 "adjudicated_cases": d["adjudicated_cases"]}
        member_of = [ck for ck, parts in COMPOSITE.items() if k in parts]
        if member_of and not sem:
            entry["label"] = "hardware-run"
            entry["semantics"] = ("byte-wise component of the composite db field %s; see that "
                                  "entry for the per-byte rules" % member_of[0])
            entry["note"] = "Not itself a db.json field: a raw byte inside a multi-byte field."
            entry["component_of"] = member_of[0]
            out[k] = entry
            continue
        if not sem:
            entry["label"] = "untested"
            entry["note"] = ((note + " ") if note else "") + \
                "No authored semantics: swept but not interpreted; do not promote."
        out[k] = entry

    # composite db fields assembled from their byte-wise sweeps
    for ck, parts in COMPOSITE.items():
        sem, note, _ = SEM.get(ck, ("", "", None))
        ok = all(out.get(p, {}).get("label") == "hardware-run" or p in v for p in parts)
        oc = collections.Counter()
        for p in parts:
            for kk, vv in v[p]["outcomes"].items():
                oc[kk] += vv
        out[ck] = {"label": "hardware-run" if ok else "untested",
                   "range": "swept BYTE-WISE: %d constituent bytes x all 256 values = %d cases"
                            % (len(parts), 256 * len(parts)),
                   "target": "M4", "evidence": ["EXP-0146"], "semantics": sem, "note": note,
                   "carrier": ck.split("@")[1], "outcomes": dict(oc), "full_dense": True,
                   "unresolved_cases": sum(v[p]["unresolved"] for p in parts),
                   "adjudicated_cases": sum(v[p]["adjudicated_cases"] for p in parts),
                   "composed_from": parts}
    Path(HERE / "field_verdicts.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    lab = collections.Counter(x["label"] for x in out.values())
    print("field_verdicts.json:", len(out), "entries", dict(lab))
    for k in sorted(out):
        if out[k]["label"] != "hardware-run":
            print("   not promoted:", k, out[k]["label"])


if __name__ == "__main__":
    main()
