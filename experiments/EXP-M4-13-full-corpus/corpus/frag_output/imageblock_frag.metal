#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// fragment reads the implicit-layout imageblock (tile memory) for current fragment
struct IB { half4 color [[color(0)]]; };
fragment half4 fMain(VOut in [[stage_in]], imageblock<IB, imageblock_layout_implicit> blk) {
    IB d = blk.read();
    d.color = d.color * half(0.5) + half4(in.col) * half(0.5);
    blk.write(d);
    return d.color;
}
