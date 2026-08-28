#include <metal_stdlib>
using namespace metal;
// Divergent if/reconverge WITHOUT discard_fragment(), driven by a buffer value so the
// compiler cannot fold the branch away. Isolates plain-branch/reconverge bytes from
// discard-specific bytes when byte-diffed against loc_if_discard.metal.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(constant float *thresh [[buffer(0)]], float4 pos [[position]]) {
    float4 c = float4(0.75, 0.5, 0.25, 1.0);
    if (pos.x < thresh[0]) { c.g = 0.9; }
    return c;
}
