// EXP-0138 pilot anchor probes. OWN MSL. Purpose: obtain byte-exact,
// compiler-emitted instances of each float-ALU family we intend to sweep,
// so each sweep starts from a KNOWN-GOOD encoding rather than a guess.
#include <metal_stdlib>
using namespace metal;
kernel void k_fma(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                  uint t [[thread_position_in_grid]]) {
    out[t] = fma(a[t+0], a[t+1], a[t+2]);
}
kernel void k_copysign(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    out[t] = copysign(a[t+0], a[t+1]);
}
kernel void k_hadd(device half* out [[buffer(0)]], device half* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) {
    out[t] = a[t+0] + a[t+1];
}
kernel void k_hsat(device half* out [[buffer(0)]], device half* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) {
    out[t] = saturate(a[t+0] + a[t+1]);
}
kernel void k_rsqrt(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                    uint t [[thread_position_in_grid]]) {
    out[t] = rsqrt(a[t+0]);
}
kernel void k_sum(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                  uint t [[thread_position_in_grid]]) {
    float s = 0.0f;
    for (uint i = 0; i < 10u; ++i) s += a[t+i];
    out[t] = s;
}
kernel void k_abs2(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) {
    out[t] = fabs(a[t+0]) + fabs(a[t+1]);
}
kernel void k_sat2(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) {
    out[t] = saturate(a[t+0] - a[t+1]);
}
kernel void k_fmaabs(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    out[t] = fma(fabs(a[t+0]), a[t+1], a[t+2]);
}
