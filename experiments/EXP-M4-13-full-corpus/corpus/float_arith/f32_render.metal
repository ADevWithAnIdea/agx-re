#include <metal_stdlib>
using namespace metal;
// Render pipeline so the VERTEX and FRAGMENT stages' fp32 ALU forms are surfaced
// (the census notes vertex/fragment use ALU groups the compute stage does not:
// low-nibble-f ALU, varying interpolation). Both stages do a spread of fp32
// arithmetic: add/mul/fma/div, min/max/clamp/saturate, floor/fract, compare+select.
struct VOut {
    float4 pos [[position]];
    float3 v   [[user(loc0)]];
};
vertex VOut vMain(uint vid [[vertex_id]],
                  device const float4* inpos [[buffer(0)]],
                  device const float3* incol [[buffer(1)]]) {
    VOut o;
    float4 p = inpos[vid];
    float3 c = incol[vid];
    // fp32 arithmetic in the vertex stage
    p.xyz = fma(p.xyz, c, floor(p.xyz)) + clamp(c, 0.0f, 1.0f);
    p.w   = max(p.w, 1.0f) / (abs(c.x) + 1.0f);
    o.pos = p;
    o.v   = mix(c, p.xyz, fract(c));
    return o;
}
fragment float4 fMain(VOut in [[stage_in]],
                      device const float* k [[buffer(0)]]) {
    float3 c = in.v;
    float  s = k[0];
    // spread of fp32 ops in the fragment stage
    float3 r = saturate(fma(c, float3(s), -c));       // fma + saturate modifier
    r = clamp(r / (abs(c) + 1.0f), float3(0.0f), c);  // div + clamp
    float m = (r.x < r.y) ? fmin(r.x, r.z) : fmax(r.y, r.z);  // compare+select+min/max
    float f = fract(m) + trunc(s) - copysign(m, s);   // fract/trunc/copysign
    return float4(r, f);
}
