#include <metal_stdlib>
using namespace metal;

// Texture sample with implicit LOD. tex.sample(s, uv) in a fragment shader
// computes the LOD from the screen-space derivatives of uv -- an
// implicit-LOD sample, which is fragment-only (compute must use sample_lod /
// gradients explicitly). Exercises the sampler + derivative machinery.
// Clean-room: OUR OWN MSL (OWN-SHADER).

struct VOut {
    float4 pos [[position]];
    float2 uv  [[user(locn0)]];
};

vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o;
    o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.uv = p;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]],
                       texture2d<float> tex [[texture(0)]],
                       sampler s [[sampler(0)]]) {
    return tex.sample(s, in.uv);
}
