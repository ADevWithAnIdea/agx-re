#include <metal_stdlib>
using namespace metal;
// volatile device pointer — defeats coalescing/reordering; each access must be
// a distinct memory op, exposing the un-optimized load/store encoding.
kernel void k(volatile device uint* out [[buffer(0)]],
              volatile device const uint* in [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    uint a = in[i];
    uint b = in[i];      // must re-load (volatile)
    out[i] = a;
    out[i] = a + b;      // must re-store (volatile)
}
