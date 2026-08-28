#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position [[position]];
    float4 filler [[user(locn0)]];
    float4 gA [[user(locn1)]];
    float4 gB [[user(locn2)]];
};

vertex VOut vmain(uint vid [[vertex_id]], constant float *p [[buffer(0)]]) {
    float2 tri[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.position = float4(tri[vid], 0, 1);
    o.filler = float4(p[8], p[9], p[10], p[11]);
    o.gA = float4(p[0], p[1], p[2], p[3]);
    o.gB = float4(p[4], p[5], p[6], p[7]);
    return o;
}

fragment float4 fmain(VOut in [[stage_in]],
                       texture2d<float> tex [[texture(0)]], sampler s [[sampler(0)]]) {
    float4 c = tex.sample(s, float2(0.5, 0.5), gradient2d(in.gB.xy, in.gB.zw));
    float sink = in.gA.x + in.gA.y + in.gA.z + in.gA.w + in.filler.x;
    return float4(c.r, c.g, sink, 1.0);
}
