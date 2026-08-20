#include <metal_stdlib>
using namespace metal;
struct V { float4 p [[position]]; float4 f [[user(locn0)]]; float4 n [[user(locn1)]]; uint4 u [[user(locn2)]]; };
struct F { float4 p [[user(locn0), center_perspective]]; float4 n [[user(locn1), center_no_perspective]]; uint4 u [[user(locn2), flat]]; };
V make_v(float4 a,uint id){float2 q[3]={float2(-.9,-.8),float2(.9,-.7),float2(-.2,.9)};float w[3]={1.,2.,.5};V o;o.p=float4(q[id],0,w[id]);o.f=a;o.n=a;o.u=uint4(id,17,33,255);return o;}
vertex V v_float(float2 p [[attribute(0)]], float4 a [[attribute(1)]], uint id [[vertex_id]]) { return make_v(a,id); }
vertex V v_u8(uint4 a [[attribute(1)]], uint id [[vertex_id]]) { return make_v(float4(a),id); }
fragment float4 f_center_p(F x [[stage_in]]) { return x.p; }
fragment float4 f_center_n(F x [[stage_in]]) { return x.n; }
fragment uint4 f_flat(F x [[stage_in]]) { return x.u; }
fragment float4 f_constant(F) { return float4(.125,.25,.5,1); }
