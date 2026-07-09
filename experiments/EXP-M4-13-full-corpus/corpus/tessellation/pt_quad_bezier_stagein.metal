#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos [[attribute(0)]]; };
struct VOut { float4 position [[position]]; };
static float4 bez(float4 a,float4 b,float4 c,float4 d,float t){
    float it=1.0-t; return a*(it*it*it)+b*(3*it*it*t)+c*(3*it*t*t)+d*(t*t*t);
}
[[patch(quad, 16)]]
vertex VOut vMain(patch_control_point<CP> cp [[stage_in]], float2 uv [[position_in_patch]]) {
    float4 r0=bez(cp[0].pos,cp[1].pos,cp[2].pos,cp[3].pos,uv.x);
    float4 r1=bez(cp[4].pos,cp[5].pos,cp[6].pos,cp[7].pos,uv.x);
    float4 r2=bez(cp[8].pos,cp[9].pos,cp[10].pos,cp[11].pos,uv.x);
    float4 r3=bez(cp[12].pos,cp[13].pos,cp[14].pos,cp[15].pos,uv.x);
    VOut o; o.position = bez(r0,r1,r2,r3,uv.y); return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return i.position; }
