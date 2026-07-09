#include <metal_stdlib>
using namespace metal;
// Bulk copy of contiguous uint4 blocks — coalesced wide load/store pattern.
kernel void k(device uint4* dst [[buffer(0)]],
              device const uint4* src [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    uint base = i * 4u;
    dst[base+0] = src[base+0];
    dst[base+1] = src[base+1];
    dst[base+2] = src[base+2];
    dst[base+3] = src[base+3];
}
