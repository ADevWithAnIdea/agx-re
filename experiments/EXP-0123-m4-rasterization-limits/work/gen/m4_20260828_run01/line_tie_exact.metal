#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut vs_line(uint vid [[vertex_id]]) {
    float2 px[2] = { float2(1.0,4.0), float2(7.0,4.0) };
    float2 p2 = px[vid];
    float2 ndc = float2( (p2.x/float(8))*2.0-1.0, 1.0-(p2.y/float(8))*2.0 );
    VOut o; o.position = float4(ndc, 0.0, 1.0);
    return o;
}
fragment float4 fs_line() { return float4(1,1,1,1); }
