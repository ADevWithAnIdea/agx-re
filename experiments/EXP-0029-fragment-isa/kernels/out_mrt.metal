#include <metal_stdlib>
using namespace metal;
// Multiple render targets: 3 colour outputs [[color(0..2)]]. Isolates the
// render-target index in the colour-store epilog (needs a 3-attachment pipeline).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct FOut {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
    float4 c2 [[color(2)]];
};
fragment FOut f_main() {
    FOut o;
    o.c0 = float4(0.10, 0.11, 0.12, 1.0);
    o.c1 = float4(0.20, 0.21, 0.22, 1.0);
    o.c2 = float4(0.30, 0.31, 0.32, 1.0);
    return o;
}
