#include <metal_stdlib>
using namespace metal;
// Same ROG probe as census_rog_tex0.metal but the protected resource is a DEVICE
// BUFFER, not a texture -- tests whether the ROG acquire/release encoding is the
// same 0x07-family op for buffer/image accesses (ATOM-11, fragment side). OUR OWN
// MSL, one paired control (census_rog_buf_none.metal).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment void f_main(device float4 *buf [[raster_order_group(0), buffer(0)]],
                     float4 pos [[position]]) {
    ushort2 c = ushort2(pos.xy);
    uint idx = c.y * 4 + c.x;
    float4 v = buf[idx];
    buf[idx] = v + float4(1.0);
}
