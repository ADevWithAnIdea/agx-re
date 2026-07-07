#include <metal_stdlib>
using namespace metal;
// Control for rog.metal: SAME read-modify-write of a read_write texture but with
// NO [[raster_order_group]] tag. Diff vs rog.metal isolates any pixel-ordering
// (wait_pix/signal_pix) op the ROG tag inserts. OUR OWN MSL.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment void f_main(texture2d<float, access::read_write> tex [[texture(0)]],
                     float4 pos [[position]]) {
    ushort2 c = ushort2(pos.xy);
    float4 v = tex.read(c);
    tex.write(v + float4(1.0), c);
}
