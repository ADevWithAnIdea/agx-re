#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* a [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    int v = a[gid]; if (v > 10) v = v - 10; out[gid] = v;
}
