#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* a [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    int s = 0; for (uint i = 0; i < uint(a[gid]); i++) s += int(i); out[gid] = s;
}
