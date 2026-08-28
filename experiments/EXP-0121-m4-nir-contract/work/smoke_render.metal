#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float v0 [[flat]]; float v1; float v2; float v3; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.v0 = 100.0; o.v1 = 101.0; o.v2 = 102.0; o.v3 = 103.0;
    return o;
}
fragment float4 f_main(VOut in [[stage_in]], device uint *buf [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)in.pos.x, py = (uint)in.pos.y;
    uint idx = py * dims.x + px;
    float arr[4] = { in.v0, in.v1, in.v2, in.v3 };
    uint sel = px % 4u;
    buf[idx] = as_type<uint>(arr[sel]);
    return float4(0,0,0,1);
}
