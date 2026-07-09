#include <metal_stdlib>
using namespace metal;
// step / smoothstep / mix / saturate-based interpolation. These decompose into
// compare+select, clamp, and fma on AGX, exercising the fused clamp/select forms
// with immediate constants (0/1/2/3) baked in as ALU immediates.
kernel void k_step(device float* o[[buffer(0)]], device const float* edge[[buffer(1)]],
                   device const float* x[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = step(edge[i], x[i]);
}
kernel void k_smoothstep(device float* o[[buffer(0)]], device const float* e0[[buffer(1)]],
                         device const float* e1[[buffer(2)]], device const float* x[[buffer(3)]],
                         uint i[[thread_position_in_grid]]) {
    o[i] = smoothstep(e0[i], e1[i], x[i]);
}
kernel void k_mix(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], device const float* t[[buffer(3)]],
                  uint i[[thread_position_in_grid]]) {
    o[i] = mix(a[i], b[i], t[i]);   // a + (b-a)*t -> fma
}
kernel void k_mix_v4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                     device const float4* b[[buffer(2)]], device const float4* t[[buffer(3)]],
                     uint i[[thread_position_in_grid]]) {
    o[i] = mix(a[i], b[i], t[i]);
}
