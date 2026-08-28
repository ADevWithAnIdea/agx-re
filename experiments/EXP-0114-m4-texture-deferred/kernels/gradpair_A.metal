#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position [[position]];
    float4 gA [[user(locn0)]];
    float4 gB [[user(locn1)]];
};

vertex VOut vmain(uint vid [[vertex_id]], constant float *p [[buffer(0)]]) {
    float2 tri[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.position = float4(tri[vid], 0, 1);
    o.gA = float4(p[0], p[1], p[2], p[3]);
    o.gB = float4(p[4], p[5], p[6], p[7]);
    return o;
}

fragment float4 fmain(VOut in [[stage_in]],
                       texture2d<float> tex [[texture(0)]], sampler s [[sampler(0)]]) {
    float4 c = tex.sample(s, float2(0.5, 0.5), gradient2d(in.gA.xy, in.gA.zw));
    float sink = in.gB.x + in.gB.y + in.gB.z + in.gB.w;
    return float4(c.r, c.g, sink, 1.0);
}
