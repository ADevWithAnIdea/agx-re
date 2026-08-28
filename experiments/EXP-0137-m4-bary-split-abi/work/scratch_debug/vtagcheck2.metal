#include <metal_stdlib>
using namespace metal;
struct VOutExtra { float4 position [[position]]; float4 vtag [[user(locn0)]]; };
vertex VOutExtra v_bary_extra(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-0.6,-0.6), float2(0.6,-0.6), float2(0.0,0.6) };
    float  w[3] = { 1.0, 2.0, 4.0 };
    float4 vtag[3] = { float4(1,2,3,4), float4(11,12,13,14), float4(21,22,23,24) };
    uint i = vid % 3;
    VOutExtra o;
    o.position = float4(p[i] * w[i], 0.0, w[i]);
    o.vtag = vtag[i];
    return o;
}
struct FSIn { float4 vtag [[user(locn0)]]; };
fragment float4 f_vtag_only(FSIn in [[stage_in]]) {
    return in.vtag;
}
