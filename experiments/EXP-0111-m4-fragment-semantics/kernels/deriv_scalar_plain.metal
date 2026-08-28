#include <metal_stdlib>
using namespace metal;
// Diagnostic (not part of the frozen matrix): isolate whether the axis-byte anomaly
// (deriv_scalar_f1..f4, dfdx-only on a transcendental-of-varying value, compiled to
// axis=0x90 instead of the 0x92 seen for dfdx(pos.x)/dfdx(pos.y) in deriv_axis_check)
// is driven by (a) varying-vs-position operand source, or (b) presence/absence of a
// paired dfdy() call in the same shader, or (c) the transcendental. This kernel: dfdx
// ONLY (no dfdy anywhere), on a PLAIN linear varying (no transcendental).
struct VOut { float4 pos [[position]]; float2 uv [[user(locn0)]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float d = dfdx(in.uv.x);
    return float4(d, 0.0, 0.0, 1.0);
}
