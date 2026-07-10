#include <metal_stdlib>
using namespace metal;

vertex float4 v(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid], 0, 1);
}

// Sample a runtime 1x1 texture (bound via --tex-fill) and output it. The colour
// is a genuine runtime float4 flowing through the colour PACK, so the pack does a
// real per-component float->unorm8 conversion (no constant folding).
fragment float4 f(texture2d<float> t [[texture(0)]],
                  sampler s [[sampler(0)]]) {
    return t.sample(s, float2(0.5, 0.5));
}
