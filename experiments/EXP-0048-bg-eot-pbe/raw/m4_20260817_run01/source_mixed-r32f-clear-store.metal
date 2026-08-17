// VERTEX
#include <metal_stdlib>
using namespace metal;
struct VO { float4 pos [[position]]; };
vertex VO v_main(uint vid [[vertex_id]]) {
  float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};
  VO o; o.pos=float4(p[vid],0,1); return o;
}

// FRAGMENT
#include <metal_stdlib>
using namespace metal;
struct VO { float4 pos [[position]]; };
struct FO { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; };
fragment FO f_main(VO in [[stage_in]]) {
  (void)in;  FO o; o.c0=float4(0.25,0.5,0.75,0.5); o.c1=float4(0.625,0.0,0.0,1.0); return o;
}
