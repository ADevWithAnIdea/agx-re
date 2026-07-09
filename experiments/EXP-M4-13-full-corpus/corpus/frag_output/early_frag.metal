#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// [[early_fragment_tests]] with a device side-effect store (UAV-style)
[[early_fragment_tests]]
fragment float4 fMain(VOut in [[stage_in]], device atomic_uint* ctr [[buffer(0)]]) {
    atomic_fetch_add_explicit(ctr, 1u, memory_order_relaxed);
    return in.col;
}
