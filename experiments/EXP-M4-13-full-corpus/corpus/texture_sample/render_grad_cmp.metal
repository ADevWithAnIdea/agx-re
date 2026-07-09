// texture_sample corpus (FRAGMENT stage): explicit gradient2d + implicit depth compare +
// gather_compare + fwidth. Exercises derivative intrinsics feeding sampling.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float2 uv; float ref; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o;
    o.pos = vin[vid];
    o.uv  = vin[vid].xy;
    o.ref = vin[vid].z;
    return o;
}
fragment float4 fMain(VOut in [[stage_in]],
                      texture2d<float> t [[texture(0)]],
                      depth2d<float> d [[texture(1)]],
                      sampler s [[sampler(0)]],
                      sampler cs [[sampler(1)]]) {
    float2 dx = dfdx(in.uv);
    float2 dy = dfdy(in.uv);
    float4 g  = t.sample(s, in.uv, gradient2d(dx, dy));
    float cmp = d.sample_compare(cs, in.uv, in.ref);   // implicit-LOD compare
    float gc  = d.gather_compare(cs, in.uv, in.ref).x;
    float w   = fwidth(in.uv.x);
    return g + float4(cmp + gc + w);
}
