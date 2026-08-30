// EXP-0179 census: CONTROL constructs that SHOULD inline (no call expected).
// CLEAN-ROOM: our own MSL. We author source until the instruction we want
// appears; we do NOT characterise Apple's inlining heuristic (declared boundary).
#include <metal_stdlib>
using namespace metal;

// C01 plain static helper, tiny body -> control, expect NO call.
static float h_tiny(float a, float b) { return a * b + 1.0f; }
kernel void k_inline_ctl(device const float* A [[buffer(0)]],
                         device const float* B [[buffer(1)]],
                         device float* O [[buffer(2)]],
                         uint i [[thread_position_in_grid]]) {
    O[i] = h_tiny(A[i], B[i]);
}

// C02 always_inline, explicitly requested -> control, expect NO call.
__attribute__((always_inline))
static float h_always(float a, float b) { return a * b + 2.0f; }
kernel void k_always_inline(device const float* A [[buffer(0)]],
                            device const float* B [[buffer(1)]],
                            device float* O [[buffer(2)]],
                            uint i [[thread_position_in_grid]]) {
    O[i] = h_always(A[i], B[i]);
}
