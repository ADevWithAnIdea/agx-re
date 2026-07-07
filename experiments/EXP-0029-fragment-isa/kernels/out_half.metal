#include <metal_stdlib>
using namespace metal;
// half4 colour output -> contrast the color-store data width vs out_const's float4.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment half4 f_main() {
    return half4(0.75h, 0.5h, 0.25h, 1.0h);
}
