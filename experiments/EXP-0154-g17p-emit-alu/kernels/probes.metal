// EXP-0154 anchor-probe kernels (ALL authored by us for this experiment).
//
// Each kernel is the smallest MSL we could write that makes the Apple compiler
// emit ONE instruction of a family we need an anchor for. We never inspect
// Apple's compiler; we compile our own source through the public runtime API
// (`newLibraryWithSource:` via tools/shdump) and read the AGX bytes it produced
// from OUR source. The bytes of the target instruction are then lifted verbatim
// into a synthesized program (harness/isa_helpers.py) so that every operand it
// names is a register WE seeded.
//
// Shapes are deliberately similar to EXP-0139/EXP-0146 probe kernels (same
// project, same rules) so that the anchors are comparable across targets; the
// files here are authored fresh for this experiment.
//
// CLEAN-ROOM: OWN-SHADER. No Apple binary is disassembled or introspected.
#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------- integer ---

kernel void k_u64add(device const ulong* a [[buffer(0)]],
                     device const ulong* b [[buffer(1)]],
                     device ulong* out [[buffer(2)]],
                     uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + b[g];                    // iadd2 (64-bit) + carry_gen + psel
}

kernel void k_u64sub(device const ulong* a [[buffer(0)]],
                     device const ulong* b [[buffer(1)]],
                     device ulong* out [[buffer(2)]],
                     uint g [[thread_position_in_grid]]) {
    out[g] = a[g] - b[g];
}

kernel void k_u32add(device const uint* a [[buffer(0)]],
                     device const uint* b [[buffer(1)]],
                     device uint* out [[buffer(2)]],
                     uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + b[g];                    // iadd2 (32-bit form)
}

kernel void k_and(device const uint* a [[buffer(0)]],
                  device const uint* b [[buffer(1)]],
                  device uint* out [[buffer(2)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = a[g] & b[g];                    // ilogic
}

kernel void k_or(device const uint* a [[buffer(0)]],
                 device const uint* b [[buffer(1)]],
                 device uint* out [[buffer(2)]],
                 uint g [[thread_position_in_grid]]) {
    out[g] = a[g] | b[g];
}

kernel void k_xor(device const uint* a [[buffer(0)]],
                  device const uint* b [[buffer(1)]],
                  device uint* out [[buffer(2)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = a[g] ^ b[g];
}

kernel void k_rot_imm(device const uint* a [[buffer(0)]],
                      device uint* out [[buffer(1)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = rotate(a[g], 5u);               // irotate
}

kernel void k_rot_var(device const uint* a [[buffer(0)]],
                      device const uint* b [[buffer(1)]],
                      device uint* out [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = rotate(a[g], b[g]);             // shift_amt_move + irotate
}

kernel void k_zext16(device const uint* a [[buffer(0)]],
                     device uint* out [[buffer(1)]],
                     uint g [[thread_position_in_grid]]) {
    ushort s = ushort(a[g]);
    out[g] = uint(s);                        // mov_zext16
}

kernel void k_bfe(device const uint* a [[buffer(0)]],
                  device uint* out [[buffer(1)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = extract_bits(a[g], 4, 8);       // ibfe
}

kernel void k_bfi(device const uint* a [[buffer(0)]],
                  device const uint* b [[buffer(1)]],
                  device uint* out [[buffer(2)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = insert_bits(a[g], b[g], 4, 8);  // ibfins
}

kernel void k_ashr(device const int* a [[buffer(0)]],
                   device int* out [[buffer(1)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] >> 2;                      // ishift (arithmetic, immediate)
}

kernel void k_shr_var(device const int* a [[buffer(0)]],
                      device const uint* b [[buffer(1)]],
                      device int* out [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = a[g] >> b[g];                   // ishift (variable amount)
}

kernel void k_imin(device const int* a [[buffer(0)]],
                   device const int* b [[buffer(1)]],
                   device int* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = min(a[g], b[g]);                // iminmax (imin)
}

kernel void k_umax(device const uint* a [[buffer(0)]],
                   device const uint* b [[buffer(1)]],
                   device uint* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = max(a[g], b[g]);                // iminmax (umax)
}

kernel void k_isel(device const int* a [[buffer(0)]],
                   device const int* b [[buffer(1)]],
                   device int* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = (a[g] < b[g]) ? (a[g] + 7) : (b[g] + 11);   // icmpsel / isel*
}

kernel void k_isel_small(device const int* a [[buffer(0)]],
                         device const int* b [[buffer(1)]],
                         device int* out [[buffer(2)]],
                         uint g [[thread_position_in_grid]]) {
    out[g] = (a[g] < b[g]) ? a[g] : b[g];
}

kernel void k_imad(device const int* a [[buffer(0)]],
                   device const int* b [[buffer(1)]],
                   device int* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] * b[g] + 12345;            // imad
}

kernel void k_loopcmp(device const int* a [[buffer(0)]],
                      device const int* b [[buffer(1)]],
                      device int* out [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    int acc = 0;
    int n = a[g];
    // A data-dependent loop defeats if-conversion, so the compare has to
    // materialize as a predicate-setting instruction (icmp_pred).
    for (int i = 0; i < n; ++i) acc += b[g] + i;
    out[g] = acc;
}

// ------------------------------------------------------------------ float ---

kernel void k_sat_add(device const float* a [[buffer(0)]],
                      device const float* b [[buffer(1)]],
                      device float* out [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = saturate(a[g] + b[g]);          // falu2_ext (8-byte)
}

kernel void k_abs_add(device const float* a [[buffer(0)]],
                      device const float* b [[buffer(1)]],
                      device float* out [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = fabs(a[g]) + fabs(b[g]);        // falu2_srcmod10 (10-byte)
}

kernel void k_fma(device const float* a [[buffer(0)]],
                  device const float* b [[buffer(1)]],
                  device float* out [[buffer(2)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = fma(a[g], b[g], a[g + 1]);      // falu3 (8-byte)
}

kernel void k_sat_fma(device const float* a [[buffer(0)]],
                      device const float* b [[buffer(1)]],
                      device float* out [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = saturate(fma(a[g], b[g], a[g + 1]));   // falu3_ext (10-byte)
}

kernel void k_fma_abs(device const float* a [[buffer(0)]],
                      device const float* b [[buffer(1)]],
                      device float* out [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = fma(fabs(a[g]), b[g], a[g + 1]);       // falu3_srcmod12 (12-byte)
}

kernel void k_sum(device const float* a [[buffer(0)]],
                  device float* out [[buffer(1)]],
                  uint g [[thread_position_in_grid]]) {
    float s = 0.0f;                          // falu_acc (compact 4-byte adds)
    for (uint i = 0; i < 10u; ++i) s += a[g + i];
    out[g] = s;
}

kernel void k_uni(device float* out [[buffer(0)]],
                  constant float4& u [[buffer(1)]],
                  device const float* a [[buffer(2)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + u.x + u.y;               // falu2_uni
}

kernel void k_half2(device const half2* a [[buffer(0)]],
                    device const half2* b [[buffer(1)]],
                    device half2* out [[buffer(2)]],
                    uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + b[g];                    // half_alu + half_pack
}

kernel void k_rsqrt(device const float* a [[buffer(0)]],
                    device float* out [[buffer(1)]],
                    uint g [[thread_position_in_grid]]) {
    out[g] = rsqrt(a[g]);                    // fspecial / fspecial_est
}
