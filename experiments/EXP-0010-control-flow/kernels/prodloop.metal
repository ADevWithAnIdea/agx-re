#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* a [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    int s = 1; int n = a[gid]; for (int i = 0; i < n; i++) { s = s*3 + 1; } out[gid] = s;
}
