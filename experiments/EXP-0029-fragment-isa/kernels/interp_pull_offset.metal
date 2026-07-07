#include <metal_stdlib>
using namespace metal;
// Pull-model interpolation (interpolate_at_*). Vertex writes a plain varying; the
// fragment receives it as an `interpolant<>` and explicitly samples it. Variants
// change only the interpolate_at_* call. Clean-room: OUR OWN MSL.
struct VOut {
    float4 pos   [[position]];
    float4 c     [[user(locn0)]];
};
struct FIn {
    interpolant<float4, interpolation::perspective> c [[user(locn0)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o;
    o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.c   = float4(p * 0.5, 0.25, 1.0);
    return o;
}
fragment float4 f_main(FIn in [[stage_in]]) {
    return in.c.interpolate_at_offset(float2(0.25, 0.25));  // <-- PULL
}
