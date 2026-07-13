// EXP-M5-17: establish the texture/sampler SLOT encoding scale (byte+6 / byte+5)
// and coordinate register scale (byte+3) by byte-diff of freshly compiled kernels
// that keep multiple resources live (select pattern defeats DCE renumbering).
// CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected.
#include <metal_stdlib>
using namespace metal;

struct VOut { float4 pos [[position]]; float2 uvA; float2 uvB; float2 uvC; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos=float4(p[vid],0,1);
    o.uvA=float2(0.25,0.25); o.uvB=float2(0.75,0.75); o.uvC=float2(0.5,0.5);
    return o;
}

// tex slot 0 vs 2
fragment float4 f_tex02(VOut in [[stage_in]],
    texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]],
    texture2d<float> t2 [[texture(2)]], sampler s [[sampler(0)]]) {
    float4 a=t0.sample(s,in.uvA); float4 b=t2.sample(s,in.uvA);
    return select(a,b,in.uvA.x>1000.0);
}
// tex slot 0 vs 3
fragment float4 f_tex03(VOut in [[stage_in]],
    texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]],
    texture2d<float> t2 [[texture(2)]], texture2d<float> t3 [[texture(3)]],
    sampler s [[sampler(0)]]) {
    float4 a=t0.sample(s,in.uvA); float4 b=t3.sample(s,in.uvA);
    return select(a,b,in.uvA.x>1000.0);
}
// sampler slot 0 vs 2
fragment float4 f_samp02(VOut in [[stage_in]], texture2d<float> t [[texture(0)]],
    sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]], sampler s2 [[sampler(2)]]) {
    float4 a=t.sample(s0,in.uvA); float4 b=t.sample(s2,in.uvA);
    return select(a,b,in.uvA.x>1000.0);
}
// sampler slot 0 vs 3
fragment float4 f_samp03(VOut in [[stage_in]], texture2d<float> t [[texture(0)]],
    sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]],
    sampler s2 [[sampler(2)]], sampler s3 [[sampler(3)]]) {
    float4 a=t.sample(s0,in.uvA); float4 b=t.sample(s3,in.uvA);
    return select(a,b,in.uvA.x>1000.0);
}
// coord regs: sample uvA vs uvC (a third float2 -> a further register)
fragment float4 f_coordAC(VOut in [[stage_in]], texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    float4 a=t.sample(s,in.uvA); float4 b=t.sample(s,in.uvC);
    return select(a,b,in.uvA.x>1000.0);
}
// three coords live: uvA vs uvB vs uvC
fragment float4 f_coordABC(VOut in [[stage_in]], texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    float4 a=t.sample(s,in.uvA); float4 b=t.sample(s,in.uvB); float4 c=t.sample(s,in.uvC);
    return select(select(a,b,in.uvA.x>1000.0),c,in.uvA.y>1000.0);
}
