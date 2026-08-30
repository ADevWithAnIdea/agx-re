#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;
// EXP-0157 (OWN-SHADER). Differential-compilation family: nine kernels that
// are BYTE-FOR-BYTE the same program except for the single intersection_query
// getter each one reads. Diffing any two compiled `_agc.main` regions
// therefore isolates the encoding of the getter itself -- which is how this
// experiment LOCATES `sr_read_wide` in a 25 kB ray-query program that does not
// tokenize end-to-end, without ever trusting a resync-walk offset.
//
// Each kernel writes ONE host-predictable scalar to out[0] and nothing else,
// so the swept field is live on the observed output path
// (FIELD-SWEEP-PROTOCOL section 3.2) -- the exact property EXP-0146's
// accumulate-everything carrier lacked.
//
// Geometry (authored by us, built by harness/agxrun_persist_as.m): three
// NON-OPAQUE triangles in the z = 1, 2, 3 planes, all straddling the +z axis.
// Ray: origin (0,0,0), direction (0,0,1), t in [0,100].
// Candidate sums are order-independent, so no oracle depends on BVH traversal
// order.
#define RQ_PROLOGUE                       \
    ray r;                                \
    r.origin       = float3(0.0f, 0.0f, 0.0f); \
    r.direction    = float3(0.0f, 0.0f, 1.0f); \
    r.min_distance = 0.0f;                \
    r.max_distance = 100.0f;              \
    intersection_query<> q;               \
    q.reset(r, accel);                    \
    float v = 0.0f;

// `triangle_data` is required for the barycentric / front-facing getters; it
// is a DIFFERENT query type, so those three kernels are diffed against each
// other, never against the plain-query kernels above.
#define RQ_PROLOGUE_TD                    \
    ray r;                                \
    r.origin       = float3(0.0f, 0.0f, 0.0f); \
    r.direction    = float3(0.0f, 0.0f, 1.0f); \
    r.min_distance = 0.0f;                \
    r.max_distance = 100.0f;              \
    intersection_query<triangle_data> q;  \
    q.reset(r, accel);                    \
    float v = 0.0f;

// ---- candidate-property getters: summed over all three candidates --------
kernel void k_cand_prim(device float *out [[buffer(0)]],
                        primitive_acceleration_structure accel [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { v += float(q.get_candidate_primitive_id()); }   // = 0+1+2 = 3
    if (gid == 0) out[0] = v;
}
kernel void k_cand_geom(device float *out [[buffer(0)]],
                        primitive_acceleration_structure accel [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { v += float(q.get_candidate_geometry_id()); }    // = 0
    if (gid == 0) out[0] = v;
}
kernel void k_cand_dist(device float *out [[buffer(0)]],
                        primitive_acceleration_structure accel [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { v += q.get_candidate_triangle_distance(); }     // = 1+2+3 = 6
    if (gid == 0) out[0] = v;
}
kernel void k_cand_baryx(device float *out [[buffer(0)]],
                         primitive_acceleration_structure accel [[buffer(1)]],
                         uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE_TD
    while (q.next()) { v += q.get_candidate_triangle_barycentric_coord().x; }
    if (gid == 0) out[0] = v;
}
kernel void k_cand_baryy(device float *out [[buffer(0)]],
                         primitive_acceleration_structure accel [[buffer(1)]],
                         uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE_TD
    while (q.next()) { v += q.get_candidate_triangle_barycentric_coord().y; }
    if (gid == 0) out[0] = v;
}
kernel void k_cand_front(device float *out [[buffer(0)]],
                         primitive_acceleration_structure accel [[buffer(1)]],
                         uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE_TD
    while (q.next()) { v += (q.is_candidate_triangle_front_facing() ? 1.0f : 0.0f); }
    if (gid == 0) out[0] = v;
}
kernel void k_cand_count(device float *out [[buffer(0)]],
                         primitive_acceleration_structure accel [[buffer(1)]],
                         uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { v += 1.0f; }                                    // = 3
    if (gid == 0) out[0] = v;
}
kernel void k_cand_td_dist(device float *out [[buffer(0)]],
                           primitive_acceleration_structure accel [[buffer(1)]],
                           uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE_TD
    while (q.next()) { v += q.get_candidate_triangle_distance(); }      // = 6
    if (gid == 0) out[0] = v;
}
// ---- committed-property getters: closest hit after committing everything --
kernel void k_comm_prim(device float *out [[buffer(0)]],
                        primitive_acceleration_structure accel [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { q.commit_triangle_intersection(); }
    v = float(q.get_committed_primitive_id());                          // = 0
    if (gid == 0) out[0] = v;
}
kernel void k_comm_geom(device float *out [[buffer(0)]],
                        primitive_acceleration_structure accel [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { q.commit_triangle_intersection(); }
    v = float(q.get_committed_geometry_id());                           // = 0
    if (gid == 0) out[0] = v;
}
kernel void k_comm_dist(device float *out [[buffer(0)]],
                        primitive_acceleration_structure accel [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { q.commit_triangle_intersection(); }
    v = q.get_committed_distance();                                     // = 1
    if (gid == 0) out[0] = v;
}
kernel void k_comm_type(device float *out [[buffer(0)]],
                        primitive_acceleration_structure accel [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { q.commit_triangle_intersection(); }
    v = (q.get_committed_intersection_type() == intersection_type::triangle)
        ? 1.0f : 0.0f;                                                  // = 1
    if (gid == 0) out[0] = v;
}
