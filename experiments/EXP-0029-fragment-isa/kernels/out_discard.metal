#include <metal_stdlib>
using namespace metal;
// discard_fragment(): conditional kill. Isolates the discard encoding vs out_const.
// Discard driven by a device-loaded uniform so the compiler can't fold it away.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(constant float *thresh [[buffer(0)]],
                       float4 pos [[position]]) {
    if (pos.x < thresh[0]) discard_fragment();
    return float4(0.75, 0.5, 0.25, 1.0);
}
