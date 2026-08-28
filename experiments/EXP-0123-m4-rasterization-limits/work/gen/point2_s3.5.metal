#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; float point_size [[point_size]]; };
vertex VOut vs_pt(uint vid [[vertex_id]]) {
    float2 p = float2(16.5, 16.5); // exact center of pixel (16,16) in a 32x32 target
    float2 ndc = float2( (p.x/float(32))*2.0-1.0, 1.0-(p.y/float(32))*2.0 );
    VOut o; o.position = float4(ndc, 0.0, 1.0); o.point_size = 3.5;
    return o;
}
fragment float4 fs_pt() { return float4(1,1,1,1); }
