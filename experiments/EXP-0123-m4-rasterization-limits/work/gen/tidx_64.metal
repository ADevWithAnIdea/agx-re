#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut vs_full(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) };
    VOut o; o.position = float4(pos[vid], 0.0, 1.0);
    return o;
}
fragment float4 fs_tbind(texture2d<float> tex [[texture(64)]]) {
    constexpr sampler s(coord::pixel, filter::nearest);
    return tex.sample(s, float2(0,0));
}
