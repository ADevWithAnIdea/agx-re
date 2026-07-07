#include <metal_stdlib>
using namespace metal;
struct VO { float4 pos [[position]]; };
vertex VO v_main(uint vid [[vertex_id]]){ float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; VO o; o.pos=float4(p[vid],0,1); return o; }
fragment float4 f_helper(VO in [[stage_in]]){ return simd_is_helper_thread() ? float4(1,0,0,1) : float4(0,1,0,1); }
fragment float4 f_plain(VO in [[stage_in]]){ return float4(0,1,0,1); }
