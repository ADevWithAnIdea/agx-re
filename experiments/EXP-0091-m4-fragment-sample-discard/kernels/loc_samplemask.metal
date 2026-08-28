#include <metal_stdlib>
using namespace metal;
// Explicit shader sample-mask write, NO discard. Isolates the sample_mask-write op
// (if distinct) from the discard op.
struct VOut { float4 pos [[position]]; };
struct FOut { float4 color [[color(0)]]; uint mask [[sample_mask]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment FOut f_main(constant float *thresh [[buffer(0)]], float4 pos [[position]]) {
    FOut o;
    o.color = float4(0.75, 0.5, 0.25, 1.0);
    o.mask = (pos.x < thresh[0]) ? 0x5u : 0xFu;
    return o;
}
