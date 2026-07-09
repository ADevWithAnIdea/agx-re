// stage_in fetch, UNSIGNED-INT dest: zero-extend/widen prologue for uchar/ushort/uint.
#include <metal_stdlib>
using namespace metal;
struct VIn  { uint4 a0 [[attribute(0)]]; };
struct VOut { float4 pos [[position]]; uint4 v [[flat]]; };
vertex VOut vMain(VIn in [[stage_in]]) { VOut o; o.pos = float4(in.a0); o.v = in.a0; return o; }
fragment uint4 fMain(VOut in [[stage_in]]) { return in.v; }
