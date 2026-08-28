#include <metal_stdlib>
using namespace metal;
// Unconditional compile-time-constant sample_mask = 0 (equivalent in effect to a
// full discard, but through the explicit sample_mask stage-out instead of
// discard_fragment()). No branch.
struct VOut { float4 pos [[position]]; };
struct FOut { float4 color [[color(0)]]; uint mask [[sample_mask]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment FOut f_main() {
    FOut o;
    o.color = float4(0.75, 0.5, 0.25, 1.0);
    o.mask = 0u;
    return o;
}
