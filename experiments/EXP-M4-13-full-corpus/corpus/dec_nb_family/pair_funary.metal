#include <metal_stdlib>
using namespace metal;
// Minimal PAIR set for the 0x?b float source-modifier move (funary). Each kernel
// materialises exactly one standalone funary op (the store cannot absorb the
// modifier), so the extracted 0x0b instruction differs from its sibling in
// exactly ONE source-level thing -> the differing byte localises the field.
kernel void k_neg (device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) { o[i] = -a[i]; }        // modifier = neg
kernel void k_abs (device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) { o[i] = fabs(a[i]); }   // modifier = abs
kernel void k_negabs(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) { o[i] = -fabs(a[i]); }  // modifier = neg+abs
