#include <metal_stdlib>
using namespace metal;

kernel void k_main(device float *out [[buffer(0)]],
                   device const float *input [[buffer(1)]],
                   constant uint &n [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    float a[8];
    for (uint i = 0u; i < 8u; ++i) a[i] = input[((gid) * 8u + i) % 4096u];
    for (uint pass = 1u; pass < n; ++pass) {
        float t = input[pass % 4096u];
        for (uint i = 0u; i < 8u; ++i) a[i] = 0.5f * a[i] + 0.5f * a[(i + 1u) % 8u] + t * 1e-6f;
    }
    float sum = 0.0f;
    for (uint i = 0u; i < 8u; ++i) sum += a[i];
    out[gid] = sum;
}
