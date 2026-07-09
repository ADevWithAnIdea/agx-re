// frag_varying: MANY varyings mixing every interpolation mode + widths in one FS.
// Stresses the full iterate-mode selection (flat/persp/nopersp x center/centroid/sample)
// and scalar/vec2/vec3/vec4 packing in a single fragment shader.
#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 pos [[position]];
    uint   flatu   [[flat]];
    float  p0;                                  // default center-perspective scalar
    float3 p1;                                  // center-perspective vec3
    float2 np      [[center_no_perspective]];
    float4 cen     [[centroid_perspective]];
    float  smp     [[sample_perspective]];
    half3  hp;                                  // half center-perspective
};
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o;
    o.pos   = vin[vid];
    o.flatu = vid;
    o.p0    = vin[vid].x;
    o.p1    = vin[vid].xyz;
    o.np    = vin[vid].xy;
    o.cen   = vin[vid];
    o.smp   = vin[vid].w;
    o.hp    = half3(vin[vid].xyz);
    return o;
}
fragment float4 fMain(VOut in [[stage_in]]) {
    float3 acc = in.p1 + float3(in.np, in.smp) + float3(in.hp);
    return in.cen + float4(acc, float(in.flatu)) + in.p0;
}
