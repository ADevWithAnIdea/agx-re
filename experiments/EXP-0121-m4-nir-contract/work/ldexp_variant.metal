#include <metal_stdlib>
using namespace metal;
kernel void k_ldexp_uniform_n(device float* x [[buffer(0)]], constant int &n [[buffer(1)]],
                               device float* out [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = ldexp(x[gid], n);
}
kernel void k_ldexp_minimal(device float* x [[buffer(0)]], device int* n [[buffer(1)]],
                             device float* out [[buffer(2)]]) {
    out[0] = ldexp(x[0], n[0]);
}
