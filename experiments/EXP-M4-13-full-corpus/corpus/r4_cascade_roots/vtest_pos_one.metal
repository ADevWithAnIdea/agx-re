#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.col = float4(p[vid].x,p[vid].y,0.25,0.75); return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.col; }
