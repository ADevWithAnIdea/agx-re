#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return float4(1); }
