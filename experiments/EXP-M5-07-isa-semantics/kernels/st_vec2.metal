#include <metal_stdlib>
using namespace metal;
kernel void k(device uint2* out [[buffer(0)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = uint2(gid, gid+100u);
}
