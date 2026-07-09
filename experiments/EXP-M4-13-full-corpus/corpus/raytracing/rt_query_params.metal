#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// intersection_params (force_opacity + accept_any) passed into reset().
kernel void kmain(device float* o [[buffer(0)]],
                  primitive_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersection_params p;
    p.accept_any_intersection(true);
    p.force_opacity(forced_opacity::non_opaque);
    p.assume_geometry_type(geometry_type::triangle);
    intersection_query<triangle_data> q;
    q.reset(r, accel, p);
    while (q.next())
        if (q.get_candidate_intersection_type() == intersection_type::triangle)
            q.commit_triangle_intersection();
    o[i] = q.get_committed_distance();
}
