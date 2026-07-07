#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* a [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid];
}
