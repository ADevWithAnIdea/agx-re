#include <metal_stdlib>
using namespace metal;

// Minimal vertex+fragment pair. Full-screen triangle from vertex_id, no
// varyings, constant fragment colour. Baseline: the smallest render pipeline.
// Clean-room: OUR OWN MSL (OWN-SHADER).

struct VOut {
    float4 pos [[position]];
};

vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o;
    o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    return o;
}

fragment float4 f_main() {
    return float4(1.0, 0.5, 0.25, 1.0);
}
