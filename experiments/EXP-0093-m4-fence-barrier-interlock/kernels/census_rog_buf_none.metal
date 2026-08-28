#include <metal_stdlib>
using namespace metal;
// Control for census_rog_buf0.metal: same device-buffer RMW, no [[raster_order_group]].
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment void f_main(device float4 *buf [[buffer(0)]],
                     float4 pos [[position]]) {
    ushort2 c = ushort2(pos.xy);
    uint idx = c.y * 4 + c.x;
    float4 v = buf[idx];
    buf[idx] = v + float4(1.0);
}
