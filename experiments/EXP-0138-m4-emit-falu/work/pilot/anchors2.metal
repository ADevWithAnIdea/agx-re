// EXP-0138 pilot anchor probes, round 2. OWN MSL.
#include <metal_stdlib>
using namespace metal;
kernel void k_add(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                  uint t [[thread_position_in_grid]]) { out[t] = a[t+0] + a[t+1]; }
kernel void k_mul(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                  uint t [[thread_position_in_grid]]) { out[t] = a[t+0] * a[t+1]; }
kernel void k_addi(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) { out[t] = a[t+0] + 3.0f; }
kernel void k_satabs(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) { out[t] = saturate(fabs(a[t+0]) + a[t+1]); }
kernel void k_satfma(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) { out[t] = saturate(fma(a[t+0], a[t+1], a[t+2])); }
kernel void k_min(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                  uint t [[thread_position_in_grid]]) { out[t] = min(a[t+0], a[t+1]); }
kernel void k_max(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                  uint t [[thread_position_in_grid]]) { out[t] = max(a[t+0], a[t+1]); }
kernel void k_uni(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                  constant float& u [[buffer(2)]], uint t [[thread_position_in_grid]]) { out[t] = a[t+0] + u; }
kernel void k_unimul(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     constant float& u [[buffer(2)]], uint t [[thread_position_in_grid]]) { out[t] = a[t+0] * u; }
kernel void k_hfmaabs(device half* out [[buffer(0)]], device half* a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) { out[t] = fma(fabs(a[t+0]), a[t+1], a[t+2]); }
kernel void k_hfma(device half* out [[buffer(0)]], device half* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) { out[t] = fma(a[t+0], a[t+1], a[t+2]); }
kernel void k_hmul(device half* out [[buffer(0)]], device half* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) { out[t] = a[t+0] * a[t+1]; }
kernel void k_absmul(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) { out[t] = fabs(a[t+0]) * a[t+1]; }
kernel void k_negabs(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) { out[t] = -fabs(a[t+0]) + a[t+1]; }
