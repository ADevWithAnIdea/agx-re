// EXP-M5-17: slot-2 encoding — keep 3 textures / 4 samplers ALL live so the compiler
// cannot compact bindings. Reads byte+6 (tex slot) / byte+5 (samp slot) for slot>=2.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float2 uvA; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};
    VOut o; o.pos=float4(p[vid],0,1); o.uvA=float2(0.25,0.25); return o;
}
// three textures all live -> binding slots 0,1,2
fragment float4 f_tex3(VOut in [[stage_in]],
    texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]],
    texture2d<float> t2 [[texture(2)]], sampler s [[sampler(0)]]) {
    float4 a=t0.sample(s,in.uvA), b=t1.sample(s,in.uvA), c=t2.sample(s,in.uvA);
    return select(select(a,b,in.uvA.x>1e3),c,in.uvA.y>1e3);
}
// four samplers all live -> sampler slots 0,1,2,3
fragment float4 f_samp4(VOut in [[stage_in]], texture2d<float> t [[texture(0)]],
    sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]],
    sampler s2 [[sampler(2)]], sampler s3 [[sampler(3)]]) {
    float4 a=t.sample(s0,in.uvA), b=t.sample(s1,in.uvA);
    float4 c=t.sample(s2,in.uvA), d=t.sample(s3,in.uvA);
    return select(select(a,b,in.uvA.x>1e3),select(c,d,in.uvA.y>1e3),in.uvA.x<-1e3);
}
