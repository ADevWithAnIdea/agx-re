#include <metal_stdlib>
using namespace metal;
// Sign manipulation: fabs (abs source modifier), negate, copysign, and the
// abs+negate combination. These are usually source/output modifiers rather than
// standalone opcodes, so isolating them tests the modifier bits directly.
kernel void k_abs(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) {
    o[i] = fabs(a[i]);
}
kernel void k_neg(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) {
    o[i] = -a[i];
}
kernel void k_copysign(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                       device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = copysign(a[i], b[i]);
}
kernel void k_negabs(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                     uint i[[thread_position_in_grid]]) {
    o[i] = -fabs(a[i]);   // combined abs+negate modifier
}
kernel void k_absdiff(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                      device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = fabs(a[i] - b[i]);   // abs output-modifier on fsub
}
kernel void k_sign(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) {
    o[i] = sign(a[i]);   // -1/0/+1
}
