#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Custom bounding-box primitive: commit_bounding_box_intersection(distance).
kernel void kmain(device float* o [[buffer(0)]],
                  primitive_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1), 0.0f, 1000.0f);
    intersection_query<> q;
    q.reset(r, accel);
    float best = 1e30f;
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::bounding_box) {
            float d = float(q.get_candidate_primitive_id()) * 0.5f + 1.0f;
            if (d < best) { best = d; q.commit_bounding_box_intersection(d); }
        }
    }
    o[i] = q.get_committed_distance();
}
