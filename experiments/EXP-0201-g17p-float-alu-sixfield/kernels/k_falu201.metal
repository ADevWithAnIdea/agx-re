// EXP-0201 float-ALU carriers (AUTHORED BY US; clean-room OWN-SHADER).
//
// One file, five instruction families, eleven kernels. Every kernel exists to
// put ONE target instruction into the compiled `_agc.main` of OUR OWN source on
// a path the read-back can observe.
//
// TARGET FIELDS
//   falu3.op            bits 16..23  (byte+2 of the 8-byte fma)
//   falu3_ext.op        bits 16..23  (byte+2 of the 10-byte saturating fma)
//   fspecial_est.srcA   bits  8..15  (byte+1 of the 6-byte NR seed op)
//   falu3_srcmod12.opsel bits 16..18 (overlaps its own match bit 17 -- see below)
//   falu3_srcmod12.ctrl  bits 32..38 (byte+4, low 2 bits are the LENGTH selector)
//   copysign.operands   bits 24..31  (byte+3 of `07 c2 88 xx`)
//
// WHY MORE THAN ONE KERNEL PER FIELD. The two `op` fields were withheld as
// UNSTABLE on ONE arm each (428 and 450 observations moved -- liveness is not in
// question, reproducibility is). `fspecial_est.srcA` was withheld with 1 moved
// observation over 4 arms, which is a DETECTION-POWER problem, not an
// instability one. So each field gets several carriers that differ in the
// dimension the field is modelled to control -- operand provenance, result
// routing, and (for the estimate) whether a second live float of a very
// different magnitude sits in the register file across the instruction.
//
// ORACLE. Every oracle is computed on the HOST from THIS source (see
// harness/carriers201.py), never from a GPU output, and is a per-value
// prediction from a CANDIDATE FUNCTION LIBRARY -- never a constant. A constant
// oracle across a varying field predicts the instruction's effect, not the
// field's; that is exactly what left `copysign.operands` at `untested` after a
// full 256-value, 256-distinct-encoding sweep on the M4.
//
// POISON + SENTINEL. Buffer 0 is bound to a file pre-filled with
// POISON(i) = 0xDEADBEEF + i, so an unwritten word is distinguishable from a
// genuine silent zero. out[8] is an integrity sentinel written FIRST through a
// path independent of the instruction under test; out[9..15] are never stored
// to and must stay poison.
#include <metal_stdlib>
using namespace metal;

#define SENT out[8] = 7.5f;

