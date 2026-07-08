#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]], device const uint* idx [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    uint i = gid;
    for (uint s=0; s<8; ++s) i = idx[i];   // each load's result indexes the next load (RAW chain)
    out[gid] = i;
}
