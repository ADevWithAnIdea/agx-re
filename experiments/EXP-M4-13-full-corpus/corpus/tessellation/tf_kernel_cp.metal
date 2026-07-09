#include <metal_stdlib>
using namespace metal;
struct TriTessHalf { half edge[3]; half inside; };
struct CPin  { float4 pos; float4 nrm; };
struct CPout { packed_float4 pos; packed_float4 nrm; };
kernel void kMain(const device CPin* in [[buffer(0)]],
                  device CPout* outCP [[buffer(1)]],
                  device TriTessHalf* outTF [[buffer(2)]],
                  constant float4x4& mvp [[buffer(3)]],
                  constant float& tess [[buffer(4)]],
                  uint pid [[thread_position_in_grid]]) {
    // transform 3 control points of this patch
    float4 e = float4(0);
    for (uint i=0;i<3;i++) {
        CPin cp = in[pid*3+i];
        float4 p = mvp * cp.pos;
        outCP[pid*3+i].pos = packed_float4(p);
        outCP[pid*3+i].nrm = packed_float4(normalize(cp.nrm));
        e[i] = tess * (1.0 + 0.25*float(i));
    }
    TriTessHalf t;
    t.edge[0]=half(e.x); t.edge[1]=half(e.y); t.edge[2]=half(e.z);
    t.inside=half((e.x+e.y+e.z)/3.0);
    outTF[pid]=t;
}
