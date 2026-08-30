// EXP-0184 copysign carriers (AUTHORED BY US; clean-room OWN-SHADER).
//
// TARGET FIELD: `copysign.operands` = byte+3 of the 4-byte `07 c2 88 xx`.
// SECOND FIELD SWEPT ON THE SAME CARRIERS: byte+1 (`0xc2`) and byte+2 (`0x88`),
// which `db.json` models as FIXED MATCH CONSTANTS. EXP-0138 (M4) reported that
// byte+1 is in fact a LIVE operand field (240/256 silent zero, 8 -> -5.0,
// 8 -> +5.0) and byte+2 a 256/256 don't-care. Sweeping byte+1 here is
// simultaneously (a) this arm's detection-power control -- it must move, or the
// arm cannot support an inert verdict on byte+3 -- and (b) the G17P
// confirmation of an M4-only db defect.
//
// WHY FIVE KERNELS. EXP-0164 withheld `operands` because exactly ONE carrier
// was ever tried and nothing moved on it: a probe that cannot show liveness
// either way. The dimension the field is *modelled* to control is the
// source/destination operand descriptor, so the carriers below differ in
// OPERAND PROVENANCE and REGISTER PRESSURE -- the two things that change which
// registers the compiler puts the operands in, and (EXP-0129, HW) the axis on
// which Apple9 operand behaviour genuinely differs: an ALU-seeded operand and a
// device_load-seeded operand do NOT behave alike.
//
//   k_cs_load   both operands straight from memory        (load-sourced)
//   k_cs_alu    both operands computed by preceding ALU   (ALU-sourced)
//   k_cs_mix    one of each                               (mixed provenance)
//   k_cs_two    two copysigns with swapped operands       (two occurrences,
//                                                          different allocation)
//   k_cs_chain  result consumed by a following ALU op     (result-routing mode)
//
// ORACLE (host-computed from THIS source, never from a GPU output). The inputs
// are chosen so that for every lane the correct answer differs from a[t], from
// |a[t]|, from b[t] and from |b[t]|, and is NEVER ZERO -- on Apple9 a wrong
// field value usually yields a silent zero, and a zero oracle would score that
// silent zero as a pass.
//
//   a = [ 5.0, -5.0,  3.25, -3.25,  9.5, -9.5,  1.75, -1.75]
//   b = [-2.0,  2.0, -8.0,   8.0,  -0.5,  0.5, -6.0,   6.0 ]
//   copysign(a,b) = [-5.0, 5.0, -3.25, 3.25, -9.5, 9.5, -1.75, 1.75]
//
// out[8] is an INTEGRITY SENTINEL written BEFORE the tested instruction through
// a path the instruction cannot name; out[9..15] are never stored to and must
// stay POISON (0xDEADBEEF+i).
#include <metal_stdlib>
using namespace metal;

#define SENT out[8] = 7.5f;      /* written first, independent of the copysign */

kernel void k_cs_load(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = copysign(a[t], b[t]);
}

kernel void k_cs_alu(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     device const float *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    float x = a[t] * 2.0f;        // ALU-sourced magnitude
    float y = b[t] + 0.0f;        // ALU-sourced sign source
    out[t] = copysign(x, y);
}

kernel void k_cs_mix(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     device const float *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = copysign(a[t] * 4.0f, b[t]);
}

kernel void k_cs_two(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     device const float *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = copysign(a[t], b[t]) * 16.0f + copysign(b[t], a[t]);
}

kernel void k_cs_chain(device float *out [[buffer(0)]],
                       device const float *a [[buffer(1)]],
                       device const float *b [[buffer(2)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    float c = copysign(a[t], b[t]);
    out[t] = c * 4.0f + 1.0f;
}