// ---------------------------------------------------------------- falu3 (fma)
// `fma(a,b,c)` with --no-fast-math lowers to the 8-byte falu3 (`09 xx 1e ...`).
kernel void k_f3_fma(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     device const float *b [[buffer(2)]],
                     device const float *c [[buffer(3)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = fma(a[t], b[t], c[t]);
}

// Result routing differs: the fma feeds a following ALU op instead of a store.
// This is the arm on which a srcB RELEASE flag can be visible at all, because a
// later instruction reads the register the fma read.
kernel void k_f3_chain(device float *out [[buffer(0)]],
                       device const float *a [[buffer(1)]],
                       device const float *b [[buffer(2)]],
                       device const float *c [[buffer(3)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    float r = fma(a[t], b[t], c[t]);
    out[t] = fma(r, 0.5f, b[t]);          // b[t] read AFTER the tested fma
}

// Two independent fmas over the same inputs: two occurrences, two allocations.
kernel void k_f3_two(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     device const float *b [[buffer(2)]],
                     device const float *c [[buffer(3)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = fma(a[t], b[t], c[t]) * 0.5f + fma(c[t], a[t], b[t]) * 0.25f;
}

// ------------------------------------------------------- falu3_ext (sat fma)
// `saturate(fma(..))` lowers to the 10-byte extended form (`... 82 08 02 00 00 82`).
// Inputs for these carriers are chosen so the six candidate functions stay
// pairwise distinct AFTER clamping to [0,1] -- a saturating carrier whose
// predictions all clamp together would be a constant oracle.
kernel void k_f3e_sat(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      device const float *c [[buffer(3)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = saturate(fma(a[t], b[t], c[t]));
}

kernel void k_f3e_chain(device float *out [[buffer(0)]],
                        device const float *a [[buffer(1)]],
                        device const float *b [[buffer(2)]],
                        device const float *c [[buffer(3)]],
                        uint t [[thread_position_in_grid]]) {
    SENT
    float r = saturate(fma(a[t], b[t], c[t]));
    out[t] = fma(r, 0.5f, 0.25f);
}

// A third saturating-fma occurrence set. The two `op` fields were withheld with
// exactly ONE arm each, so a second and third independent arm is the deficiency
// being fixed, not more values.
kernel void k_f3e_two(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      device const float *c [[buffer(3)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = saturate(fma(a[t], b[t], c[t]))
           + saturate(fma(c[t], a[t], b[t])) * 0.125f;
}

// ------------------------------------------------- falu3_srcmod12 (12B abs fma)
// `db.json`: "abs promotes to the 12B falu3_srcmod12 form". The 12-byte form is
// the fma with a source ABS modifier.
kernel void k_f12_abs(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      device const float *c [[buffer(3)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = fma(fabs(a[t]), b[t], c[t]);
}

kernel void k_f12_abs2(device float *out [[buffer(0)]],
                       device const float *a [[buffer(1)]],
                       device const float *b [[buffer(2)]],
                       device const float *c [[buffer(3)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = fma(fabs(a[t]), fabs(b[t]), c[t]);
}

// ------------------------------------------------------------- fspecial_est
// `precise::` (with --no-fast-math) selects the Newton-Raphson lowering whose
// SEED is the 6-byte `fspecial_est`, rather than the single-op SFU.
//
// b[t] is a SECOND LIVE FLOAT of a very different magnitude, stored AFTER the
// estimate so it is live across it. That is the whole point of these carriers:
// `srcA` was withheld with 1 moved observation over 4 arms, which is a
// detection-power problem. If the estimate is seeded from the wrong register,
// the refinement cannot rescue it when the two magnitudes are orders apart.
kernel void k_fsp_rsqrt(device float *out [[buffer(0)]],
                        device const float *a [[buffer(1)]],
                        device const float *b [[buffer(2)]],
                        uint t [[thread_position_in_grid]]) {
    SENT
    float y = b[t];
    out[t] = precise::rsqrt(a[t]);
    out[16 + t] = y + 0.125f;             // keeps y live across the estimate
}

kernel void k_fsp_rcp(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    float y = b[t];
    out[t] = precise::divide(1.0f, a[t]);
    out[16 + t] = y + 0.125f;
}

kernel void k_fsp_sqrt(device float *out [[buffer(0)]],
                       device const float *a [[buffer(1)]],
                       device const float *b [[buffer(2)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    float y = b[t];
    out[t] = precise::sqrt(a[t]);
    out[16 + t] = y + 0.125f;
}

// Two estimates of two different live values in one kernel: if `srcA` selects
// the source register, the two occurrences must disagree about which one they
// read, and the host can name both candidate answers.
kernel void k_fsp_two(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    float p = precise::rsqrt(a[t]);
    float q = precise::rsqrt(b[t]);
    out[t] = p;
    out[16 + t] = q;
}

// ------------------------------------------------------------------ copysign
// `copysign(x,y)` (float) compiles to the 4-byte `07 c2 88 xx`.
//
// The inputs (harness/carriers201.py) are ASYMMETRIC and one lane of the sign
// source is -0.0, so that copysign(a,b), copysign(b,a), a, b, |a|, |b|, -a, -b,
// -|a|, -|b|, 0, a*b and a+b are thirteen PAIRWISE-DISTINCT 8-lane vectors. Two
// lanes deliberately have sign(a) == sign(b), because with all signs opposite
// copysign(a,b) collides with -a and the library stops discriminating.
kernel void k_cs_load(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = copysign(a[t], b[t]);
}

// The SAME instruction with the operand ROLES EXCHANGED -- the dimension
// `operands` is modelled to control. Two carriers identical in the dimension the
// field controls are one carrier.
kernel void k_cs_swap(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = copysign(b[t], a[t]);
}

kernel void k_cs_alu(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     device const float *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    float x = a[t] * 2.0f;                // ALU-sourced magnitude
    float y = b[t] + 0.0f;                // ALU-sourced sign source
    out[t] = copysign(x, y);
}

kernel void k_cs_chain(device float *out [[buffer(0)]],
                       device const float *a [[buffer(1)]],
                       device const float *b [[buffer(2)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    float r = copysign(a[t], b[t]);
    out[t] = fma(r, 4.0f, 1.0f);
}
