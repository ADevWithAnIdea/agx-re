// EXP-0179 census: [[visible]] functions -- direct and through a
// visible_function_table (Metal's dynamic-linking surface).
// CLEAN-ROOM: our own MSL.
#include <metal_stdlib>
using namespace metal;

[[visible]] float vadd(float a, float b) { return a + b; }
[[visible]] float vmul(float a, float b) { return a * b; }

// C19 a [[visible]] function called DIRECTLY from the same library.
kernel void k_visible_direct(device const float* A [[buffer(0)]],
                             device const float* B [[buffer(1)]],
                             device float* O [[buffer(2)]],
                             uint i [[thread_position_in_grid]]) {
    O[i] = vadd(A[i], B[i]);
}

// C20 runtime-selected indirect call through a visible_function_table.
kernel void k_vft_dyn(device const float* A [[buffer(0)]],
                      device const float* B [[buffer(1)]],
                      device float* O [[buffer(2)]],
                      visible_function_table<float(float, float)> ftab [[buffer(3)]],
                      device const uint* sel [[buffer(4)]],
                      uint i [[thread_position_in_grid]]) {
    O[i] = ftab[sel[i]](A[i], B[i]);
}

// C21 constant-index indirect call.
kernel void k_vft_const(device const float* A [[buffer(0)]],
                        device const float* B [[buffer(1)]],
                        device float* O [[buffer(2)]],
                        visible_function_table<float(float, float)> ftab [[buffer(3)]],
                        uint i [[thread_position_in_grid]]) {
    O[i] = ftab[0](A[i], B[i]);
}
