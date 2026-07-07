#include <metal_stdlib>
using namespace metal;
// Explicit imageblock G-buffer write (fragment). Provokes the imageblock/tile
// slice store path and the [[color(n)]] slot layout. OUR OWN MSL.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct GBuffer {
    half4  albedo [[color(0)]];
    half4  normal [[color(1)]];
    float  depthv [[color(2)]];
};
fragment GBuffer f_main(float4 pos [[position]]) {
    GBuffer g;
    g.albedo = half4(0.5h, 0.25h, 0.125h, 1.0h);
    g.normal = half4(0.0h, 0.0h, 1.0h, 0.0h);
    g.depthv = 0.9;
    return g;
}
