// EXP-M5-17: M5 texture SAMPLE/READ operand mapping via agxrender splice-and-observe.
// CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected. Fragment->pixel deltas only.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float2 uvA;   // interpolates to a fixed value everywhere (const across the 3 verts)
    float2 uvB;   // ditto, distinct value -> distinct texel of a 2x2
};

// Full-screen triangle. Both varyings are CONSTANT across the 3 vertices, so each
// interpolates to a known fixed value at every covered pixel yet is OPAQUE to the
// compiler (comes through stage_in), forcing a real coordinate REGISTER rather
// than a folded immediate.
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.pos = float4(p[vid], 0, 1);
    o.uvA = float2(0.25, 0.25);   // nearest -> texel (0,0)
    o.uvB = float2(0.75, 0.75);   // nearest -> texel (1,1)
    return o;
}

// ---- coordinate-register probe: identical but for which varying feeds sample ----
fragment float4 f_coordA(VOut in [[stage_in]],
                         texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uvA);
}
fragment float4 f_coordB(VOut in [[stage_in]],
                         texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uvB);
}

// ---- texture-slot probe: two bound textures, select slot 0 vs slot 1 ----
fragment float4 f_tex0(VOut in [[stage_in]],
                       texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]],
                       sampler s [[sampler(0)]]) {
    return t0.sample(s, in.uvA);
}
fragment float4 f_tex1(VOut in [[stage_in]],
                       texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]],
                       sampler s [[sampler(0)]]) {
    return t1.sample(s, in.uvA);
}

// ---- sampler-slot probe: two bound samplers, select slot 0 vs slot 1 ----
fragment float4 f_samp0(VOut in [[stage_in]],
                        texture2d<float> t [[texture(0)]],
                        sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]]) {
    return t.sample(s0, in.uvA);
}
fragment float4 f_samp1(VOut in [[stage_in]],
                        texture2d<float> t [[texture(0)]],
                        sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]]) {
    return t.sample(s1, in.uvA);
}

// ---- LOD-operand probe ----
fragment float4 f_lod0(VOut in [[stage_in]],
                       texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uvA, level(0.0));
}
fragment float4 f_lod1(VOut in [[stage_in]],
                       texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uvA, level(1.0));
}
fragment float4 f_lod2(VOut in [[stage_in]],
                       texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uvA, level(2.0));
}
fragment float4 f_lodreg(VOut in [[stage_in]],
                         texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uvA, level(in.uvB.x));   // register LOD from a varying
}
fragment float4 f_bias(VOut in [[stage_in]],
                       texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uvA, bias(1.0));
}

// ---- unfiltered READ probe (integer coord, no sampler) ----
fragment float4 f_read0(VOut in [[stage_in]],
                        texture2d<float> t [[texture(0)]]) {
    return t.read(uint2(0, 0));
}
fragment float4 f_read1(VOut in [[stage_in]],
                        texture2d<float> t [[texture(0)]]) {
    return t.read(uint2(1, 1));
}
