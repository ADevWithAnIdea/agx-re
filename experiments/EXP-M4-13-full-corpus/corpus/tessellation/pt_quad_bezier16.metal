#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos; };
struct VOut { float4 position [[position]]; };
static float4 bez(float4 a,float4 b,float4 c,float4 d,float t){
    float it=1.0-t; float b0=it*it*it, b1=3*it*it*t, b2=3*it*t*t, b3=t*t*t;
    return a*b0+b*b1+c*b2+d*b3;
}
[[patch(quad, 16)]]
vertex VOut vMain(const device CP* cp [[buffer(0)]], uint pid [[patch_id]],
                  float2 uv [[position_in_patch]]) {
    const device CP* p = cp + pid*16;
    float4 r0=bez(p[0].pos,p[1].pos,p[2].pos,p[3].pos,uv.x);
    float4 r1=bez(p[4].pos,p[5].pos,p[6].pos,p[7].pos,uv.x);
    float4 r2=bez(p[8].pos,p[9].pos,p[10].pos,p[11].pos,uv.x);
    float4 r3=bez(p[12].pos,p[13].pos,p[14].pos,p[15].pos,uv.x);
    VOut o; o.position = bez(r0,r1,r2,r3,uv.y); return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return i.position; }
