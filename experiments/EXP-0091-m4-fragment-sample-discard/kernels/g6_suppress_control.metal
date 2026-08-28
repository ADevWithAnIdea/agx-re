#include <metal_stdlib>
using namespace metal;
// Control for g6_suppress.metal: identical body, NO discard, for baseline ctr[0]
// count and baseline buf[]/color/depth pattern.
struct FDOut { float4 color [[color(0)]]; float d [[depth(any)]]; };
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment FDOut f_main(float4 pos [[position]],
                       device uint *buf [[buffer(0)]],
                       device atomic_uint *ctr [[buffer(1)]],
                       constant uint2 &dims [[buffer(2)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    buf[idx] = 0xC0FFEEu + idx;
    atomic_fetch_add_explicit(&ctr[0], 1u, memory_order_relaxed);
    FDOut o;
    o.color = float4(0.75, 0.5, 0.25, 1.0);
    o.d = 0.1;
    return o;
}
