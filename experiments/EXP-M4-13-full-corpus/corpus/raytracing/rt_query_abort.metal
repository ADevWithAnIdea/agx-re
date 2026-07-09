#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// abort() early termination of traversal.
kernel void kmain(device float* o [[buffer(0)]],
                  primitive_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersection_query<triangle_data> q;
    q.reset(r, accel);
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::triangle) {
            q.commit_triangle_intersection();
            q.abort();
        }
    }
    o[i] = q.get_committed_distance();
}
