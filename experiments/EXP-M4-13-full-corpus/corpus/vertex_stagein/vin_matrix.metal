// stage_in float4 position transformed by a constant float4x4 MVP: surfaces the
// column-times-vector fma chain in vertex context + constant-buffer load.
#include <metal_stdlib>
using namespace metal;
struct VIn  { float4 pos [[attribute(0)]]; float4 col [[attribute(1)]]; };
struct VOut { float4 pos [[position]]; float4 col; };
vertex VOut vMain(VIn in [[stage_in]], constant float4x4& mvp [[buffer(8)]]) {
    VOut o; o.pos = mvp * in.pos; o.col = in.col; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.col; }
