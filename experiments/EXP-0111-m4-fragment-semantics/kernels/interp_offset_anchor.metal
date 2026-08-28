#include <metal_stdlib>
using namespace metal;
// Pilot diagnostic only: compare push-model center_perspective, pull-model
// interpolate_at_center(), and pull-model interpolate_at_offset(0,0) on the SAME
// affine varying (two copies at two locations, fed identical per-vertex values), to
// isolate an unexpected -1.0 constant offset seen in interp_offset_sweep.
struct VOut { float4 pos [[position]]; float v0 [[user(locn0)]]; float v1 [[user(locn1)]]; };
struct FIn  { float4 pos [[position]];
              float vpush [[user(locn0)]];
              interpolant<float, interpolation::perspective> vpull [[user(locn1)]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.v0 = p[vid].x; o.v1 = p[vid].x; return o;
}
fragment float4 f_main(FIn in [[stage_in]], device uint *buf [[buffer(0)]]) {
    float a = in.vpush;
    float b = in.vpull.interpolate_at_center();
    float c = in.vpull.interpolate_at_offset(float2(0,0));
    buf[0] = as_type<uint>(a);
    buf[1] = as_type<uint>(b);
    buf[2] = as_type<uint>(c);
    return float4(0,0,0,1);
}
