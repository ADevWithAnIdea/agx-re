// frag_varying: center_no_perspective (LINEAR / screen-space) interpolation.
// Isolates the non-perspective iterate mode (no per-fragment 1/w divide).
#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 pos [[position]];
    float4 a [[center_no_perspective]];
    float2 b [[center_no_perspective]];
};
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.a = vin[vid]; o.b = vin[vid].zw; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.a + in.b.xyxy; }
