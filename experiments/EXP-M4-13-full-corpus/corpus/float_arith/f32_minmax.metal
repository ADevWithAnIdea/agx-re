#include <metal_stdlib>
using namespace metal;
// min/max/fmin/fmax. Metal's min/max and fmin/fmax differ in NaN semantics, so
// they may lower to distinct opcodes (one may set an NaN-propagation modifier).
kernel void k_fmin(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = fmin(a[i], b[i]);
}
kernel void k_fmax(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = fmax(a[i], b[i]);
}
kernel void k_min(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = min(a[i], b[i]);
}
kernel void k_max(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = max(a[i], b[i]);
}
kernel void k_minmax3(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                      device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                      uint i[[thread_position_in_grid]]) {
    o[i] = fmax(fmin(a[i], b[i]), c[i]);   // min3/max3 fusion candidate
}
kernel void k_fmax_v4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                      device const float4* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = fmax(a[i], b[i]);
}
