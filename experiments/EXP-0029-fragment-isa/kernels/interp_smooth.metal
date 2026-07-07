#include <metal_stdlib>
using namespace metal;
// Interpolation-mode probe. Vertex emits a per-vertex colour; fragment reads it
// via [[stage_in]]. The ONLY thing that changes across the interp_* kernels is
// the interpolation qualifier on `color` -> isolates the interpolation-mode
// field in the fragment `iter` instruction. Clean-room: OUR OWN MSL.
struct VOut {
    float4 pos   [[position]];
    float4 color [[user(locn0)]] [[center_perspective]];  // <-- MODE
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o;
    o.pos   = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.color = float4(p * 0.5, 0.25, 1.0);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    return in.color;
}
