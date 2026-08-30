// EXP-0160 anchor-probe kernels (ALL authored by us for this experiment).
//
// Each kernel is the smallest MSL that makes the public Metal runtime compiler
// emit ONE instruction of the family we need an anchor for. We never inspect
// Apple's compiler or any Apple binary; we compile OUR OWN source through the
// public runtime API (`newLibraryWithSource:` via tools/shdump) and read the
// AGX bytes produced from that source. The target instruction's bytes are then
// lifted verbatim into a synthesized program (harness/isa_helpers.py) so every
// operand it names is a register WE seeded.
//
// k_sat_add / k_fma / k_sat_fma / k_imin / k_imad / k_half2 / k_rsqrt are the
// same one-line shapes EXP-0154 used (same project, same rules); re-authored
// here so this experiment is self-contained. k_addimm is new: EXP-0154 had no
// falu2i arm, so falu2i.ctrl_lo had no anchor.
//
// CLEAN-ROOM: OWN-SHADER. No Apple binary is disassembled or introspected.
#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------- integer ---

kernel void k_imin(device const int* a [[buffer(0)]],
                   device const int* b [[buffer(1)]],
                   device int* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = min(a[g], b[g]);                // iminmax (imin)
}

kernel void k_imad(device const int* a [[buffer(0)]],
                   device const int* b [[buffer(1)]],
                   device int* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] * b[g] + 12345;            // imad (mul + immediate addend)
}

kernel void k_half2(device const half2* a [[buffer(0)]],
                    device const half2* b [[buffer(1)]],
                    device half2* out [[buffer(2)]],
                    uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + b[g];                    // half_alu + half_pack
}

// ------------------------------------------------------------------ float ---

kernel void k_sat_add(device const float* a [[buffer(0)]],
                      device const float* b [[buffer(1)]],
                      device float* out [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = saturate(a[g] + b[g]);          // falu2_ext (8-byte)
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

kernel void k_rsqrt(device const float* a [[buffer(0)]],
                    device float* out [[buffer(1)]],
                    uint g [[thread_position_in_grid]]) {
    out[g] = rsqrt(a[g]);                    // fspecial_est + isel8
}

kernel void k_addimm(device const float* a [[buffer(0)]],
                     device float* out [[buffer(1)]],
                     uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + 3.0f;                    // falu2i (packed minifloat imm)
}
