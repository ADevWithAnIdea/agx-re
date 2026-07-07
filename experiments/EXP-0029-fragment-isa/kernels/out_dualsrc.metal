#include <metal_stdlib>
using namespace metal;
// Dual-source blend: two outputs at color(0) index(0)/index(1). Isolates the
// output-index (second source) field in the colour-store epilog. OUR OWN MSL.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct FOut {
    float4 s0 [[color(0), index(0)]];
    float4 s1 [[color(0), index(1)]];
};
fragment FOut f_main() {
    FOut o;
    o.s0 = float4(0.70, 0.50, 0.25, 1.0);
    o.s1 = float4(0.10, 0.20, 0.30, 0.4);
    return o;
}
