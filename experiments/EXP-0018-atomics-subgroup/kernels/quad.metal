#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------------------
// EXP-0018 quad-group op provocation + semantics kernels (OUR MSL).
// Quads are 4 consecutive lanes {0-3},{4-7},... Feed lane i distinct in[i],
// read o[i] to prove 2x2 quad semantics on hardware.
// ---------------------------------------------------------------------------

kernel void q_laneid(device uint* o [[buffer(2)]],
                     uint i [[thread_position_in_grid]],
                     uint q [[thread_index_in_quadgroup]]) {
    o[i] = q;                                  // per-lane quad index (0..3)
}
kernel void q_bcast0(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                     uint i [[thread_position_in_grid]]) {
    o[i] = quad_broadcast(in[i], 0);           // quad lanes <- in[quad-lane0]
}
kernel void q_bcast2(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                     uint i [[thread_position_in_grid]]) {
    o[i] = quad_broadcast(in[i], 2);           // quad lanes <- in[quad-lane2]
}
kernel void q_shuf_xor1(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                        uint i [[thread_position_in_grid]]) {
    o[i] = quad_shuffle_xor(in[i], 1);         // o[i] = in[qlane^1]
}
kernel void q_shuf_lane(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                        uint i [[thread_position_in_grid]],
                        uint q [[thread_index_in_quadgroup]]) {
    o[i] = quad_shuffle(in[i], q ^ 2);
}
kernel void q_shuf_up1(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                       uint i [[thread_position_in_grid]]) {
    o[i] = quad_shuffle_up(in[i], 1);
}
kernel void q_shuf_down1(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = quad_shuffle_down(in[i], 1);
}
kernel void q_sum(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = quad_sum(in[i]);                     // sum over the 2x2 quad
}
kernel void q_max(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = quad_max(in[i]);
}
kernel void q_min(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = quad_min(in[i]);
}
kernel void q_and(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = quad_and(in[i]);
}
kernel void q_prefix_inc(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = quad_prefix_inclusive_sum(in[i]);
}
