#include <metal_stdlib>
using namespace metal;
// discard_fragment() with NO branch at all (unconditional every-lane kill). Isolates
// the submission op from any comparison/branch machinery.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main() {
    discard_fragment();
    return float4(0.75, 0.5, 0.25, 1.0);
}
