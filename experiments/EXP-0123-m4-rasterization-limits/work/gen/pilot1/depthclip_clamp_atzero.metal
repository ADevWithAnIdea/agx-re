#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut vs_tri(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-0.8,-0.8), float2(0.8,-0.8), float2(0.0,0.8) };
    VOut o; o.position = float4(pos[vid], 0.0, 1.0);
    return o;
}
fragment float4 fs_white() { return float4(1,1,1,1); }
