#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;

// Minimal single-getter: committed distance only.
kernel void k_dist(acceleration_structure<> accel [[buffer(0)]],
                   device const float *rin [[buffer(1)]],
                   device float *out [[buffer(2)]],
                   uint tid [[thread_position_in_grid]]) {
    ray r;
    r.origin    = float3(rin[0], rin[1], rin[2]);
    r.direction = float3(rin[3], rin[4], rin[5]);
    r.min_distance = rin[6];
    r.max_distance = rin[7];
    intersection_query<> q;
    q.reset(r, accel);
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::triangle)
            q.commit_triangle_intersection();
    }
    out[tid] = q.get_committed_distance();
}

// Single getter: committed primitive id.
kernel void k_prim(acceleration_structure<> accel [[buffer(0)]],
                   device const float *rin [[buffer(1)]],
                   device float *out [[buffer(2)]],
                   uint tid [[thread_position_in_grid]]) {
    ray r;
    r.origin    = float3(rin[0], rin[1], rin[2]);
    r.direction = float3(rin[3], rin[4], rin[5]);
    r.min_distance = rin[6];
    r.max_distance = rin[7];
    intersection_query<> q;
    q.reset(r, accel);
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::triangle)
            q.commit_triangle_intersection();
    }
    out[tid] = float(q.get_committed_primitive_id());
}

// Candidate-distance getter feeding output (before commit).
kernel void k_cand(acceleration_structure<> accel [[buffer(0)]],
                   device const float *rin [[buffer(1)]],
                   device float *out [[buffer(2)]],
                   uint tid [[thread_position_in_grid]]) {
    ray r;
    r.origin    = float3(rin[0], rin[1], rin[2]);
    r.direction = float3(rin[3], rin[4], rin[5]);
    r.min_distance = rin[6];
    r.max_distance = rin[7];
    intersection_query<> q;
    q.reset(r, accel);
    float acc = -1.0f;
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::triangle) {
            acc = q.get_candidate_triangle_distance();
            q.commit_triangle_intersection();
        }
    }
    out[tid] = acc;
}

// Committed barycentric coord u (2D result getter).
kernel void k_bary(acceleration_structure<> accel [[buffer(0)]],
                   device const float *rin [[buffer(1)]],
                   device float *out [[buffer(2)]],
                   uint tid [[thread_position_in_grid]]) {
    ray r;
    r.origin    = float3(rin[0], rin[1], rin[2]);
    r.direction = float3(rin[3], rin[4], rin[5]);
    r.min_distance = rin[6];
    r.max_distance = rin[7];
    intersection_query<> q;
    q.reset(r, accel);
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::triangle)
            q.commit_triangle_intersection();
    }
    out[tid] = float(q.get_committed_geometry_id());
}
