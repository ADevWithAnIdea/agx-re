#include <metal_stdlib>
using namespace metal;
// FS-08 remainder, Y-axis companion to interp_offset_sweep.metal: v=ndc_y (varies with Y
// only), same full-coverage N=1 setup, sweeping the offset's Y component. Cross-checks
// whether interpolate_at_offset's Y axis follows the same absolute window-space,
// pixel-top-left-corner-relative convention found on X, and whether it is sign-flipped
// (window Y increases downward, matching [[position]].y per FS-03) relative to the
// increasing-upward NDC-y varying used here.
struct VOut { float4 pos [[position]]; float v [[user(locn0)]]; };
struct FIn  { float4 pos [[position]]; interpolant<float, interpolation::perspective> v [[user(locn0)]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.v = p[vid].y; return o;
}
fragment float4 f_main(FIn in [[stage_in]], device uint *buf [[buffer(0)]],
                        constant float2 &offset [[buffer(1)]]) {
    float v_off = in.v.interpolate_at_offset(offset);
    buf[0] = as_type<uint>(v_off);
    return float4(0,0,0,1);
}
