#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// raster_order_group forces ordered tilebuffer access on the color input
fragment half4 fMain(VOut in [[stage_in]], half4 dst [[color(0), raster_order_group(0)]]) {
    return dst * half(1.0h - in.col.a) + half4(in.col) * half(in.col.a);
}
