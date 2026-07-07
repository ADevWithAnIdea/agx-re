#include <metal_stdlib>
using namespace metal;

// Explicit screen-space derivatives: dfdx/dfdy of an interpolated varying.
// Derivative (quad-difference) instructions are fragment-only.
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

fragment float4 f_main(VOut in [[stage_in]]) {
    float2 dx = dfdx(in.uv);
    float2 dy = dfdy(in.uv);
    return float4(dx + dy, 0.0, 1.0);
}
