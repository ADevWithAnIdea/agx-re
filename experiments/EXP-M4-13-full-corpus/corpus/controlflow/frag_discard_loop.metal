#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut vMain(uint vid[[vertex_id]]){
    VOut o; float2 p = float2((vid<<1)&2, vid&2);
    o.pos = float4(p*2.0-1.0, 0, 1); o.uv=p; return o;
}
fragment float4 fMain(VOut in[[stage_in]]){
    float2 uv=in.uv; float acc=0.0;
    for(int j=0;j<8;j++){
        float d = length(uv - float2(float(j)*0.1));
        if(d<0.05) discard_fragment();
        acc += (d>0.5) ? 1.0 : d;
    }
    if(acc<0.01) discard_fragment();
    return float4(acc, uv, 1.0);
}
