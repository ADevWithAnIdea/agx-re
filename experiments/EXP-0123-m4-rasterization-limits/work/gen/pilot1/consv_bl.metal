#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut vs_tri(uint vid [[vertex_id]]) {
    float2 px[3] = { float2(4.0,5.0), float2(4.2,5.0), float2(4.0,4.8) };
    float2 p2 = px[vid];
    float2 ndc = float2((p2.x/float(8))*2.0-1.0, 1.0-(p2.y/float(8))*2.0);
    VOut o; o.position = float4(ndc, 0.0, 1.0); return o;
}
fragment float4 fs_white() { return float4(1,1,1,1); }
