#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Isolate the ray-query traversal predicate op: a candidate-loop that compares
// the intersection result and conditionally commits -> compiler emits the
// icmp_pred -> <n6 predicate op> -> if_push/branch sequence.
kernel void k(device float* o [[buffer(0)]],
              instance_acceleration_structure accel [[buffer(1)]],
              device const float3* org [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    ray r; r.origin = org[i]; r.direction = float3(0,0,1); r.min_distance=0; r.max_distance=1e9;
    intersector<instancing, triangle_data> is;
    intersection_query<instancing, triangle_data> q(r, accel, {});
    float acc = 0.0f;
    while (q.next()) {
        if (q.get_candidate_triangle_distance() < 5.0f) {
            q.commit_triangle_intersection();
            acc += 1.0f;
        }
    }
    o[i] = acc;
}
