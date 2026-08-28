// EXP-0142 carrier C -- fragment derivative carrier for tex_deriv (byte0 0x37).
//
// A full-screen triangle carries a varying that is EXACTLY the pixel
// coordinate scaled by in[0], so dfdx(uv.x) == in[0] and dfdy(uv.y) == in[0]
// are host-computable constants, and the two cross terms are exactly 0.
//
// LIVENESS (the EXP-0129 trap): each of the four derivative results is routed
// to its own channel of an RGBA32Float render target that is read back
// per-pixel. Component r carries dfdx(uv.x), g carries dfdy(uv.y), b carries
// dfdx(uv.y), a carries dfdy(uv.x) + the integrity sentinel offset in[5], so a
// derivative that fails to reach the rasterised pixel changes a specific,
// named float. The pre-registered positive control forces the axis byte and
// must swap r and g; if it does not, the arm is reported dead exactly as
// EXP-0129 did rather than assumed live.
//
// Clean-room: our own MSL.
#include <metal_stdlib>
using namespace metal;

struct VO { float4 pos [[position]]; float2 uv; };

vertex VO v_main(uint vid [[vertex_id]], device const float *in [[buffer(0)]]) {
    float2 p[3] = { float2(-1.0f,-1.0f), float2(3.0f,-1.0f), float2(-1.0f,3.0f) };
    VO o;
    o.pos = float4(p[vid], 0.0f, 1.0f);
    o.uv  = (p[vid] * 0.5f + 0.5f) * 4.0f * in[0];
    return o;
}

fragment float4 f_main(VO i, device const float *in [[buffer(0)]]) {
    float a = dfdx(i.uv.x);
    float b = dfdy(i.uv.y);
    float c = dfdx(i.uv.y);
    float d = dfdy(i.uv.x);
    return float4(a, b, c, d + in[5]);   // in[5] = 0 -> sentinel-checked channel
}
