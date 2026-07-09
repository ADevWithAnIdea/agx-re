// frag_varying: PULL-MODEL interpolate on a NO-PERSPECTIVE (linear) interpolant.
// Isolates the explicit interpolate with the non-perspective coefficient path.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float2 c [[user(loc0)]]; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.c = vin[vid].xy; return o;
}
struct FIn {
    float4 pos [[position]];
    interpolant<float2, interpolation::no_perspective> c [[user(loc0)]];
};
fragment float4 fMain(FIn in [[stage_in]], device const float2* off [[buffer(0)]]) {
    float2 a = in.c.interpolate_at_center();
    float2 b = in.c.interpolate_at_offset(off[0]);
    return float4(a, b);
}
