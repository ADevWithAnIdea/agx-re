#!/usr/bin/env python3
"""EXP-0145 FROZEN encoding rules for the byte0-low-nibble-1 bfloat/half ALU
group, derived in the DISCLOSED pre-freeze pilot phase (PROGRESS.md M1-M3,
raw evidence work/pilot/explore_bfadd.jsonl + the explore2 byte maps).

These are RULES, not copied byte strings: every generated instruction in the
GENERATED family is built from the fields below, so a wrong rule shows up as a
wrong host oracle, not as a silently-correct replay.

  8-BYTE FORM  (bf_add_dst / bf_mul_dst / bf_alu -- one descriptor, three names)
    byte+0  bits[7:4] = dst register (r0..r15); bits[3:0] = 0x1  (group)
    byte+1  srcA operand = (reg << 1) | fmt      reg 7 bits, fmt 0=bf16 1=fp16
    byte+2  opsel: bits[2:0]  4=add 5=mul 6=fma(->10 byte) 7=illegal
                   bits[5:3]  inert; bits[7:6] -> silent zero
    byte+3  srcB operand = (reg << 1) | fmt
    byte+4  operand half-select / required base:
                   bit3 = srcA half (0 = low 16, 1 = high 16)
                   bit4 = srcB half
                   the remaining bits are a CARRIER-DEPENDENT required pattern
                   (0x01 for the native-bfloat carrier, 0x05 for the
                   float-converted carrier); deviations silently zero.
    byte+5  source modifiers: bit0 = suppress srcA, bit1|bit2 = suppress srcB,
                   bit3 = negate srcB, bit4 -> zero, bits[7:5] inert
    byte+6  bits[7:6] MUST be 0b11 (operand-valid base); bit1 = negate srcA;
                   bits 0,2,3,4,5 inert
    byte+7  bits[1:0] MUST be 0b01; bits[7:2] inert on the float carrier

  10-BYTE FORM (bf_fma_dst, opsel 0x1e) -- PREDICTED, this experiment tests it:
    byte+0..3 as above; byte+5 = srcC operand = (reg << 1) | fmt;
    byte+4, byte+6, byte+7 carry the half-select/control pattern (kept at the
    compiler's own baseline value); byte+8 = 0xC0 base, byte+9 = marker.

`fmt=1` does NOT widen the operand: it re-interprets the SAME 16-bit halfword
as IEEE binary16 instead of bfloat16 (pilot: r2 holding bf16 0x4040 reads 3.0
with fmt=0 and 2.125 with fmt=1).
"""

ADD, MUL, FMA = 0x1C, 0x1D, 0x1E

def bf8(dst, srcA_reg, fmtA, srcB_reg, fmtB, opsel,
        selA=0, selB=0, killA=0, killB=0, negB=0, negA=0,
        base4=0x01, marker=0x81, b6_extra=0, b5_extra=0):
    """Build the 8-byte bfloat/half ALU instruction from the rule above."""
    return bytes([
        ((dst & 0xF) << 4) | 0x01,
        ((srcA_reg & 0x7F) << 1) | (fmtA & 1),
        opsel & 0xFF,
        ((srcB_reg & 0x7F) << 1) | (fmtB & 1),
        (base4 | ((selA & 1) << 3) | ((selB & 1) << 4)) & 0xFF,
        ((killA & 1) | ((killB & 1) << 1) | ((negB & 1) << 3) | b5_extra) & 0xFF,
        (0xC0 | ((negA & 1) << 1) | b6_extra) & 0xFF,
        marker & 0xFF,
    ])

def bf10(dst, srcA_reg, fmtA, srcB_reg, fmtB, srcC_reg, fmtC,
         b4=0x86, b6=0x10, b7=0x00, negA=0, negB=0, marker=0x81):
    """Build the PREDICTED 10-byte bfloat fma from the rule above."""
    return bytes([
        ((dst & 0xF) << 4) | 0x01,
        ((srcA_reg & 0x7F) << 1) | (fmtA & 1),
        FMA,
        ((srcB_reg & 0x7F) << 1) | (fmtB & 1),
        b4 & 0xFF,
        ((srcC_reg & 0x7F) << 1) | (fmtC & 1),
        b6 & 0xFF,
        b7 & 0xFF,
        (0xC0 | ((negA & 1) << 1)) & 0xFF,
        marker & 0xFF,
    ])
