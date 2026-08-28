#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid], 0, 1); return o;
}
fragment float4 f_width_report(VOut in [[stage_in]],
                                uint lid [[thread_index_in_simdgroup]],
                                uint tw [[threads_per_simdgroup]]) {
    return float4(float(lid)/255.0, float(tw)/255.0, 0.0, 1.0);
}
