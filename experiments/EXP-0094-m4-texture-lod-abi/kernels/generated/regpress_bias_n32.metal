// EXP-0094 generated register-pressure probe (bias, N=32), v3.
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
    float4 vj2 [[user(locn3)]];
    float4 vj3 [[user(locn4)]];
    float4 vj4 [[user(locn5)]];
    float4 vj5 [[user(locn6)]];
    float4 vj6 [[user(locn7)]];
    float4 vj7 [[user(locn8)]];
};

vertex VOut vmain(uint vid [[vertex_id]], constant float *params [[buffer(0)]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.position = float4(p[vid], 0, 1);
    o.vbias = float4(params[0], params[1], params[2], 0);
    o.vj0 = float4(params[4], params[5], params[6], params[7]);
    o.vj1 = float4(params[8], params[9], params[10], params[11]);
    o.vj2 = float4(params[12], params[13], params[14], params[15]);
    o.vj3 = float4(params[16], params[17], params[18], params[19]);
    o.vj4 = float4(params[20], params[21], params[22], params[23]);
    o.vj5 = float4(params[24], params[25], params[26], params[27]);
    o.vj6 = float4(params[28], params[29], params[30], params[31]);
    o.vj7 = float4(params[32], params[33], params[34], params[35]);
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
    float j8 = in.vj2.x;
    float j9 = in.vj2.y;
    float j10 = in.vj2.z;
    float j11 = in.vj2.w;
    float j12 = in.vj3.x;
    float j13 = in.vj3.y;
    float j14 = in.vj3.z;
    float j15 = in.vj3.w;
    float j16 = in.vj4.x;
    float j17 = in.vj4.y;
    float j18 = in.vj4.z;
    float j19 = in.vj4.w;
    float j20 = in.vj5.x;
    float j21 = in.vj5.y;
    float j22 = in.vj5.z;
    float j23 = in.vj5.w;
    float j24 = in.vj6.x;
    float j25 = in.vj6.y;
    float j26 = in.vj6.z;
    float j27 = in.vj6.w;
    float j28 = in.vj7.x;
    float j29 = in.vj7.y;
    float j30 = in.vj7.z;
    float j31 = in.vj7.w;
    float sink = j0;
    sink = sink * j1 - j0;
    sink = max(sink, j2) + sink * 0.0001f;
    sink = fma(sink, 1.00004f, j3);
    sink = sink * j4 - j3;
    sink = max(sink, j5) + sink * 0.0001f;
    sink = fma(sink, 1.00007f, j6);
    sink = sink * j7 - j6;
    sink = max(sink, j8) + sink * 0.0001f;
    sink = fma(sink, 1.00003f, j9);
    sink = sink * j10 - j9;
    sink = max(sink, j11) + sink * 0.0001f;
    sink = fma(sink, 1.00006f, j12);
    sink = sink * j13 - j12;
    sink = max(sink, j14) + sink * 0.0001f;
    sink = fma(sink, 1.00002f, j15);
    sink = sink * j16 - j15;
    sink = max(sink, j17) + sink * 0.0001f;
    sink = fma(sink, 1.00005f, j18);
    sink = sink * j19 - j18;
    sink = max(sink, j20) + sink * 0.0001f;
    sink = fma(sink, 1.00001f, j21);
    sink = sink * j22 - j21;
    sink = max(sink, j23) + sink * 0.0001f;
    sink = fma(sink, 1.00004f, j24);
    sink = sink * j25 - j24;
    sink = max(sink, j26) + sink * 0.0001f;
    sink = fma(sink, 1.00007f, j27);
    sink = sink * j28 - j27;
    sink = max(sink, j29) + sink * 0.0001f;
    sink = fma(sink, 1.00003f, j30);
    sink = sink * j31 - j30;
    float biasVal = in.vbias.z;
    float v = tex.sample(s, uv, bias(biasVal)).r;
    return float4(v, sink, 0, 1);
}
