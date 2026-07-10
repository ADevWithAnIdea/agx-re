#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

kernel void rq_committed(device float* out, instance_acceleration_structure accel [[buffer(0)]],
                         device const float* rays [[buffer(1)]], uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin = float3(rays[0], rays[1], rays[2]);
    r.direction = float3(rays[3], rays[4], rays[5]);
    r.min_distance = 0.0f; r.max_distance = 100.0f;
    intersection_query<instancing> q;
    q.reset(r, accel);
    while (q.next()) {}
    float acc = 0;
    acc += q.get_committed_distance();
    acc += float(q.get_committed_primitive_id());
    acc += float(q.get_committed_geometry_id());
    acc += float(q.get_committed_instance_id());
    out[i] = acc;
}

kernel void rq_dist(device float* out, instance_acceleration_structure accel [[buffer(0)]],
                    device const float* rays [[buffer(1)]], uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin = float3(rays[0], rays[1], rays[2]);
    r.direction = float3(rays[3], rays[4], rays[5]);
    r.min_distance = 0.0f; r.max_distance = 100.0f;
    intersection_query<instancing> q;
    q.reset(r, accel);
    while (q.next()) {}
    out[i] = q.get_committed_distance();
}

kernel void rq_candidate(device float* out, instance_acceleration_structure accel [[buffer(0)]],
                         device const float* rays [[buffer(1)]], uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin = float3(rays[0], rays[1], rays[2]);
    r.direction = float3(rays[3], rays[4], rays[5]);
    r.min_distance = 0.0f; r.max_distance = 100.0f;
    intersection_query<instancing> q;
    q.reset(r, accel);
    float acc = 0;
    while (q.next()) {
        acc += float(q.get_candidate_primitive_id());
        acc += float(q.get_candidate_geometry_id());
        acc += q.get_candidate_triangle_distance();
    }
    out[i] = acc;
}
