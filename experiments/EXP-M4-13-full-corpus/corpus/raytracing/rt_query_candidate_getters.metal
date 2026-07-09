#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Exhaustive candidate-side getters (field extraction from query state).
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersection_query<triangle_data, instancing> q;
    q.reset(r, accel);
    float acc = 0.0f;
    while (q.next()) {
        acc += q.get_candidate_triangle_distance();
        acc += float(q.get_candidate_primitive_id());
        acc += float(q.get_candidate_geometry_id());
        acc += float(q.get_candidate_instance_id());
        acc += float(q.get_candidate_user_instance_id());
        acc += q.get_candidate_triangle_barycentric_coord().x;
        acc += q.is_candidate_non_opaque_bounding_box() ? 1.0f : 0.0f;
        q.commit_triangle_intersection();
    }
    o[i] = acc;
}
