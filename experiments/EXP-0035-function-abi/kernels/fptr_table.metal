// EXP-0035 B: function pointers via visible_function_table (A18 Pro / G17P).
// CLEAN-ROOM: OUR OWN MSL. Only our own compiled bytes are inspected.
//
// Goal: an INDIRECT call through a visible_function_table (an argument-buffer
// slot, exactly like the RT intersection_function_table of EXP-0023). Shows how
// the call target is loaded from the table then called, and how the visible
// functions themselves are compiled (separate callable symbol regions).
#include <metal_stdlib>
using namespace metal;

// Two [[visible]] functions with the SAME signature -> both valid table targets.
[[visible]] float vadd(float a, float b) { return a + b; }
[[visible]] float vmul(float a, float b) { return a * b; }

// Caller: pick a target at runtime from a device buffer -> defeats devirtualization.
kernel void fptr_call(device const float *A [[buffer(0)]],
                      device const float *B [[buffer(1)]],
                      device float *O [[buffer(2)]],
                      visible_function_table<float(float, float)> ftab [[buffer(3)]],
                      device const uint *sel [[buffer(4)]],
                      uint i [[thread_position_in_grid]]) {
    O[i] = ftab[sel[i]](A[i], B[i]);
}
