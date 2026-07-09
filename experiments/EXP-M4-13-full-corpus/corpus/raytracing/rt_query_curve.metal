#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// intersection_query curve getters: get_candidate_curve_parameter().
kernel void kmain(device float* o [[buffer(0)]],
                  primitive_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersection_query<triangle_data, curve_data> q;
    q.reset(r, accel);
    float acc = 0.0f;
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::curve) {
            acc += q.get_candidate_curve_parameter();
            q.commit_triangle_intersection();
        }
    }
    acc += q.get_committed_curve_parameter();
    o[i] = acc;
}
