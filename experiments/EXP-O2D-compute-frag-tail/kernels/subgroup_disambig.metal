#include <metal_stdlib>
using namespace metal;

// Disambiguate the 0xbf reduce op-select: compare float sum/product/min/max and
// int and/or so we can read byte+1 (op) and byte+7 (dtype) unambiguously.
kernel void rf_sum(device float* o [[buffer(0)]], device const float* v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) { o[i] = simd_sum(v[i]); }
kernel void rf_prod(device float* o [[buffer(0)]], device const float* v [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) { o[i] = simd_product(v[i]); }
kernel void rf_min(device float* o [[buffer(0)]], device const float* v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) { o[i] = simd_min(v[i]); }
kernel void rf_max(device float* o [[buffer(0)]], device const float* v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) { o[i] = simd_max(v[i]); }
kernel void ru_and(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) { o[i] = simd_and(v[i]); }
kernel void ru_or(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) { o[i] = simd_or(v[i]); }
kernel void ru_xor(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) { o[i] = simd_xor(v[i]); }
kernel void ru_max(device uint* o [[buffer(0)]], device const uint* v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) { o[i] = simd_max(v[i]); }
// prefix product float exclusive vs inclusive (native scan)
kernel void pf_excl_prod(device float* o [[buffer(0)]], device const float* v [[buffer(1)]],
                         uint i [[thread_position_in_grid]]) { o[i] = simd_prefix_exclusive_product(v[i]); }
kernel void pf_incl_prod(device float* o [[buffer(0)]], device const float* v [[buffer(1)]],
                         uint i [[thread_position_in_grid]]) { o[i] = simd_prefix_inclusive_product(v[i]); }
kernel void pf_excl_sum(device float* o [[buffer(0)]], device const float* v [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) { o[i] = simd_prefix_exclusive_sum(v[i]); }
