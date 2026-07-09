#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos [[attribute(0)]]; float4 uvn [[attribute(1)]]; float4 tan [[attribute(2)]]; };
struct VOut { float4 position [[position]]; float2 uv; float3 nrm; float3 tang; float fog; };
[[patch(quad, 4)]]
vertex VOut vMain(patch_control_point<CP> cp [[stage_in]], float2 uv [[position_in_patch]]) {
    float4 pa = mix(cp[0].pos, cp[1].pos, uv.x), pb = mix(cp[2].pos, cp[3].pos, uv.x);
    float4 na = mix(cp[0].uvn, cp[1].uvn, uv.x), nb = mix(cp[2].uvn, cp[3].uvn, uv.x);
    float4 ta = mix(cp[0].tan, cp[1].tan, uv.x), tb = mix(cp[2].tan, cp[3].tan, uv.x);
    VOut o;
    o.position = mix(pa, pb, uv.y);
    float4 n = mix(na, nb, uv.y);
    o.uv = n.xy; o.nrm = normalize(n.xyz); o.tang = normalize(mix(ta,tb,uv.y).xyz);
    o.fog = clamp(o.position.z*0.5+0.5, 0.0, 1.0);
    return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return float4(i.nrm*i.fog + i.tang, i.uv.x); }
