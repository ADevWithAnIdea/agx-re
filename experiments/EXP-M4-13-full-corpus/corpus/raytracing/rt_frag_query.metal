#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Ray query executed in a FRAGMENT shader (RT ops in fragment stage).
struct VOut { float4 pos [[position]]; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    VOut o;
    float2 p = float2((vid==2)?3.0:-1.0, (vid==1)?3.0:-1.0);
    o.pos = float4(p, 0.0, 1.0);
    return o;
}
fragment float4 fMain(VOut in [[stage_in]],
                      primitive_acceleration_structure accel [[buffer(0)]]) {
    ray r(float3(0,0,0), float3(0,0,1), 0.0f, 1000.0f);
    intersection_query<triangle_data> q;
    q.reset(r, accel);
    while (q.next())
        if (q.get_candidate_intersection_type() == intersection_type::triangle)
            q.commit_triangle_intersection();
    return float4(q.get_committed_distance());
}
