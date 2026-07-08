#include <metal_stdlib>
using namespace metal;
struct VO { float4 pos [[position]]; };
vertex VO v_main(uint vid [[vertex_id]]) { VO o; o.pos=float4(0,0,0,1); return o; }
fragment float4 f_main(VO in [[stage_in]]) {
    bool h = simd_is_helper_thread();
    return float4(h ? 1.0 : 0.0, 0, 0, 1);
}
