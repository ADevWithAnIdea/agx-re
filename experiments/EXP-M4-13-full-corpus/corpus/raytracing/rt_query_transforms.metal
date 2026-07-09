#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Query world-space ray + candidate/committed transform getters (instancing).
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(1,0,0), float3(0,0,1));
    intersection_query<triangle_data, instancing> q;
    q.reset(r, accel);
    float acc = 0.0f;
    while (q.next()) {
        float4x3 c2w = q.get_candidate_object_to_world_transform();
        float4x3 w2c = q.get_candidate_world_to_object_transform();
        acc += c2w[3].x + w2c[3].x;
        q.commit_triangle_intersection();
    }
    acc += q.get_world_space_ray_origin().x + q.get_world_space_ray_direction().x;
    float4x3 m = q.get_committed_object_to_world_transform();
    float4x3 n = q.get_committed_world_to_object_transform();
    o[i] = acc + m[0].x + n[0].x;
}
