// EXP-0187 intersection_query carriers (AUTHORED BY US; OWN-SHADER).
//
// TARGET FIELD: `n4_rt_word.dst` -- byte+1 of the 4-byte compact word
// `04 <dst> 20 80`, emitted in the ray-query traversal SETUP immediately before
// an if_push / frame_marker / reg_move. `validation.json` records it
// `tokenization-only`, "framing only (round-trips; no value semantics
// established)". It is the SINGLE field of a single-field instruction, so
// promoting it moves `n4_rt_word` across the emittable line by itself.
//
// EXP-0184 named this the next target and left the carrier proven: its four
// intersection_query carriers ran 0 hangs / 0 malformed responses / 0 cross-run
// disagreements on G17P and moved `rt_query_traverse.dst`. This file is that
// carrier set, EXTENDED so the carriers differ in the dimension `n4_rt_word.dst`
// plausibly controls (which register the traversal setup targets):
//
//   k_q_mdist   committed distance                oracle   1.0   committed phase
//   k_q_mprim   committed primitive id            oracle   2.0   committed phase
//   k_q_cdist   sum of candidate distances        oracle  10.0   candidate phase
//   k_q_ccount  number of candidates              oracle   4.0   candidate phase
//   k_q_cgeom   sum of (candidate geometry_id+1)  oracle   5.0   candidate, 2 geometries
//   k_q_multi   3 getters combined                oracle 124.0   HIGHER register pressure
//   k_q_bbox    bounding-box traversal path       oracle   6.0   the OTHER traversal path
//   k_q_inst    instancing traversal              oracle  11.0   instance AS setup
//
// Geometry contract, fixed by harness/agxrun_persist_as.m (EXP-0157's AS-capable
// runner, reused verbatim and cited):
//   --accel-kind primitive : geometry 0 = 3 NON-OPAQUE triangles at z = 3,2,1
//                            (primitive ids 0,1,2); geometry 1 = 1 NON-OPAQUE
//                            triangle at z = 4 (primitive id 0).
//   --accel-kind bbox      : 3 axis-aligned boxes at z in [1,1.5],[2,2.5],[3,3.5]
//                            (primitive ids 0,1,2).
//   --accel-kind instance  : one identity instance wrapping the primitive AS.
//   ray: origin (0,0,0), direction (0,0,1), t in [0,100] -> every primitive is hit.
// `opaque = NO` is load-bearing: an opaque hit is committed without ever
// surfacing as a candidate, which would make the candidate getters dead.
//
// EVERY ORACLE IS NON-ZERO BY CONSTRUCTION. On Apple9 a wrong field value
// usually produces a SILENT ZERO, and a zero oracle scores that silent zero as a
// pass. out[1] is an integrity sentinel written through a path independent of
// the ray query and BEFORE it; out[2..3] are never stored to and must stay POISON.
//
// Shape (not results) reused and cited from EXP-0184 kernels/k_rq184.metal and
// EXP-0157 kernels/k_rq_getters.metal -- our own MSL, same project, same rules.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;

#define RQ_PROLOGUE                            \
    ray r;                                     \
    r.origin       = float3(0.0f, 0.0f, 0.0f); \
    r.direction    = float3(0.0f, 0.0f, 1.0f); \
    r.min_distance = 0.0f;                     \
    r.max_distance = 100.0f;                   \
    float v = 0.0f;                            \
    if (gid == 0) out[1] = 7.5f;

kernel void k_q_mdist(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    intersection_query<> q; q.reset(r, accel);
    while (q.next()) { q.commit_triangle_intersection(); }
    v = q.get_committed_distance();                              // = 1.0
    if (gid == 0) out[0] = v;
}

kernel void k_q_mprim(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    intersection_query<> q; q.reset(r, accel);
    while (q.next()) { q.commit_triangle_intersection(); }
    v = float(q.get_committed_primitive_id());                   // = 2.0
    if (gid == 0) out[0] = v;
}

kernel void k_q_cdist(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    intersection_query<> q; q.reset(r, accel);
    while (q.next()) { v += q.get_candidate_triangle_distance(); }   // 3+2+1+4
    if (gid == 0) out[0] = v;
}

kernel void k_q_ccount(device float *out [[buffer(0)]],
                       primitive_acceleration_structure accel [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    intersection_query<> q; q.reset(r, accel);
    while (q.next()) { v += 1.0f; }                                  // = 4.0
    if (gid == 0) out[0] = v;
}

kernel void k_q_cgeom(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    intersection_query<> q; q.reset(r, accel);
    while (q.next()) {
        v += float(q.get_candidate_geometry_id()) + 1.0f;            // 1+1+1+2 = 5
    }
    if (gid == 0) out[0] = v;
}

kernel void k_q_multi(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    intersection_query<> q; q.reset(r, accel);
    float n = 0.0f;
    while (q.next()) { n += 1.0f; q.commit_triangle_intersection(); }
    v = q.get_committed_distance() * 100.0f
        + float(q.get_committed_primitive_id()) * 10.0f + n;          // 100+20+4
    if (gid == 0) out[0] = v;
}

kernel void k_q_bbox(device float *out [[buffer(0)]],
                     primitive_acceleration_structure accel [[buffer(1)]],
                     uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    intersection_query<> q; q.reset(r, accel);
    while (q.next()) {
        if (q.get_candidate_intersection_type() ==
            intersection_type::bounding_box) {
            v += float(q.get_candidate_primitive_id()) + 1.0f;        // 1+2+3 = 6
        }
    }
    if (gid == 0) out[0] = v;
}

kernel void k_q_inst(device float *out [[buffer(0)]],
                     instance_acceleration_structure accel [[buffer(1)]],
                     uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    intersection_query<instancing> q; q.reset(r, accel);
    while (q.next()) { q.commit_triangle_intersection(); }
    v = q.get_committed_distance() * 10.0f
        + float(q.get_committed_instance_id()) + 1.0f;                // 10+0+1 = 11
    if (gid == 0) out[0] = v;
}
