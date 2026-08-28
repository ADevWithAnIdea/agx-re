#include <metal_stdlib>
using namespace metal;

kernel void k_main(device float *out [[buffer(0)]],
                   device const float *input [[buffer(1)]],
                   constant uint &n [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    float sum = input[gid % 4096u];
    for (uint pass = 1u; pass < n; ++pass) sum = 0.5f * sum + 0.5f * input[pass % 4096u];
    out[gid] = sum;
}
