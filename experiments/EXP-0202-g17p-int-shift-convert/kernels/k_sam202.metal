// EXP-0202 shift/rotate carriers (AUTHORED BY US; OWN-SHADER).
//
// TWO TARGET INSTRUCTIONS LIVE HERE.
//
// (1) `shift_amt_move.src_flag` -- bit 15 (= byte+1 bit 7) of the 4-byte compact
//     move that stages a shift/rotate amount. db.json types byte+1 as
//     src_reg(7) + src_flag(1) with enum 0=gpr / 1=uniform-class, INHERITED from
//     reg_move_c0 and never proven. EXP-0168 swept it on ONE carrier whose amount
//     came from a GPR and saw byte-identical register digests at both values at
//     all 13 sampled indices. That is the field's dimension held FIXED: if the bit
//     selects a FILE, a carrier that only ever uses one file cannot move.
//
//     So the carriers below differ in EXACTLY that dimension -- where the staged
//     amount comes from:
//       k_sam_gpr      amount = b[t]      per-thread device load  -> GPR
//       k_sam_uni      amount = sh        THREAD-INVARIANT        -> uniform class
//       k_sam_shl_uni  same, driving <<   (different `kind` nibble)
//       k_sam_shr_uni  same, driving >>
//       k_sam_uni2     TWO distinct thread-invariant amounts, so the uniform side
//                      holds two different known values at two different indices
//       k_sam_mix      one GPR amount and one uniform amount IN THE SAME PROGRAM,
//                      so both files are populated with values we chose and they
//                      are guaranteed unequal (2 vs 13)
//
// (2) `irotate.operands` -- the 40-bit operand blob of the 12-byte single-op
//     immediate rotate. It needs a SECOND ARM (EXP-0189 withheld it for having
//     one), so six constant amounts are compiled. The set {1,5,7,13,19,31} also
//     byte-diffs WHICH byte of `operands` carries the immediate, which is what
//     turns a "did it move" test into an EXACT per-value oracle.
//
// ORACLE: every expected value is computed on the host from these exact inputs by
// the same arithmetic, in Python. No expected value is 0.
//   a[t] = 0x8000000Bu + t*0x01234567u   (asymmetric, both halves populated)
//   b[t] = 1 + t*3 (mod 32)              (a different rotate amount per lane)
//   sh   = 13, sh2 = (5, 19)
//
// POISON: buffer 0 is pre-filled with 0xDEADBEEF+i by the harness, so a word that
// reads back as its own poison is UNWRITTEN rather than a silent zero.
// SENTINEL: out[8] = 12345, stored through a path independent of every
// instruction under test, and BEFORE it.
//
// CLEAN-ROOM: our own MSL. No Apple source consulted.
#include <metal_stdlib>
using namespace metal;

#define SENT out[8] = 12345u;

// ---------------------------------------------- shift_amt_move: file dimension
kernel void k_sam_gpr(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], b[t]);
}

kernel void k_sam_uni(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      constant uint &sh [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], sh);
}

kernel void k_sam_shl_uni(device uint *out [[buffer(0)]],
                          device const uint *a [[buffer(1)]],
                          constant uint &sh [[buffer(2)]],
                          uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = a[t] << (sh & 31u);
}

kernel void k_sam_shr_uni(device uint *out [[buffer(0)]],
                          device const uint *a [[buffer(1)]],
                          constant uint &sh [[buffer(2)]],
                          uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = a[t] >> (sh & 31u);
}

kernel void k_sam_uni2(device uint *out [[buffer(0)]],
                       device const uint *a [[buffer(1)]],
                       constant uint2 &sh2 [[buffer(2)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], sh2.x) ^ rotate(a[t], sh2.y);
}

// Both files populated in ONE program with values we chose and that differ.
kernel void k_sam_mix(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *b [[buffer(2)]],
                      constant uint &sh [[buffer(3)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], b[t]) ^ (rotate(a[t], sh) * 3u);
}

// ------------------------------------------------ irotate: immediate amount
kernel void k_rot_k1(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], 1u);
}

kernel void k_rot_k5(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], 5u);
}

kernel void k_rot_k7(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], 7u);
}

kernel void k_rot_k13(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], 13u);
}

kernel void k_rot_k19(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], 19u);
}

kernel void k_rot_k31(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], 31u);
}

// A rotate whose RESULT IS CONSUMED BY AN ALU op rather than stored -- the
// result-routing dimension, so `irotate` gets a second arm that differs in
// something other than the constant.
kernel void k_rot_alu(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], 5u) * 3u + 7u;
}

// Two immediate rotates by different amounts in one program: two occurrences.
kernel void k_rot_two(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], 5u) ^ (rotate(a[t], 19u) + 1u);
}
