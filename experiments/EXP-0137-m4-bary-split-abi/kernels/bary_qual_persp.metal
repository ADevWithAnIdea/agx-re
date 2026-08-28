// bary_qual_persp.metal -- EXP-0129 H1 grammar probe (OWN-SHADER, compile-only).
// Does MSL accept an explicit interpolation qualifier on [[barycentric_coord]],
// the same way it does on an ordinary [[user(n)]] varying (e.g.
// [[user(locn0), center_no_perspective]])? Isolated in its own file so a
// parse rejection here cannot block any other kernel's compile.
#include <metal_stdlib>
using namespace metal;
struct VOutQ { float4 position [[position]]; };
vertex VOutQ v_bary_q(uint vid [[vertex_id]]) {
    VOutQ o;
    float2 p[3] = { float2(-0.6,-0.6), float2(0.6,-0.6), float2(0.0,0.6) };
    float  w[3] = { 1.0, 2.0, 4.0 };
    uint i = vid % 3;
    o.position = float4(p[i] * w[i], 0.0, w[i]);
    return o;
}
fragment float4 f_bary_qpersp(float3 b [[barycentric_coord, center_perspective]]) {
    return float4(b, 1.0);
}
