#include <metal_stdlib>
using namespace metal;
struct BlendParams { float4 srcFactor; float4 dstFactor; uint mode; };
static float4 __attribute__((noinline)) do_blend_epilog2(float4 src, float4 dst, constant BlendParams &p) {
    float4 s = src * p.srcFactor;
    float4 d = dst * p.dstFactor;
    if (p.mode == 0u) { return s + d; } else { return s * d; }
}
struct VOutC2 { float4 position [[position]]; };
vertex VOutC2 v_split_common2(uint vid [[vertex_id]]) {
    float2 p3[3] = { float2(-1.0,-1.0), float2(3.0,-1.0), float2(-1.0,3.0) };
    VOutC2 o; o.position = float4(p3[vid % 3], 0.0, 1.0); return o;
}
fragment float4 f_split_epilog2(float4 dst [[color(0)]], constant float4 &srcColor [[buffer(0)]], constant BlendParams &bp [[buffer(1)]]) {
    return do_blend_epilog2(srcColor, dst, bp);
}
