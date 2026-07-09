// Vertex output [[point_size]] alongside [[position]].
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float ps [[point_size]]; float4 v; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vb [[buffer(0)]]) {
    VOut o; o.pos = vb[vid]; o.ps = clamp(vb[vid].w * 8.0, 1.0, 64.0); o.v = vb[vid]; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.v; }
