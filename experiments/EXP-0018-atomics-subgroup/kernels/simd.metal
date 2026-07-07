#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------------------
// EXP-0018 subgroup / SIMD-group op provocation + semantics kernels (OUR MSL).
// Each kernel isolates ONE op and writes the per-lane result to o[i]. We feed
// lane i a DISTINCT known value in[i] and read back o[i] to PROVE semantics on
// hardware directly (OWN-SHADER + HW-PROBE; no splice needed to observe).
// ---------------------------------------------------------------------------

// ---- SIMD width probes ----
kernel void s_width_sr(device uint* o [[buffer(2)]],
                       uint i [[thread_position_in_grid]],
                       uint w [[threads_per_simdgroup]]) {
    o[i] = w;                                  // threads_per_simdgroup special reg
}
kernel void s_laneid(device uint* o [[buffer(2)]],
                     uint i [[thread_position_in_grid]],
                     uint lane [[thread_index_in_simdgroup]]) {
    o[i] = lane;                               // per-lane SIMD lane index
}
kernel void s_sum1(device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = simd_sum(1);                        // = active-lane count (width if full)
}

// ---- broadcast ----
kernel void s_bcast0(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                     uint i [[thread_position_in_grid]]) {
    o[i] = simd_broadcast(in[i], 0);           // all lanes <- in[lane0]
}
kernel void s_bcast5(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                     uint i [[thread_position_in_grid]]) {
    o[i] = simd_broadcast(in[i], 5);           // all lanes <- in[lane5]
}
kernel void s_bcast_first(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                          uint i [[thread_position_in_grid]]) {
    o[i] = simd_broadcast_first(in[i]);        // all lanes <- in[first active]
}

// ---- shuffle family ----
kernel void s_shuf_xor1(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                        uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_xor(in[i], 1);         // o[i] = in[lane^1]
}
kernel void s_shuf_lane(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                        uint i [[thread_position_in_grid]],
                        uint lane [[thread_index_in_simdgroup]]) {
    o[i] = simd_shuffle(in[i], lane ^ 1);      // dynamic index shuffle
}
kernel void s_shuf_up1(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                       uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_up(in[i], 1);          // o[i] = in[lane-1]
}
kernel void s_shuf_down1(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_down(in[i], 1);        // o[i] = in[lane+1]
}
kernel void s_rot_up1(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                      uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_rotate_up(in[i], 1);   // rotating up
}
kernel void s_rot_down1(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                        uint i [[thread_position_in_grid]]) {
    o[i] = simd_shuffle_rotate_down(in[i], 1); // rotating down
}

// ---- reductions ----
kernel void s_sum(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = simd_sum(in[i]);
}
kernel void s_prod(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = simd_product(in[i]);
}
kernel void s_min(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = simd_min(in[i]);
}
kernel void s_max(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = simd_max(in[i]);
}
kernel void s_and(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = simd_and(in[i]);
}
kernel void s_or(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                 uint i [[thread_position_in_grid]]) {
    o[i] = simd_or(in[i]);
}
kernel void s_xor(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = simd_xor(in[i]);
}
kernel void s_fsum(device float* in [[buffer(1)]], device float* o [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = simd_sum(in[i]);                    // float reduction
}

// ---- prefix scans ----
kernel void s_prefix_inc(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = simd_prefix_inclusive_sum(in[i]);   // o[i] = sum(in[0..i])
}
kernel void s_prefix_exc(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = simd_prefix_exclusive_sum(in[i]);   // o[i] = sum(in[0..i-1])
}
kernel void s_prefix_prod(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                          uint i [[thread_position_in_grid]]) {
    o[i] = simd_prefix_inclusive_product(in[i]);
}

// ---- ballot / vote / elect ----
kernel void s_ballot(device int* in [[buffer(1)]], device uint* o [[buffer(2)]],
                     uint i [[thread_position_in_grid]]) {
    simd_vote v = simd_ballot(in[i] > 0);
    o[i] = uint((simd_vote::vote_t)v);         // low 32 bits of the ballot mask
}
kernel void s_all(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = simd_all(in[i] > 0) ? 1 : 0;
}
kernel void s_any(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = simd_any(in[i] > 0) ? 1 : 0;
}
kernel void s_is_first(device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = simd_is_first() ? 1 : 0;            // active-lane elect
}
kernel void s_active_mask(device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    simd_vote v = simd_active_threads_mask();
    o[i] = uint((simd_vote::vote_t)v);         // active-lane mask
}
