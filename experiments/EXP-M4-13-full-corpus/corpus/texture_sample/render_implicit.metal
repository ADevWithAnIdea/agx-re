// texture_sample corpus (FRAGMENT stage): implicit-LOD sample + bias + min_lod_clamp.
// Fragment stage exposes the derivative-driven sample instruction class.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o;
    o.pos = vin[vid];
    o.uv  = vin[vid].xy;
    return o;
}
fragment float4 fMain(VOut in [[stage_in]],
                      texture2d<float> t [[texture(0)]],
                      sampler s [[sampler(0)]]) {
    float4 a = t.sample(s, in.uv);                     // implicit LOD (HW derivatives)
    float4 b = t.sample(s, in.uv, bias(1.5));          // LOD bias
    float4 c = t.sample(s, in.uv, min_lod_clamp(0.5)); // implicit + min-lod clamp
    return a + b + c;
}
