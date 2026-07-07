#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* a [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    int s = a[gid]; if (gid & 1u) { for (uint i = 0; i < 3u; i++) s += 10; } else { s -= 1; } out[gid] = s;
}
