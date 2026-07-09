// Multi-attribute stage_in: interleaved unpack of 3 different formats in one
// prologue (--attrs float4,uchar4n,half2). Tests fetch scheduling/packing.
#include <metal_stdlib>
using namespace metal;
struct VIn  { float4 pos [[attribute(0)]]; float4 col [[attribute(1)]]; float2 uv [[attribute(2)]]; };
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(VIn in [[stage_in]]) { VOut o; o.pos=in.pos; o.col=in.col; o.uv=in.uv; return o; }
fragment float4 fMain(VOut in [[stage_in]]) { return in.col + float4(in.uv,0,0); }
