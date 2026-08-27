#include <metal_stdlib>
using namespace metal;

// EXP-0073: FP32 division precision probe (OPT-02).
// Plain '/' on float. No fast-path intrinsics (no rsqrt/rcp), no `precise`
// qualifier, no explicit rounding hints: the tested configuration is the
// default MSL divide compiled with MTLCompileOptions.fastMathEnabled = NO.
// Inputs and outputs are transported as raw uint bit patterns so that no
// CPU-side float conversion ever touches an observation.

kernel void k_fdiv(device const uint2 *in [[buffer(0)]],
                   device uint *out [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    float a = as_type<float>(in[i].x);
    float b = as_type<float>(in[i].y);
    out[i] = as_type<uint>(a / b);
}
