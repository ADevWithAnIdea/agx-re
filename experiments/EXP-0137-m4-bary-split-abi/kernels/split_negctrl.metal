// split_negctrl.metal -- EXP-0129 H2 negative control (OWN-SHADER, compile-only).
// Entry-point-only attributes ([[color(n)]], [[stage_in]], [[position]], ...)
// should NOT be usable on a non-entry (ordinary callable) function -- a
// driver implementing a genuine prolog/epilog split via the CALL ABI must
// forward such values as PLAIN parameters from the entry function, it cannot
// give a callee its own resource/stage-IO bindings. This file's own-compiler
// diagnostic is the falsifier: if this somehow compiles, the "must forward"
// claim in RESULTS.md is wrong and must be corrected, not asserted anyway.
#include <metal_stdlib>
using namespace metal;

struct VOutN { float4 position [[position]]; };
vertex VOutN v_negctrl(uint vid [[vertex_id]]) {
    VOutN o;
    float2 p3[3] = { float2(-1.0,-1.0), float2(3.0,-1.0), float2(-1.0,3.0) };
    o.position = float4(p3[vid % 3], 0.0, 1.0);
    return o;
}

float4 bad_helper(float4 dst [[color(0)]]) {
    return dst;
}

fragment float4 f_negctrl_caller(float4 x [[color(0)]]) {
    return bad_helper(x);
}
