#include <metal_stdlib>
using namespace metal;

// EXP-0034 texture-atomics HW validation kernels (r32uint). Metal ACCEPTS these
// (contrary to expectation). We validate they actually run and are atomic under
// contention. Clean-room: OUR OWN MSL.

// distinct texel per thread: after 16 threads each texel == its initial + 1
kernel void at_distinct(texture2d<uint, access::read_write> t [[texture(0)]],
                        uint i [[thread_position_in_grid]]) {
    t.atomic_fetch_add(uint2(i & 3, i >> 2), 1u);
}

// CONTENDED: every thread adds 1 to texel (0,0). If atomic, texel(0,0)==N_threads.
kernel void at_contend(texture2d<uint, access::read_write> t [[texture(0)]],
                       uint i [[thread_position_in_grid]]) {
    t.atomic_fetch_add(uint2(0, 0), 1u);
}

// atomic max: each thread writes max(texel, i). texel(0,0) should end == max i.
kernel void at_max(texture2d<uint, access::read_write> t [[texture(0)]],
                   uint i [[thread_position_in_grid]]) {
    t.atomic_fetch_max(uint2(0, 0), i);
}
