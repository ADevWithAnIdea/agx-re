// c_iter.metal -- EXP-0143 carrier for the interpolation family
// (iter / vary_slot / vary_store).  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// Vertex stage emits FOUR distinct, asymmetric, linearly-interpolated varyings
// (v0..v3) plus [[position]].  The fragment stage reads them and writes them
// straight to the colour attachment, so every interpolated value is LIVE on the
// observed pixel: a change in any `iter` field that alters the interpolated
// result must appear in the read-back float.
//
// Vertex positions/varyings are computed ARITHMETICALLY from vertex_id (no
// constant-array indexing) so the compiled vertex program tokenizes cleanly
// under tools/agx-isa and the varying stores can be located by the DB rather
// than by hand-counted byte offsets.
//
// Per-vertex varying values (vid = 0,1,2) are mutually non-affine so that a
// slot mix-up is always numerically visible:
//   v0 = 1 + f          -> 1,    2,    3
//   v1 = 10 + f*f       -> 10,   11,   14
//   v2 = 100 - 3f       -> 100,  97,   94
//   v3 = 1000 + 5f*f-2f -> 1000, 1003, 1016

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0;
    float  v1;
    float  v2;
    float  v3;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0  = 1.0f    + f;
    o.v1  = 10.0f   + f * f;
    o.v2  = 100.0f  - 3.0f * f;
    o.v3  = 1000.0f + 5.0f * f * f - 2.0f * f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.v0, in.v1, in.v2, in.v3);
}
