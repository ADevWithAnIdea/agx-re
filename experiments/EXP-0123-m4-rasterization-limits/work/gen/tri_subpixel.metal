#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut vs_tri(uint vid [[vertex_id]]) {
    // pixel coords in an 8x8 target; triangle occupies a small corner sliver
    // near pixel (4,4)'s top-left corner (4.0,4.0), NOT covering the center (4.5,4.5)
    float2 px[3] = { float2(4.0,4.0), float2(4.2,4.0), float2(4.0,4.2) };
    float2 p = px[vid];
    float2 ndc = float2((p.x/8.0)*2.0-1.0, 1.0-(p.y/8.0)*2.0);
    VOut o; o.position = float4(ndc,0.0,1.0); return o;
}
fragment float4 fs_white() { return float4(1,1,1,1); }
