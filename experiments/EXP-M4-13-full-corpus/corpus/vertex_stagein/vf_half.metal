// stage_in fetch, HALF dest: unpack/convert directly into 16-bit registers.
#include <metal_stdlib>
using namespace metal;
struct VIn  { half4 a0 [[attribute(0)]]; };
struct VOut { float4 pos [[position]]; half4 v; };
vertex VOut vMain(VIn in [[stage_in]]) { VOut o; o.pos = float4(in.a0); o.v = in.a0; return o; }
fragment half4 fMain(VOut in [[stage_in]]) { return in.v; }
