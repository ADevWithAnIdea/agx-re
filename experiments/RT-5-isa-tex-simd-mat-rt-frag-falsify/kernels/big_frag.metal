#include <metal_stdlib>
using namespace metal;
// Large fragment shader: 3 textures, 2 samplers, many varyings (flat + smooth),
// MRT output (3 render targets). Stresses iter / sample / frag_color_store / MRT.
struct VOut {
    float4 pos [[position]];
    float4 a;
    float4 b;
    float2 uv;
    float  f [[flat]];
};
struct FOut {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
    float4 c2 [[color(2)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.pos = float4(p[vid],0,1);
    o.a = float4(0.1,0.2,0.3,0.4) + 0.01f*p[vid].x;
    o.b = float4(0.5,0.6,0.7,0.8) + 0.01f*p[vid].y;
    o.uv = 0.5f*(p[vid]+1.0f);
    o.f = float(vid);
    return o;
}
fragment FOut f_main(VOut in [[stage_in]],
                     texture2d<float> t0 [[texture(0)]],
                     texture2d<float> t1 [[texture(1)]],
                     texture2d<float> t2 [[texture(2)]],
                     sampler s0 [[sampler(0)]],
                     sampler s1 [[sampler(1)]]) {
    FOut o;
    float4 x0 = t0.sample(s0, in.uv);
    float4 x1 = t1.sample(s1, in.uv);
    float4 x2 = t2.read(uint2(in.uv * 2.0f));
    o.c0 = in.a + x0;
    o.c1 = in.b + x1 * in.f;
    o.c2 = x2 + float4(in.uv, 0, 1);
    return o;
}
