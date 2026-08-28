// EXP-0094 lodquery_probe.metal -- own MSL. Cross-checks the sample()-implicit
// effective LOD (via the LOD-recovery texture trick, r channel; no bias) against
// calculate_clamped_lod (g) and calculate_unclamped_lod (b) for the SAME uv
// derivative, in the same draw.
//
// params[0] = uvScale.x, params[1] = uvScale.y
#include <metal_stdlib>
using namespace metal;

struct VOut { float4 position [[position]]; };

vertex VOut vmain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.position = float4(p[vid], 0, 1);
    return o;
}

fragment float4 fmain(float4 position [[position]],
                       texture2d<float> tex [[texture(0)]],
                       sampler s [[sampler(0)]],
                       constant float *params [[buffer(0)]]) {
    float2 uv = position.xy * float2(params[0], params[1]);
    float sampled = tex.sample(s, uv).r;
    float clampedLod = tex.calculate_clamped_lod(s, uv);
    float unclampedLod = tex.calculate_unclamped_lod(s, uv);
    return float4(sampled, clampedLod, unclampedLod, 1);
}
