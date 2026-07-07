#include <metal_stdlib>
using namespace metal;
kernel void k(device short* out [[buffer(0)]], device const int* a [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = short(a[gid]);
}
