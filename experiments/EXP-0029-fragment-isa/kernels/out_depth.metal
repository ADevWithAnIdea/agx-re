#include <metal_stdlib>
using namespace metal;
// [[depth]] fragment output: shader-written depth. Isolates the depth-store encoding.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct FOut {
    float4 color [[color(0)]];
    float  depth [[depth(any)]];
};
fragment FOut f_main(constant float *d [[buffer(0)]]) {
    FOut o;
    o.color = float4(0.75, 0.5, 0.25, 1.0);
    o.depth = d[0];
    return o;
}
