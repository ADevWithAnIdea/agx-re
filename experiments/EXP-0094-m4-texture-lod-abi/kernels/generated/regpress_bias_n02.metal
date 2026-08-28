// EXP-0094 generated register-pressure probe (bias, N=2), v3.
// analysis/gen_regpressure.py -- do not hand-edit. bias/junk values arrive as
// a per-vertex-interpolated varying (stage_in), NOT a direct constant-buffer
// read, so the fragment compiler cannot hoist them to the preamble -- see the
// v3 header note in this file for why v1/v2 failed.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position [[position]];
    float4 vbias [[user(locn0)]];   // x=uvScaleX y=uvScaleY z=biasVal w=unused
    float4 vj0 [[user(locn1)]];
};

vertex VOut vmain(uint vid [[vertex_id]], constant float *params [[buffer(0)]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.position = float4(p[vid], 0, 1);
    o.vbias = float4(params[0], params[1], params[2], 0);
    o.vj0 = float4(params[4], params[5], 0, 0);
    return o;
}

fragment float4 fmain(VOut in [[stage_in]],
                       texture2d<float> tex [[texture(0)]],
                       sampler s [[sampler(0)]]) {
    float2 uv = in.position.xy * float2(in.vbias.x, in.vbias.y);
    float j0 = in.vj0.x;
    float j1 = in.vj0.y;
    float sink = j0;
    sink = sink * j1 - j0;
    float biasVal = in.vbias.z;
    float v = tex.sample(s, uv, bias(biasVal)).r;
    return float4(v, sink, 0, 1);
}
