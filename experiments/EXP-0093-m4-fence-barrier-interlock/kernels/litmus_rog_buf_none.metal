#include <metal_stdlib>
using namespace metal;
// WEAK control for litmus_rog_buf.metal: no [[raster_order_group]] tag.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment void f_main(device uint *ctr [[buffer(0)]]) {
    uint v = ctr[0];
    ctr[0] = v + 1u;
}
