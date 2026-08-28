#include <metal_stdlib>
using namespace metal;
vertex float4 v_plain(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-1.0,-1.0), float2(3.0,-1.0), float2(-1.0,3.0) };
    return float4(pos[vid], 0.0, 1.0);
}
struct VO { float4 pos [[position]]; float4 col; };
vertex VO v_col(uint vid [[vertex_id]], constant float4 *tab [[buffer(0)]]) {
    VO o; o.pos = tab[vid]; o.col = tab[vid+3]; return o;
}
fragment float4 f_c(float4 dst [[color(0)]], constant float4 &src [[buffer(0)]]) { return dst*2.0+src; }
fragment float4 f_v(VO in [[stage_in]]) { return in.col; }
