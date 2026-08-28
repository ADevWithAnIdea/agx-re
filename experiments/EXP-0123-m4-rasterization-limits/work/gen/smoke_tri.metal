#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut vs_smoke(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-0.9,-0.9), float2(0.9,-0.9), float2(0.0,0.9) };
    VOut o; o.position = float4(pos[vid], 0.0, 1.0);
    return o;
}
fragment float4 fs_smoke() {
    return float4(1.0, 0.5, 0.25, 1.0);
}
