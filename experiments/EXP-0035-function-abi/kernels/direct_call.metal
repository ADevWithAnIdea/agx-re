// EXP-0035 A: direct call/return ABI (A18 Pro / G17P).
// CLEAN-ROOM: OUR OWN MSL. Compiled at runtime (newLibraryWithSource:); only our
// own compiled bytes are ever inspected. No Apple binary is disassembled.
//
// Goal: force a NON-INLINED helper call so a dedicated call + return instruction
// appears, then diff against an inlined baseline (same math) to localize the
// call/return opcodes and the calling convention (which regs carry args/return).
#include <metal_stdlib>
using namespace metal;

// ---- noinline helper: 2 float args -> 1 float return -----------------------
__attribute__((noinline))
static float helper2(float a, float b) {
    return a * b + 1.0f;
}

// Caller that invokes the non-inlined helper.
kernel void call_noinline(device const float *A [[buffer(0)]],
                          device const float *B [[buffer(1)]],
                          device float *O [[buffer(2)]],
                          uint i [[thread_position_in_grid]]) {
    O[i] = helper2(A[i], B[i]);
}

// ---- inlined baseline: identical math, helper allowed to inline -------------
static float helper2_inl(float a, float b) {
    return a * b + 1.0f;
}
kernel void call_inlined(device const float *A [[buffer(0)]],
                         device const float *B [[buffer(1)]],
                         device float *O [[buffer(2)]],
                         uint i [[thread_position_in_grid]]) {
    O[i] = helper2_inl(A[i], B[i]);
}
