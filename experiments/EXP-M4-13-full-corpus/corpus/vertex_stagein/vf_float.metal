// stage_in fetch, FLOAT dest: exercises format unpack/convert prologue for any
// float/normalized/packed vertex format (driven by --attrs).
#include <metal_stdlib>
using namespace metal;
struct VIn  { float4 a0 [[attribute(0)]]; };
struct VOut { float4 pos [[position]]; float4 v; };
vertex VOut vMain(VIn in [[stage_in]]) { VOut o; o.pos = in.a0; o.v = in.a0; return o; }
fragment float4 fMain(VOut in [[stage_in]]) { return in.v; }
