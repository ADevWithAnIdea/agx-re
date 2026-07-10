#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float4 cc  [[centroid_perspective]];   // centroid-interpolated varying
    float4 sp  [[sample_perspective]];      // sample-interpolated varying
};

vertex VOut v(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.pos = float4(p[vid], 0, 1);
    o.cc  = float4(p[vid] * 0.5 + 0.5, 0.25, 1.0);
    o.sp  = float4(0.1, 0.2, 0.3, 0.4);
    return o;
}

// Read centroid- and sample-interpolated varyings -> the compiler emits the
// fragment centroid/sample-position preamble read (byte0==0x04 residue op).
fragment float4 f(VOut in [[stage_in]]) {
    return in.cc + in.sp;
}
