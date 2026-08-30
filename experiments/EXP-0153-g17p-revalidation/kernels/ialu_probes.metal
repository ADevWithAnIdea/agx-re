// EXP-0153 authored MSL probes. The two kernels below are verbatim copies of
// the corresponding kernels in experiments/EXP-0139-m4-emit-ialu/kernels/
// ialu_probes.metal (our own MSL, authored by this project) -- reused unchanged
// so that the G17P capture is a re-run of the M4 experiment rather than a new
// construction. Buffer signature is identical in every kernel so one harness
// can drive them all: a[] in, b[] in, o[] out.
#include <metal_stdlib>
using namespace metal;

// --- ibfe: compile-time-constant extract (EXP-0033's single-op shape) ------
kernel void k_bfe_const(device const uint* a [[buffer(0)]],
                        device const uint* b [[buffer(1)]],
                        device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = extract_bits(a[i], 4u, 8u);
}

// --- ishift: variable right shift; a SECOND, independent ibfe lowering -----
kernel void k_shr(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                  device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] >> b[i];
}
