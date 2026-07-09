// frag_varying: DEFAULT center-perspective interpolation of a float4 varying.
// Isolates the baseline perspective-correct iterate/interpolate instruction.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 a; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.a = vin[vid] * 0.5f + 0.25f; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.a; }
