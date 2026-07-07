#include <metal_stdlib>
using namespace metal;
// Programmable blending: read the CURRENT colour-attachment value as a fragment
// input ([[color(0)]] input) and blend in-shader. On Apple TBDR this reads the
// tilebuffer -- the ld_tile analogue. Clean-room: OUR OWN MSL.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct FIn {
    float4 dst [[color(0)]];   // <-- reads existing framebuffer/tile value
};
fragment float4 f_main(FIn in [[stage_in]]) {
    float4 src = float4(0.8, 0.2, 0.1, 0.5);
    return src * src.a + in.dst * (1.0 - src.a);   // custom over-blend
}
