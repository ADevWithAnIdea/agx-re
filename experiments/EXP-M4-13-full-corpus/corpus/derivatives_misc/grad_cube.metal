#include <metal_stdlib>
using namespace metal;
// Cube-map explicit-gradient sample: gradientcube(dPdx,dPdy) with 3-vector
// derivatives. Different operand count/layout from the 2D gradient form.
struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 fMain(VOut in [[stage_in]],
                      texturecube<float> tex [[texture(0)]],
                      sampler s [[sampler(0)]]) {
    float3 dir = normalize(float3(in.uv * 2.0 - 1.0, 1.0));
    float3 dx  = dfdx(dir);
    float3 dy  = dfdy(dir);
    return tex.sample(s, dir, gradientcube(dx, dy));
}
