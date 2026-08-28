#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment void f_main(texture2d<uint, access::read_write> tex
                        [[raster_order_group(127), texture(0)]]) {
    uint v = tex.read(uint2(0,0)).r;
    tex.write(uint4(v + 1u,0,0,0), uint2(0,0));
}
