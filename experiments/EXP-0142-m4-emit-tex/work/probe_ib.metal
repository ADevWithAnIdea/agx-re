#include <metal_stdlib>
using namespace metal;
struct VO { float4 pos [[position]]; float2 uv [[user(locn0)]]; };
vertex VO v_main(uint vid [[vertex_id]], device const float *in [[buffer(0)]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VO o; o.pos = float4(p[vid], 0, 1);
    o.uv = (p[vid]*0.5f+0.5f) * 4.0f * in[0];
    return o;
}
struct GB { float4 a [[color(0)]]; };
fragment void f_main(imageblock<GB, imageblock_layout_explicit> img,
                     float4 pos [[position]],
                     float2 uv [[user(locn0)]],
                     device const float *in [[buffer(0)]])
{
    GB v = img.read();
    v.a = float4(v.a.x + in[0], uv.x, in[2], in[3]);
    img.write(v);
}
