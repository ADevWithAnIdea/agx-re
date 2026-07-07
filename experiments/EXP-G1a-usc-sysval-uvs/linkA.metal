#include <metal_stdlib>
using namespace metal;
struct VO { float4 pos [[position]]; float4 v0; float4 v1; float4 v2; };
vertex VO v_main(uint vid [[vertex_id]]) {
  float2 q = float2((vid==2)?3.0:-1.0, (vid==1)?3.0:-1.0);
  VO o; o.pos=float4(q,0,1);
  o.v0=float4(0,0,0.1,1);   // A
  o.v1=float4(0,0,0.2,1);   // B
  o.v2=float4(0,0,0.3,1);   // C
  return o;
}
fragment float4 f_main(VO in [[stage_in]]){ return in.v1; }   // read MIDDLE slot
