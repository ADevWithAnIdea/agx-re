#include <metal_stdlib>
using namespace metal;
// Full ordered compare set, each feeding a select so the compiler emits the
// compare-and-select (fcmpsel) with a distinct condition code per kernel. This
// pins every fp compare predicate: lt/le/gt/ge/eq/ne. Result written as float
// so no int-domain conversion hides the compare.
kernel void k_cmp_lt(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                     device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = (a[i] <  b[i]) ? a[i] : b[i];
}
kernel void k_cmp_le(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                     device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = (a[i] <= b[i]) ? a[i] : b[i];
}
kernel void k_cmp_gt(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                     device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = (a[i] >  b[i]) ? a[i] : b[i];
}
kernel void k_cmp_ge(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                     device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = (a[i] >= b[i]) ? a[i] : b[i];
}
kernel void k_cmp_eq(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                     device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = (a[i] == b[i]) ? a[i] : b[i];
}
kernel void k_cmp_ne(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                     device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = (a[i] != b[i]) ? a[i] : b[i];
}
// Compare producing a 0/1 mask (bool->float) to surface the non-select form.
kernel void k_cmp_mask(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                       device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = float(a[i] < b[i]);
}
