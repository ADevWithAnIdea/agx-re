#include <metal_stdlib>
using namespace metal;

// EXP-0034 texture-atomics probe. Metal/MSL is expected to REJECT image atomics
// (no atomic methods on texture types). We compile these to CAPTURE the exact
// rejection for the capability matrix. Each is compiled independently; a compile
// failure is the datum. Clean-room: OUR OWN MSL.

// candidate A: atomic_fetch_add method on a read_write texture (does not exist)
kernel void a_add(texture2d<uint, access::read_write> t [[texture(0)]],
                  uint i [[thread_position_in_grid]]) {
    t.atomic_fetch_add(uint2(i & 3, i >> 2), 1u);
}

// candidate B: texture_buffer atomic (does not exist)
kernel void a_buf(texture_buffer<uint, access::read_write> t [[texture(0)]],
                  uint i [[thread_position_in_grid]]) {
    t.atomic_fetch_add(i, 1u);
}
