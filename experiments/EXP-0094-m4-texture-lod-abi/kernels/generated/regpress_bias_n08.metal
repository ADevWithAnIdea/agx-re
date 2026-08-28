// EXP-0094 generated register-pressure probe (bias, N=8), v3.
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
    float4 vj1 [[user(locn2)]];
};

vertex VOut vmain(uint vid [[vertex_id]], constant float *params [[buffer(0)]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.position = float4(p[vid], 0, 1);
    o.vbias = float4(params[0], params[1], params[2], 0);
    o.vj0 = float4(params[4], params[5], params[6], params[7]);
    o.vj1 = float4(params[8], params[9], params[10], params[11]);
    return o;
}

fragment float4 fmain(VOut in [[stage_in]],
                       texture2d<float> tex [[texture(0)]],
                       sampler s [[sampler(0)]]) {
    float2 uv = in.position.xy * float2(in.vbias.x, in.vbias.y);
    float j0 = in.vj0.x;
    float j1 = in.vj0.y;
    float j2 = in.vj0.z;
    float j3 = in.vj0.w;
    float j4 = in.vj1.x;
    float j5 = in.vj1.y;
    float j6 = in.vj1.z;
    float j7 = in.vj1.w;
    float sink = j0;
    sink = sink * j1 - j0;
    sink = max(sink, j2) + sink * 0.0001f;
    sink = fma(sink, 1.00004f, j3);
    sink = sink * j4 - j3;
    sink = max(sink, j5) + sink * 0.0001f;
    sink = fma(sink, 1.00007f, j6);
    sink = sink * j7 - j6;
    float biasVal = in.vbias.z;
    float v = tex.sample(s, uv, bias(biasVal)).r;
    return float4(v, sink, 0, 1);
}
