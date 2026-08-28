#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float clip_dist [[clip_distance]] [10];
};
struct FIn {
    float4 position [[position]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    o.clip_dist[0] = 1.0;
    o.clip_dist[1] = 1.0;
    o.clip_dist[2] = 1.0;
    o.clip_dist[3] = 1.0;
    o.clip_dist[4] = 1.0;
    o.clip_dist[5] = 1.0;
    o.clip_dist[6] = 1.0;
    o.clip_dist[7] = 1.0;
    o.clip_dist[8] = 1.0;
    o.clip_dist[9] = 1.0;
    return o;
}
fragment float4 f_main(FIn in [[stage_in]]) {
    return float4(1,1,1,1);
}
