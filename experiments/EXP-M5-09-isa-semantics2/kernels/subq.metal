// EXP-M5-09: Subgroup/quad reduce/shuffle/prefix provocations on M5. Map the op selector
// on the 0x2f-lowered / 0x3f / 0xbf families. CLEAN-ROOM: OUR OWN MSL; one op per kernel.
#include <metal_stdlib>
using namespace metal;

kernel void s_sum(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) { o[i] = simd_sum(a[i]); }
kernel void s_prod(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) { o[i] = simd_product(a[i]); }
kernel void s_min(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) { o[i] = simd_min(a[i]); }
kernel void s_max(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) { o[i] = simd_max(a[i]); }
kernel void s_and(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) { o[i] = simd_and(a[i]); }
kernel void s_or(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                 uint i [[thread_position_in_grid]]) { o[i] = simd_or(a[i]); }
kernel void s_xor(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) { o[i] = simd_xor(a[i]); }
kernel void s_prefix(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) { o[i] = simd_prefix_inclusive_sum(a[i]); }
kernel void s_prefixx(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                      uint i [[thread_position_in_grid]]) { o[i] = simd_prefix_exclusive_sum(a[i]); }
kernel void s_shuffle(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                      uint i [[thread_position_in_grid]]) { o[i] = simd_shuffle(a[i], 0); }
kernel void s_bcast(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) { o[i] = simd_broadcast_first(a[i]); }
kernel void q_sum(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) { o[i] = quad_sum(a[i]); }
kernel void q_max(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) { o[i] = quad_max(a[i]); }
kernel void q_shuffle(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                      uint i [[thread_position_in_grid]]) { o[i] = quad_shuffle(a[i], 1); }
kernel void q_shxor(device const uint *a [[buffer(0)]], device uint *o [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) { o[i] = quad_shuffle_xor(a[i], 1); }
