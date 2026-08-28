// split_callret.metal -- EXP-0129 H2: multi-argument / multi-component-
// return CALL-ABI generalization (OWN-SHADER, compute).
//
// EXP-0035 (A18) HW-validated the CALL ABI for a 2-argument, single-scalar-
// return `h_sub` case: args in r10,r11,...; return in r10. A genuine
// prolog/epilog split will routinely need MORE than 2 scalar arguments
// (e.g. several attribute components) and a MULTI-component (vector)
// return (e.g. a fetched float4 attribute, or a blended float4 color).
// This kernel generalizes both axes at once: a noinline callee taking 5
// scalar args (spanning past r10..r14) and returning a float4 (spanning
// r10..r13 at the RETURN site), called TWICE (two independent call sites,
// also a fresh cross-check of EXP-0117's byte+6 CALL-signature-uniformity
// finding on a different kernel shape).

#include <metal_stdlib>
using namespace metal;

[[clang::noinline]] float4 mk4(float a, float b, float c, float d, float e) {
    return float4(a + b, b + c, c + d, d + e);
}

kernel void k_callret(device const float *in [[buffer(0)]],
                       device float4 *out [[buffer(1)]],
                       uint tid [[thread_position_in_grid]]) {
    float base = in[tid];
    float4 r1 = mk4(base, base + 1.0, base + 2.0, base + 3.0, base + 4.0);
    float4 r2 = mk4(base * 2.0, base * 2.0 + 1.0, base * 2.0 + 2.0, base * 2.0 + 3.0, base * 2.0 + 4.0);
    out[tid] = r1 + r2;
}
