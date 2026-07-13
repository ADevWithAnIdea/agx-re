// EXP-M5-22: texture BINDING-TABLE addressing for dense slots >=2.
// Argument-buffer (Tier-2) single-slot samples force a fixed binding-table index k,
// so byte-diff of f_ab0..f_ab7 reveals how byte+4 (bank) + byte+6 (slot) select the
// texture descriptor. Direct dense bindings (f_texN) cross-check.
// CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected.
#include <metal_stdlib>
using namespace metal;

struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = float2(0.25,0.25);
    return o;
}

// ---- Tier-2 argument buffer: an 8-texture table. tt.tex[k] is a FIXED binding-table
//      index k regardless of DCE (it is an offset into one buffer, not a live binding). ----
struct TexTable { array<texture2d<float>, 8> tex; };

fragment float4 f_ab0(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) { return tt.tex[0].sample(s, in.uv); }
fragment float4 f_ab1(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) { return tt.tex[1].sample(s, in.uv); }
fragment float4 f_ab2(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) { return tt.tex[2].sample(s, in.uv); }
fragment float4 f_ab3(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) { return tt.tex[3].sample(s, in.uv); }
fragment float4 f_ab4(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) { return tt.tex[4].sample(s, in.uv); }
fragment float4 f_ab5(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) { return tt.tex[5].sample(s, in.uv); }
fragment float4 f_ab6(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) { return tt.tex[6].sample(s, in.uv); }
fragment float4 f_ab7(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) { return tt.tex[7].sample(s, in.uv); }

// two live indices in ONE program (byte-diff within a program: cleanest field isolation)
fragment float4 f_ab_01(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) {
    float4 a=tt.tex[0].sample(s,in.uv), b=tt.tex[1].sample(s,in.uv); return select(a,b,in.uv.x>1e3); }
fragment float4 f_ab_02(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) {
    float4 a=tt.tex[0].sample(s,in.uv), b=tt.tex[2].sample(s,in.uv); return select(a,b,in.uv.x>1e3); }
fragment float4 f_ab_04(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) {
    float4 a=tt.tex[0].sample(s,in.uv), b=tt.tex[4].sample(s,in.uv); return select(a,b,in.uv.x>1e3); }
fragment float4 f_ab_07(VOut in [[stage_in]], constant TexTable& tt [[buffer(0)]], sampler s [[sampler(0)]]) {
    float4 a=tt.tex[0].sample(s,in.uv), b=tt.tex[7].sample(s,in.uv); return select(a,b,in.uv.x>1e3); }

// ---- direct dense bindings (cross-check; each texture is a separate [[texture(N)]]) ----
fragment float4 f_tex2(VOut in [[stage_in]], texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]], sampler s [[sampler(0)]]) {
    float4 a=t0.sample(s,in.uv), b=t1.sample(s,in.uv); return select(a,b,in.uv.x>1e3); }
fragment float4 f_tex4(VOut in [[stage_in]], texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]],
    texture2d<float> t2 [[texture(2)]], texture2d<float> t3 [[texture(3)]], sampler s [[sampler(0)]]) {
    float4 a=t0.sample(s,in.uv), b=t1.sample(s,in.uv), c=t2.sample(s,in.uv), d=t3.sample(s,in.uv);
    return select(select(a,b,in.uv.x>1e3),select(c,d,in.uv.y>1e3),in.uv.x<-1e3); }
fragment float4 f_tex8(VOut in [[stage_in]],
    texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]],
    texture2d<float> t2 [[texture(2)]], texture2d<float> t3 [[texture(3)]],
    texture2d<float> t4 [[texture(4)]], texture2d<float> t5 [[texture(5)]],
    texture2d<float> t6 [[texture(6)]], texture2d<float> t7 [[texture(7)]], sampler s [[sampler(0)]]) {
    float4 a=t0.sample(s,in.uv), b=t1.sample(s,in.uv), c=t2.sample(s,in.uv), d=t3.sample(s,in.uv);
    float4 e=t4.sample(s,in.uv), f=t5.sample(s,in.uv), g=t6.sample(s,in.uv), h=t7.sample(s,in.uv);
    float4 ab=select(a,b,in.uv.x>1e3), cd=select(c,d,in.uv.y>1e3), ef=select(e,f,in.uv.x<-1e3), gh=select(g,h,in.uv.y<-1e3);
    return select(select(ab,cd,in.uv.x>2e3),select(ef,gh,in.uv.x<-2e3),in.uv.y>2e3); }
