#include <metal_stdlib>
using namespace metal;
// Programmable blend, half4 tile read (typical G-buffer/tile format). Contrast
// against blend_read (float4) to see the tile-read data-width field.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct FIn {
    half4 dst [[color(0)]];
};
fragment half4 f_main(FIn in [[stage_in]]) {
    half4 src = half4(0.8h, 0.2h, 0.1h, 0.5h);
    return src * src.a + in.dst * (1.0h - src.a);
}
