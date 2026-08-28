#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position [[position]];
};

vertex VOut v_main(uint vid [[vertex_id]]) {
    // Fullscreen triangle, positions authored directly (no vertex buffer).
    float2 pos[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    VOut o;
    o.position = float4(pos[vid], 0.0, 1.0);
    return o;
}

fragment float4 f_main() {
    return float4(1.0, 0.0, 0.0, 1.0); // solid red
}
