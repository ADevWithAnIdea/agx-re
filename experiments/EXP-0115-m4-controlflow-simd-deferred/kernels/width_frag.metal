// width_frag.metal -- EXP-0115 item 6: fragment-stage SIMD width sweep
// (EXP-0104 covered compute only). Own-authored MSL, no Apple code read.
// One kernel; the render TARGET SIZE (a dispatch-time, not compile-time,
// parameter) is swept by the harness across sizes crossing the known fixed
// 32x32 AGX fragment tile boundary (docs/pipeline/README.md).
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
    return float4(float(lid) / 255.0, float(tw) / 255.0, 0.0, 1.0);
}
