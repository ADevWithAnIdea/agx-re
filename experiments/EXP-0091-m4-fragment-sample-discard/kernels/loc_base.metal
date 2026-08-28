#include <metal_stdlib>
using namespace metal;
// Baseline: no branch, no discard, no sample_mask write. Reference for byte-diff.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main() {
    return float4(0.75, 0.5, 0.25, 1.0);
}
