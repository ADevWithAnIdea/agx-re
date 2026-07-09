#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Ray query executed in a VERTEX shader (RT ops in vertex stage).
struct VOut { float4 pos [[position]]; float d; };
vertex VOut vMain(uint vid [[vertex_id]],
                  primitive_acceleration_structure accel [[buffer(0)]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersection_query<triangle_data> q;
    q.reset(r, accel);
    while (q.next())
        if (q.get_candidate_intersection_type() == intersection_type::triangle)
            q.commit_triangle_intersection();
    VOut o;
    o.pos = float4(0,0,0,1);
    o.d = q.get_committed_distance();
    return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return float4(in.d); }
