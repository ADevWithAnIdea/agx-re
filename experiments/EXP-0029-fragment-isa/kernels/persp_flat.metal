#include <metal_stdlib>
using namespace metal;
// Perspective-distorting geometry: a screen-covering triangle whose 3rd vertex
// has w=3 (the others w=1). With this w-variation, perspective-correct and linear
// interpolation of `u` give DIFFERENT pixel values -> lets a splice of the
// interpolation-mode field flip perspective<->linear observably. OUR OWN MSL.
struct VOut {
    float4 pos [[position]];
    float4 u   [[user(locn0)]] [[flat]];   // <-- MODE
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    // ndc corners of a full-screen triangle, with a per-vertex w.
    float2 ndc[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    float  w[3]   = { 1.0, 1.0, 3.0 };
    float  uval[3]= { 0.0, 0.0, 1.0 };
    VOut o;
    o.pos = float4(ndc[vid] * w[vid], 0.0, w[vid]);  // clip = ndc*w so ndc is preserved
    o.u   = float4(uval[vid], 0.25, 0.5, 1.0);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    return in.u;
}
