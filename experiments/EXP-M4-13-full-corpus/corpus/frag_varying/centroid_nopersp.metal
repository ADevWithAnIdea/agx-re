// frag_varying: centroid_no_perspective interpolation (linear, centroid-sampled).
// Isolates the centroid + non-perspective iterate mode combination.
#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 pos [[position]];
    float4 a [[centroid_no_perspective]];
};
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.a = vin[vid]; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.a; }
