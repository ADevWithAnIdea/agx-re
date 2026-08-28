#include <metal_stdlib>
using namespace metal;
// Both a shader sample-mask write AND discard_fragment(), to see whether they share
// one submission op or use two independent ones.
struct VOut { float4 pos [[position]]; };
struct FOut { float4 color [[color(0)]]; uint mask [[sample_mask]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment FOut f_main(constant float *thresh [[buffer(0)]], float4 pos [[position]]) {
    if (pos.x < thresh[0]) discard_fragment();
    FOut o;
    o.color = float4(0.75, 0.5, 0.25, 1.0);
    o.mask = 0xAu;
    return o;
}
