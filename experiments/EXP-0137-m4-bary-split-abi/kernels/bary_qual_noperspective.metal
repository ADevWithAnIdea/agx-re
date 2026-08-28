// bary_qual_noperspective.metal -- EXP-0129 H1 grammar probe (OWN-SHADER,
// compile-only), the no-perspective counterpart to bary_qual_persp.metal.
// Isolated in its own file so a parse rejection cannot block other kernels.
#include <metal_stdlib>
using namespace metal;
struct VOutQ2 { float4 position [[position]]; };
vertex VOutQ2 v_bary_q2(uint vid [[vertex_id]]) {
    VOutQ2 o;
    float2 p[3] = { float2(-0.6,-0.6), float2(0.6,-0.6), float2(0.0,0.6) };
    float  w[3] = { 1.0, 2.0, 4.0 };
    uint i = vid % 3;
    o.position = float4(p[i] * w[i], 0.0, w[i]);
    return o;
}
fragment float4 f_bary_qnopersp(float3 b [[barycentric_coord, center_no_perspective]]) {
    return float4(b, 1.0);
}
