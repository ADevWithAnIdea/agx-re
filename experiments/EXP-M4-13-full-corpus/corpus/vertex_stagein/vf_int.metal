// stage_in fetch, SIGNED-INT dest: sign-extend/widen prologue for char/short/int.
#include <metal_stdlib>
using namespace metal;
struct VIn  { int4 a0 [[attribute(0)]]; };
struct VOut { float4 pos [[position]]; int4 v [[flat]]; };
vertex VOut vMain(VIn in [[stage_in]]) { VOut o; o.pos = float4(in.a0); o.v = in.a0; return o; }
fragment int4 fMain(VOut in [[stage_in]]) { return in.v; }
