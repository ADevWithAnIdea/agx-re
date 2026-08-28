#include <metal_stdlib>
using namespace metal;
// FS-01/FS-03: raw-bit readback of [[position]].xy at every pixel of a full-coverage
// WxH target (asymmetric W!=H to catch an x/y swap). Oracle: pos.x = px+0.5,
// pos.y = py+0.5 for every covered pixel (upper-left-origin, pixel-center convention).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]],
                        device uint *buf [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    buf[idx*2+0] = as_type<uint>(pos.x);
    buf[idx*2+1] = as_type<uint>(pos.y);
    return float4(0,0,0,1);
}
