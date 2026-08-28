#include <metal_stdlib>
using namespace metal;
// GLFS-A08 / ATOM-11 litmus (device BUFFER, STRONG/protected): same non-atomic
// RMW-count invariant as litmus_rog_tex.metal but through a device buffer
// instead of a texture, to compare whether raster-order-group mutual exclusion
// also covers ordinary buffer/image accesses (not just texture caches).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment void f_main(device uint *ctr [[raster_order_group(0), buffer(0)]]) {
    uint v = ctr[0];
    ctr[0] = v + 1u;
}
