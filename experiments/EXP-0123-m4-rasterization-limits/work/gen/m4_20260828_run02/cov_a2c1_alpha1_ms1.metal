#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut vs_full(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) };
    VOut o; o.position = float4(pos[vid], 0.5, 1.0); return o;
}
fragment float4 fs_cov() { return float4(1,1,1,1.0); }
