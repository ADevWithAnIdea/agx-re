#include <metal_stdlib>
using namespace metal;
struct VO {
  float4 pos [[position]];
  float4 va;   // varying 0
  float4 vb;   // varying 1
  float4 vc;   // varying 2
};
vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]) {
  float2 q = p[vid];
  VO o;
  o.pos = float4(q,0,1);
  o.va  = float4(q.x*1.0f, q.y*1.0f, 0.1f, 1.0f);
  o.vb  = float4(q.x*2.0f, q.y*2.0f, 0.2f, 1.0f);
  o.vc  = float4(q.x*3.0f, q.y*3.0f, 0.3f, 1.0f);
  return o;
}
fragment float4 f_main(VO in [[stage_in]]) {
  return in.va + in.vb + in.vc;   // all three live
}
