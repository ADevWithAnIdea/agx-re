#include <metal_stdlib>
using namespace metal;

// EXP-0034 texture-variant battery -- FRAGMENT stage. Implicit-LOD sample_compare
// (real shadow-map path) + gather/offset variants that need the fragment quad.
// Shares a uv-passthrough vertex. Clean-room: OUR OWN MSL (OWN-SHADER).

struct VOut {
    float4 pos [[position]];
    float2 uv  [[user(locn0)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); o.uv = p; return o;
}

// implicit-LOD depth compare (the classic shadow-map fragment path)
fragment float4 f_scmp(VOut in [[stage_in]],
                       depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    float r = t.sample_compare(s, in.uv, 0.5);
    return float4(r, 0.0, 0.0, 1.0);
}
// implicit-LOD depth compare with a constant texel offset
fragment float4 f_scmp_off(VOut in [[stage_in]],
                           depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    float r = t.sample_compare(s, in.uv, 0.5, int2(1, 0));
    return float4(r, 0.0, 0.0, 1.0);
}
// gather_compare (fragment)
fragment float4 f_gcmp(VOut in [[stage_in]],
                       depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.gather_compare(s, in.uv, 0.5);
}
// plain implicit-LOD sample (baseline for the depth-compare byte-diff)
fragment float4 f_sample(VOut in [[stage_in]],
                         texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv);
}
// gather z / w to finish the component enum in fragment too
fragment float4 f_gather_z(VOut in [[stage_in]],
                           texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.gather(s, in.uv, int2(0), component::z);
}
fragment float4 f_gather_w(VOut in [[stage_in]],
                           texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.gather(s, in.uv, int2(0), component::w);
}
// sample with constant texel offset (fragment)
fragment float4 f_sample_off(VOut in [[stage_in]],
                             texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv, int2(1, 1));
}
