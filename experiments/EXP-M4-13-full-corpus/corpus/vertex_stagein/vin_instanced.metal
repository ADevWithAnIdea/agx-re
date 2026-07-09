// stage_in with a PER-INSTANCE stepped attribute (--attrs float4 --iattrs float4):
// prologue must address attr1 by instance rather than vertex.
#include <metal_stdlib>
using namespace metal;
struct VIn  { float4 pos [[attribute(0)]]; float4 inst [[attribute(1)]]; };
struct VOut { float4 pos [[position]]; float4 v; };
vertex VOut vMain(VIn in [[stage_in]], uint iid [[instance_id]]) {
    VOut o; o.pos = in.pos + in.inst; o.v = in.inst * float(iid); return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.v; }
