#include <metal_stdlib>
using namespace metal;
kernel void k(device int2* out [[buffer(0)]], device const int2* a [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid];
}
