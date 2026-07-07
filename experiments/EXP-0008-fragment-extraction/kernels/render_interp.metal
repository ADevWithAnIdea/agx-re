#include <metal_stdlib>
using namespace metal;

// Interpolated varying: the vertex emits a per-vertex colour; the fragment
// reads it via [[stage_in]]. This forces the fragment to perform perspective
// varying interpolation (barycentric), an instruction family that does NOT
// exist in compute shaders.
// Clean-room: OUR OWN MSL (OWN-SHADER).

struct VOut {
    float4 pos   [[position]];
    float4 color [[user(locn0)]];
};

vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o;
    o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.color = float4(p, 0.0, 1.0);
    return o;
}

fragment float4 f_main(VOut in [[stage_in]]) {
    return in.color;
}
