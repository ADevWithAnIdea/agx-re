#include <metal_stdlib>
using namespace metal;
// RT-10 Part5: BIG render pair — vertex + fragment with varyings, texture sampling,
// derivatives, divergent CF, to measure fragment-stage census %.
struct VOut {
    float4 pos [[position]];
    float2 uv;
    float3 col;
    float  w;
};
vertex VOut v_main(uint vid [[vertex_id]],
                   const device float2* vpos [[buffer(0)]]) {
    VOut o;
    float2 p = vpos[vid];
    o.pos = float4(p, 0.0f, 1.0f);
    o.uv  = p * 0.5f + 0.5f;
    o.col = float3(p.x, p.y, 1.0f - p.x);
    o.w   = p.x + p.y + 2.0f;
    return o;
}
fragment float4 f_main(VOut in [[stage_in]],
                       texture2d<float> tex [[texture(0)]],
                       sampler samp [[sampler(0)]]) {
    float4 t = tex.sample(samp, in.uv);
    // derivatives
    float2 dx = dfdx(in.uv);
    float2 dy = dfdy(in.uv);
    float  lod = max(length(dx), length(dy));
    float4 tl  = tex.sample(samp, in.uv, level(lod * 4.0f));
    // divergent CF over interpolated values
    float3 c = in.col;
    if (in.w > 3.0f) {
        c *= t.xyz;
        for (int i = 0; i < 4; i++) {
            if ((int)(in.uv.x * 8.0f) == i) { c += 0.1f * (float)i; break; }
            c *= 0.95f;
        }
    } else {
        c = mix(c, tl.xyz, 0.5f);
    }
    float a = (in.uv.x > 0.5f) ? 1.0f : (in.uv.y > 0.5f ? 0.75f : 0.5f);
    if (a < 0.4f) discard_fragment();
    return float4(c, a);
}
