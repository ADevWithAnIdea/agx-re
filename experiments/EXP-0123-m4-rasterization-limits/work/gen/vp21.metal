#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; uint vpidx [[viewport_array_index]]; };
vertex VOut vs_vp(uint vid [[vertex_id]], uint iid [[instance_id]]) {
    float2 pos[3] = { float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) };
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); o.vpidx = iid % 21;
    return o;
}
fragment float4 fs_white() { return float4(1,1,1,1); }
