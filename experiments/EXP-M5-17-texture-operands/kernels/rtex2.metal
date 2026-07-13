// EXP-M5-17: dual-sample "select(a,b,opaque-false)" kernels. Both sample ops stay
// live (no DCE), differ in exactly ONE field, and the pixel returns 'a'. Splicing
// the first op's field -> the pixel flips to the second resource's value.
// CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float2 uvA;   // -> texel (0,0)
    float2 uvB;   // -> texel (1,1)
    float2 uvR;   // out-of-range: clamp vs repeat give different texels
};

vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.pos = float4(p[vid], 0, 1);
    o.uvA = float2(0.25, 0.25);
    o.uvB = float2(0.75, 0.75);
    o.uvR = float2(1.25, 1.25);
    return o;
}

// SAMPLER-slot probe with an out-of-range coord: s0(clamp) vs s1(repeat) give
// distinct texels, so the pixel proves which sampler slot the op used.
// a = sample(s0, uvR) -> returns a (sampler-0 result).
fragment float4 f_sampaddr(VOut in [[stage_in]],
                           texture2d<float> t [[texture(0)]],
                           sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]]) {
    float4 a = t.sample(s0, in.uvR);
    float4 b = t.sample(s1, in.uvR);
    return select(a, b, in.uvA.x > 1000.0);
}

// COORD: a=sample(uvA), b=sample(uvB); cond false -> returns a (texel 0,0).
// The two ops differ only in the coordinate register.
fragment float4 f_coord(VOut in [[stage_in]],
                        texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    float4 a = t.sample(s, in.uvA);
    float4 b = t.sample(s, in.uvB);
    return select(a, b, in.uvA.x > 1000.0);
}

// TEXSLOT: a=sample(t0), b=sample(t1); returns a (slot-0 color).
fragment float4 f_texslot(VOut in [[stage_in]],
                          texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]],
                          sampler s [[sampler(0)]]) {
    float4 a = t0.sample(s, in.uvA);
    float4 b = t1.sample(s, in.uvA);
    return select(a, b, in.uvA.x > 1000.0);
}

// SAMPSLOT: a=sample(s0), b=sample(s1); returns a (sampler-0 result).
fragment float4 f_sampslot(VOut in [[stage_in]],
                           texture2d<float> t [[texture(0)]],
                           sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]]) {
    float4 a = t.sample(s0, in.uvA);
    float4 b = t.sample(s1, in.uvA);
    return select(a, b, in.uvA.x > 1000.0);
}

// LODSEL: a=sample level0, b=sample level1; returns a (level-0 color).
fragment float4 f_lodsel(VOut in [[stage_in]],
                         texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    float4 a = t.sample(s, in.uvA, level(0.0));
    float4 b = t.sample(s, in.uvA, level(1.0));
    return select(a, b, in.uvA.x > 1000.0);
}

// READSEL: a=read(0,0), b=read(1,1); returns a (texel 0,0). No sampler.
fragment float4 f_readsel(VOut in [[stage_in]],
                          texture2d<float> t [[texture(0)]]) {
    float4 a = t.read(uint2(0, 0));
    float4 b = t.read(uint2(1, 1));
    return select(a, b, in.uvA.x > 1000.0);
}
