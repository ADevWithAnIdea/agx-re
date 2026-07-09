// frag_varying: HALF-precision perspective varyings (16-bit iterate width).
// Isolates the half-typed interpolate path vs the 32-bit float path.
#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 pos [[position]];
    half4  a;                       // center-perspective half4
    half2  b [[center_no_perspective]];
};
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.a = half4(vin[vid]); o.b = half2(vin[vid].zw); return o;
}
fragment half4 fMain(VOut in [[stage_in]]) { return in.a + in.b.xyxy; }
