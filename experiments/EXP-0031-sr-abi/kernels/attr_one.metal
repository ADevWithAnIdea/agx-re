#include <metal_stdlib>
using namespace metal;
struct VIn { float4 pos [[attribute(0)]]; };
vertex float4 v_main(VIn in [[stage_in]]) { return in.pos; }
fragment float4 f_main() { return float4(1,0,0,1); }
