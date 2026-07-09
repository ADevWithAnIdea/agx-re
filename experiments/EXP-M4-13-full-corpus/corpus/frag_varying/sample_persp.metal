// frag_varying: sample_perspective interpolation -> forces per-SAMPLE shading.
// Isolates per-sample perspective iterate; exercises sample-rate execution.
#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 pos [[position]];
    float4 a [[sample_perspective]];
};
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.a = vin[vid]; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.a; }
