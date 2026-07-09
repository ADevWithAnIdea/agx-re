#include <metal_stdlib>
using namespace metal;
// Rounding family: floor, ceil, trunc, rint (round-to-nearest-even), round
// (round-half-away), and fract. These typically map to a single round-mode ALU
// op selected by a rounding-mode field -> isolating each pins that field's
// encoding. fract may be its own op or floor+sub.
kernel void k_floor(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                    uint i[[thread_position_in_grid]]) {
    o[i] = floor(a[i]);
}
kernel void k_ceil(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) {
    o[i] = ceil(a[i]);
}
kernel void k_trunc(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                    uint i[[thread_position_in_grid]]) {
    o[i] = trunc(a[i]);
}
kernel void k_rint(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) {
    o[i] = rint(a[i]);
}
kernel void k_round(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                    uint i[[thread_position_in_grid]]) {
    o[i] = round(a[i]);
}
kernel void k_fract(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                    uint i[[thread_position_in_grid]]) {
    o[i] = fract(a[i]);
}
kernel void k_floor_v4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                       uint i[[thread_position_in_grid]]) {
    o[i] = floor(a[i]);
}
