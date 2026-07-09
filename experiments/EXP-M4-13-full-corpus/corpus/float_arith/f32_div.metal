#include <metal_stdlib>
using namespace metal;
// Division / reciprocal family. Under fast-math a/b lowers to rcp+mul; with
// --no-fast-math it takes the IEEE-correct expansion (surfaces different opcodes
// / rcp refinement steps). Also isolate bare reciprocal and rsqrt-adjacent forms.
kernel void k_div(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = a[i] / b[i];
}
kernel void k_recip(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                    uint i[[thread_position_in_grid]]) {
    o[i] = 1.0f / a[i];
}
kernel void k_divide_fn(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                        device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = divide(a[i], b[i]);   // metal::divide explicit
}
kernel void k_div_v4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                     device const float4* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = a[i] / b[i];
}
