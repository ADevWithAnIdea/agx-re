#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], constant int* a [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid];
}
