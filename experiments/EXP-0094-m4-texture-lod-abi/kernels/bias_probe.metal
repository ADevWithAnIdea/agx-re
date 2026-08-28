// EXP-0094 bias_probe.metal -- own MSL. Fragment shader isolating the shader
// `bias(b)` operand from implicit-LOD sampling. The vertex stage is a fixed
// "big triangle" (no interpolated varyings); the fragment stage derives uv
// directly from window-space [[position]], so d(uv)/d(pixel) = params[0..1]
// EXACTLY (no interpolation rounding) -- see harness/texrender.m header.
//
// params[0] = uvScale.x   (=> dudx exactly; dvdx=0)
// params[1] = uvScale.y   (=> dvdy exactly; dudy=0)
// params[2] = bias operand passed to bias()
#include <metal_stdlib>
using namespace metal;

struct VOut { float4 position [[position]]; };

vertex VOut vmain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.position = float4(p[vid], 0, 1);
    return o;
}

fragment float4 fmain(float4 position [[position]],
                       texture2d<float> tex [[texture(0)]],
                       sampler s [[sampler(0)]],
                       constant float *params [[buffer(0)]]) {
    float2 uv = position.xy * float2(params[0], params[1]);
    float v = tex.sample(s, uv, bias(params[2])).r;
    return float4(v, 0, 0, 1);
}
