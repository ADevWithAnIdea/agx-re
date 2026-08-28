// EXP-0094 regpair_bias_B.metal -- own MSL, v2 (varying-routed, forces
// genuine per-fragment residency -- see analysis/gen_regpressure.py v3 header
// for why a direct `constant float*` read is NOT sufficient: it gets hoisted
// to the shader preamble as a provably-uniform value, defeating the point).
// Minimal differential-compilation pair (B side): biasA and biasB both arrive
// as components of a per-vertex-interpolated varying (all 3 vertices write
// the SAME value, so the interpolated per-fragment result is numerically
// constant, but the FRAGMENT compiler has no visibility into that -- a
// stage_in field is always treated as per-fragment-varying). This variant
// feeds biasA to bias(); biasB is sunk into the g channel. regpair_bias_B.metal
// is byte-identical source except which named field feeds bias() and which
// feeds the sink -- any AGX byte that differs between the two compiled
// fragment outputs is a candidate for "the register the sample instruction
// reads the bias operand from".
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position [[position]];
    float4 vbias [[user(locn0)]];   // x=uvScaleX y=uvScaleY z=biasA w=biasB
};

vertex VOut vmain(uint vid [[vertex_id]], constant float *params [[buffer(0)]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.position = float4(p[vid], 0, 1);
    o.vbias = float4(params[0], params[1], params[2], params[3]);
    return o;
}

fragment float4 fmain(VOut in [[stage_in]],
                       texture2d<float> tex [[texture(0)]],
                       sampler s [[sampler(0)]]) {
    float2 uv = in.position.xy * float2(in.vbias.x, in.vbias.y);
    float biasA = in.vbias.z;
    float biasB = in.vbias.w;
    float v = tex.sample(s, uv, bias(biasB)).r;
    return float4(v, biasA, 0, 1);
}
