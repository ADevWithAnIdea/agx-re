#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;
// EXP-0157 (OWN-SHADER). BOUNDING-BOX ray-query carriers.
//
// WHY: the reachability probe (harness/reachprobe.py) showed that a
// TRIANGLE-only intersection query never executes the regions holding
// `rtq_pred` and `rtq_dualsrc` -- erasing 256 contiguous bytes at eleven of
// their resolved offsets leaves the traversal result exactly correct, while
// the same erase over a live `sr_read_wide` breaks it at four bytes. Custom
// (bounding-box) geometry takes the other traversal path: a candidate is a box
// the shader must range-test itself and commit with an explicit distance, so
// the query loop carries a real predicate -- which is what `rtq_pred`'s name
// and db.json provenance both describe.
//
// Geometry (built by harness/agxrun_persist_as.m --accel-kind bbox): three
// non-opaque axis-aligned boxes spanning z in [1,1.5], [2,2.5], [3,3.5], all
// straddling the +z axis. The ray (origin 0, direction +z, t in [0,100]) hits
// all three, with primitive ids 0, 1, 2.
//
// out[1] = 7.5 is the query-independent integrity sentinel.
#define BB_PROLOGUE                        \
    ray r;                                 \
    r.origin       = float3(0.0f, 0.0f, 0.0f); \
    r.direction    = float3(0.0f, 0.0f, 1.0f); \
    r.min_distance = 0.0f;                 \
    r.max_distance = 100.0f;               \
    intersection_query<> q;                \
    q.reset(r, accel);                     \
    float v = 0.0f;                        \
    if (gid == 0) out[1] = 7.5f;

kernel void k_bb_count(device float *out [[buffer(0)]],
                       primitive_acceleration_structure accel [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    BB_PROLOGUE
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::bounding_box)
            v += 1.0f;                                            // = 3
    }
    if (gid == 0) out[0] = v;
}
kernel void k_bb_prim(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    BB_PROLOGUE
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::bounding_box)
            v += float(q.get_candidate_primitive_id()) + 1.0f;    // = 1+2+3 = 6
    }
    if (gid == 0) out[0] = v;
}
kernel void k_bb_commit(device float *out [[buffer(0)]],
                        primitive_acceleration_structure accel [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    BB_PROLOGUE
    // A real custom-intersection loop: range-test each candidate box and commit
    // the hit at the box's own near plane. Committing narrows the interval, so
    // the committed result is the NEAREST box.
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::bounding_box) {
            float t = float(q.get_candidate_primitive_id()) + 1.0f;
            if (t > 0.0f && t < 100.0f)
                q.commit_bounding_box_intersection(t);
        }
    }
    v = q.get_committed_distance();                               // = 1
    if (gid == 0) out[0] = v;
}
kernel void k_bb_geom(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    BB_PROLOGUE
    while (q.next()) {
        if (q.is_candidate_non_opaque_bounding_box())
            v += float(q.get_candidate_geometry_id()) + 2.0f;     // = 2+2+2 = 6
    }
    if (gid == 0) out[0] = v;
}
