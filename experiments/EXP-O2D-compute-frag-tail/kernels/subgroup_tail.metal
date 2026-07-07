#include <metal_stdlib>
using namespace metal;

// ============ Sub-experiment 4: subgroup tail ops ============
// New op-selects in the 0x47/0xc7 (shuffle) and 0xbf/0x3f (reduce/scan) families:
//  simd_shuffle_and_fill_up/down, the modulo/rotate variants,
//  simd_prefix_exclusive/inclusive_product, and simd_*_product reductions.

// ---- shuffle references (already decoded, EXP-0018) ----
kernel void sh_up(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_up(v[i], 1u);
}
kernel void sh_down(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_down(v[i], 1u);
}
kernel void sh_xor(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_xor(v[i], 1u);
}
// ---- shuffle-and-fill (new) ----
kernel void sh_fill_up(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                       device const uint* f [[buffer(2)]],
                       uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_and_fill_up(v[i], f[i], 1u);
}
kernel void sh_fill_down(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                         device const uint* f [[buffer(2)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_and_fill_down(v[i], f[i], 1u);
}
// ---- shuffle-and-fill modulo/rotate variants (new) ----
kernel void sh_fill_up_mod(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                           device const uint* f [[buffer(2)]],
                           uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_and_fill_up(v[i], f[i], 1u, 8u);
}
kernel void sh_fill_down_mod(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                             device const uint* f [[buffer(2)]],
                             uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_and_fill_down(v[i], f[i], 1u, 8u);
}

// ---- reductions: sum (ref) vs product (new op-select) ----
kernel void red_sum(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    o[i] = simd_sum(v[i]);
}
kernel void red_prod(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    o[i] = simd_product(v[i]);
}
kernel void red_prod_f(device float* o [[buffer(0)]], device const float* v [[buffer(1)]],
                       uint i [[thread_position_in_grid]]) {
    o[i] = simd_product(v[i]);
}

// ---- prefix scans: sum (ref) vs product (new) ----
kernel void pre_excl_sum(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = simd_prefix_exclusive_sum(v[i]);
}
kernel void pre_incl_sum(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = simd_prefix_inclusive_sum(v[i]);
}
kernel void pre_excl_prod(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                          uint i [[thread_position_in_grid]]) {
    o[i] = simd_prefix_exclusive_product(v[i]);
}
kernel void pre_incl_prod(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                          uint i [[thread_position_in_grid]]) {
    o[i] = simd_prefix_inclusive_product(v[i]);
}
kernel void pre_excl_prod_f(device float* o [[buffer(0)]], device const float* v [[buffer(1)]],
                            uint i [[thread_position_in_grid]]) {
    o[i] = simd_prefix_exclusive_product(v[i]);
}
