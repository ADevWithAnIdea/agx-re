#include <metal_stdlib>
using namespace metal;

// EXP-0016 texture/sample instruction battery -- FRAGMENT stage.
// Every fragment shares the same uv-passthrough vertex v_main (full-screen
// triangle from vertex_id, no vertex buffer). Each fragment provokes exactly
// one texture op / variant so byte-diffing localizes the fields.
// Clean-room: OUR OWN MSL (OWN-SHADER).

struct VOut {
    float4 pos [[position]];
    float2 uv  [[user(locn0)]];
    float2 ga  [[user(locn1)]];   // an independent varying used as an explicit gradient
};

vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o;
    o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.uv  = p;
    o.ga  = p * 0.5;
    return o;
}

// ---- Sample variant selector (all implicit/explicit LOD) ----

// baseline: implicit-LOD sample (LOD from derivatives)
fragment float4 f_sample(VOut in [[stage_in]],
                         texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv);
}

// LOD bias
fragment float4 f_bias(VOut in [[stage_in]],
                       texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv, bias(1.0));
}

// explicit LOD (level)
fragment float4 f_lod(VOut in [[stage_in]],
                      texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv, level(1.0));
}

// explicit gradient
fragment float4 f_grad(VOut in [[stage_in]],
                       texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv, gradient2d(in.ga, in.ga.yx));
}

// gather (2x2), default component .x
fragment float4 f_gather(VOut in [[stage_in]],
                         texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.gather(s, in.uv);
}

// gather component .y
fragment float4 f_gather_y(VOut in [[stage_in]],
                           texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.gather(s, in.uv, int2(0), component::y);
}

// ---- Texture-slot / sampler-slot references (two ops in one shader) ----

// two textures, same sampler -> the field that differs between the two samples
// is the TEXTURE slot.
fragment float4 f_two_tex(VOut in [[stage_in]],
                          texture2d<float> t0 [[texture(0)]],
                          texture2d<float> t1 [[texture(1)]],
                          sampler s [[sampler(0)]]) {
    return t0.sample(s, in.uv) + t1.sample(s, in.uv) * 0.0 + t1.sample(s, in.uv);
}

// one texture, two samplers -> the field that differs is the SAMPLER slot.
fragment float4 f_two_samp(VOut in [[stage_in]],
                           texture2d<float> t [[texture(0)]],
                           sampler s0 [[sampler(0)]],
                           sampler s1 [[sampler(1)]]) {
    return t.sample(s0, in.uv) + t.sample(s1, in.uv);
}

// texture at binding index 1 only (cross-shader slot test vs f_sample)
fragment float4 f_tex1(VOut in [[stage_in]],
                       texture2d<float> t [[texture(1)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv);
}

// sampler at binding index 1 only (cross-shader slot test vs f_sample)
fragment float4 f_samp1(VOut in [[stage_in]],
                        texture2d<float> t [[texture(0)]], sampler s [[sampler(1)]]) {
    return t.sample(s, in.uv);
}

// ---- Result component count (return .x vs full float4) ----

fragment float4 f_sample_x(VOut in [[stage_in]],
                           texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return float4(t.sample(s, in.uv).x, 0.0, 0.0, 1.0);
}

// ---- Texture read (no sampler) ----

fragment float4 f_read(VOut in [[stage_in]], texture2d<float> t [[texture(0)]]) {
    uint2 c = uint2(in.uv * 4.0);
    return t.read(c);
}

fragment float4 f_read_lod(VOut in [[stage_in]], texture2d<float> t [[texture(0)]]) {
    uint2 c = uint2(in.uv * 4.0);
    return t.read(c, 1);           // read explicit mip level
}

// ---- Texture queries ----

fragment float4 f_width(VOut in [[stage_in]], texture2d<float> t [[texture(0)]]) {
    return float4(float(t.get_width()) / 255.0, 0.0, 0.0, 1.0);
}

fragment float4 f_height(VOut in [[stage_in]], texture2d<float> t [[texture(0)]]) {
    return float4(float(t.get_height()) / 255.0, 0.0, 0.0, 1.0);
}

fragment float4 f_nmips(VOut in [[stage_in]], texture2d<float> t [[texture(0)]]) {
    return float4(float(t.get_num_mip_levels()) / 255.0, 0.0, 0.0, 1.0);
}

fragment float4 f_wh(VOut in [[stage_in]], texture2d<float> t [[texture(0)]]) {
    return float4(float(t.get_width()) / 255.0, float(t.get_height()) / 255.0, 0.0, 1.0);
}
