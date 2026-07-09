// frag_varying: PULL-MODEL interpolate_at_offset(dynamic float2 offset).
// Isolates explicit interpolate at an arbitrary sub-pixel offset (from a buffer).
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 c [[user(loc0)]]; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.c = vin[vid]; return o;
}
struct FIn {
    float4 pos [[position]];
    interpolant<float4, interpolation::perspective> c [[user(loc0)]];
};
fragment float4 fMain(FIn in [[stage_in]], device const float2* off [[buffer(0)]]) {
    return in.c.interpolate_at_offset(off[0]);
}
