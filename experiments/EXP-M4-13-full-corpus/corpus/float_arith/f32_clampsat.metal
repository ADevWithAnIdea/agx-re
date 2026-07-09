#include <metal_stdlib>
using namespace metal;
// clamp / saturate. saturate(x)=clamp(x,0,1) often has a dedicated ALU output
// modifier on AGX; clamp(x,lo,hi) with register bounds is min(max()). Isolate
// both, plus the saturate output-modifier folded onto a mul/add.
kernel void k_clamp(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                    device const float* lo[[buffer(2)]], device const float* hi[[buffer(3)]],
                    uint i[[thread_position_in_grid]]) {
    o[i] = clamp(a[i], lo[i], hi[i]);
}
kernel void k_saturate(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                       uint i[[thread_position_in_grid]]) {
    o[i] = saturate(a[i]);
}
kernel void k_clamp01(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                      uint i[[thread_position_in_grid]]) {
    o[i] = clamp(a[i], 0.0f, 1.0f);   // should fold to saturate modifier
}
kernel void k_sat_mul(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                      device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = saturate(a[i] * b[i]);     // saturate output-modifier on fmul
}
kernel void k_clamp_v4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                       device const float4* lo[[buffer(2)]], device const float4* hi[[buffer(3)]],
                       uint i[[thread_position_in_grid]]) {
    o[i] = clamp(a[i], lo[i], hi[i]);
}
