#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float flat_mode [[flat]]; float2 uv; };
vertex VOut vMain(uint vid[[vertex_id]]){
    VOut o; float2 p = float2((vid<<1)&2, vid&2);
    o.pos = float4(p*2.0-1.0, 0, 1); o.uv=p; o.flat_mode=float(vid&3); return o;
}
fragment float4 fMain(VOut in[[stage_in]]){
    int m = int(in.flat_mode);
    float4 c;
    switch(m){
        case 0: c=float4(in.uv,0,1); break;
        case 1: c=float4(1.0-in.uv,0,1); break;
        case 2: c=float4(in.uv.x, 0, in.uv.y, 1); break;
        default: c=float4(0.5); break;
    }
    return c;
}
