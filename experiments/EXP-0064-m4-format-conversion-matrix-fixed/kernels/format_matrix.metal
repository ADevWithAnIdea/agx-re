// EXP-0064 complete authored MSL: public typed render-store/read behavior only.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
  float2 p = vid == 0u ? float2(-1,-1) : vid == 1u ? float2(3,-1) : float2(-1,3);
  return {float4(p,0,1)};
}
fragment float4 f_rgba8unorm_edges(VOut x [[stage_in]]) { return float4(-.25,.5,1.25,128.0/255.0); }
fragment float4 f_bgra8unorm_edges(VOut x [[stage_in]]) { return float4(-.25,.5,1.25,128.0/255.0); }
fragment float4 f_rgba8srgb_threshold(VOut x [[stage_in]]) { return float4(.0031308,.0031309,.5,.5); }
fragment float4 f_r16unorm_midpoint(VOut x [[stage_in]]) { return float4(.5,0,0,1); }
fragment float4 f_rgba16float_edges(VOut x [[stage_in]]) { return float4(-0.0,1.0,65504.0,.333251953125); }
fragment uint f_r32uint_exact(VOut x [[stage_in]]) { return 0xdeadbeefu; }
kernel void k_read_float(texture2d<float, access::read> t [[texture(0)]], device uint4 *o [[buffer(0)]]) { o[0]=as_type<uint4>(t.read(uint2(0))); }
kernel void k_read_uint(texture2d<uint, access::read> t [[texture(0)]], device uint4 *o [[buffer(0)]]) { o[0]=t.read(uint2(0)); }
