#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    uint s = 0;
    for (int j=0; j<20; ++j) s += a[gid + j*37];   // 20 INDEPENDENT loads, no inter-dependency
    out[gid] = s;
}
