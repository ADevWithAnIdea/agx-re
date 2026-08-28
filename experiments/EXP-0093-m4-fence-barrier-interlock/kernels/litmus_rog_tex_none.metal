#include <metal_stdlib>
using namespace metal;
// WEAK control for litmus_rog_tex.metal: identical non-atomic RMW counter
// increment, NO [[raster_order_group]] tag. If the final value is < N for
// N > 1 overlapping fragments, increments were lost to a race -- the expected
// falsifier this control exists to trigger.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment void f_main(texture2d<uint, access::read_write> ctr [[texture(0)]]) {
    uint v = ctr.read(uint2(0, 0)).r;
    ctr.write(uint4(v + 1u, 0, 0, 0), uint2(0, 0));
}
