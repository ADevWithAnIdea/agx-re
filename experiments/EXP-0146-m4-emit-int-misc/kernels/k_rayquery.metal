#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;
// EXP-0146 P4 carrier search: intersection_query getters were reported (EXP-M4-13) as the
// only own-MSL producer of sr_read_wide (byte+1 0xa1/0x81 property reads).
kernel void k(device float *out [[buffer(0)]],
              instance_acceleration_structure accel [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    ray r;
    r.origin = float3(0.0f, 0.0f, 0.0f);
    r.direction = float3(0.0f, 0.0f, 1.0f);
    r.min_distance = 0.0f;
    r.max_distance = 100.0f;
    intersection_query<instancing> q;
    q.reset(r, accel);
    float acc = 0.0f;
    while (q.next()) {
        acc += float(q.get_candidate_primitive_id());
        acc += float(q.get_candidate_geometry_id());
        acc += q.get_candidate_triangle_distance();
    }
    q.commit_triangle_intersection();
    acc += float(q.get_committed_primitive_id());
    acc += float(q.get_committed_geometry_id());
    acc += float(q.get_committed_instance_id());
    acc += q.get_committed_distance();
    out[gid] = acc;
}
