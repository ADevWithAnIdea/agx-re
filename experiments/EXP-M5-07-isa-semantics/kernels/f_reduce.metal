#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]], device float* out [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    float s = 0.0f;
    for (uint i=0;i<4;i++) s += a[gid*4+i] * a[gid*4+i];
    out[gid] = s;
}
