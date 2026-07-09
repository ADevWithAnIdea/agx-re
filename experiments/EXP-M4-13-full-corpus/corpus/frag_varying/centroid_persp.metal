// frag_varying: centroid_perspective interpolation (sample inside covered area).
// Isolates the centroid-sampled perspective iterate mode.
#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 pos [[position]];
    float4 a [[centroid_perspective]];
};
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.a = vin[vid]; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.a; }
