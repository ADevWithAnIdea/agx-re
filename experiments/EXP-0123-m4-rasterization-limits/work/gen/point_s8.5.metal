#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; float point_size [[point_size]]; };
vertex VOut vs_pt(uint vid [[vertex_id]]) {
    VOut o; o.position = float4(0.0, 0.0, 0.0, 1.0); o.point_size = 8.5;
    return o;
}
fragment float4 fs_pt() { return float4(1,1,1,1); }
