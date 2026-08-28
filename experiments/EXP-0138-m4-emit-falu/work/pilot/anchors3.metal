// EXP-0138 pilot anchor probes, round 3 (fast-math single-op transcendentals). OWN MSL.
#include <metal_stdlib>
using namespace metal;
kernel void k_rsqrtf(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) { out[t] = rsqrt(a[t+0]); }
kernel void k_rcpf(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) { out[t] = 1.0f / a[t+0]; }
kernel void k_exp2f(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                    uint t [[thread_position_in_grid]]) { out[t] = exp2(a[t+0]); }
kernel void k_log2f(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                    uint t [[thread_position_in_grid]]) { out[t] = log2(a[t+0]); }
kernel void k_sqrtf(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                    uint t [[thread_position_in_grid]]) { out[t] = sqrt(a[t+0]); }
kernel void k_floorf(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) { out[t] = floor(a[t+0]); }
