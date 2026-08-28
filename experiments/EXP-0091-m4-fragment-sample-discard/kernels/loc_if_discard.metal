#include <metal_stdlib>
using namespace metal;
// Divergent if + discard_fragment(): the EXP-0029 out_discard.metal probe, recompiled
// under this experiment's own hashes for a clean differential-compile chain.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(constant float *thresh [[buffer(0)]], float4 pos [[position]]) {
    if (pos.x < thresh[0]) discard_fragment();
    return float4(0.75, 0.5, 0.25, 1.0);
}
