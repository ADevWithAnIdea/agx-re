#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// intersection_query with motion (time argument in reset).
kernel void kmain(device float* o [[buffer(0)]],
                  primitive_acceleration_structure accel [[buffer(1)]],
                  device const float* t [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersection_query<triangle_data, primitive_motion> q;
    q.reset(r, accel, t[i]);
    while (q.next())
        if (q.get_candidate_intersection_type() == intersection_type::triangle)
            q.commit_triangle_intersection();
    o[i] = q.get_committed_distance();
}
