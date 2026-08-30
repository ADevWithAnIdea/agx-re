#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;
// EXP-0157 (OWN-SHADER). Ray-query carrier against a PRIMITIVE acceleration
// structure, authored so that every intersection_query getter reaches a
// SEPARATE output word -- the property EXP-0146's carrier lacked (its single
// accumulated `acc` could not tell one getter from another, and with no AS
// bound none of them ran at all).
//
// The runner (harness/agxrun_persist_as.m) binds a 3-triangle non-opaque
// primitive acceleration structure at buffer(1); the triangles sit in the
// z = 1, 2, 3 planes, so the ray below hits all three.
//
// HOST ORACLE (see harness/carriers.py RQ_ORACLE) -- computed from the
// geometry WE authored, never read off the GPU:
//   out[0] = number of candidates                       = 3
//   out[1] = sum of candidate primitive ids  (0+1+2)    = 3
//   out[2] = sum of candidate geometry ids   (0+0+0)    = 0
//   out[3] = sum of candidate distances      (1+2+3)    = 6
//   out[4] = committed primitive id (closest hit)       = 0
//   out[5] = committed geometry id                      = 0
//   out[6] = committed distance                         = 1
//   out[7] = committed intersection type (triangle = 1) = 1
kernel void k(device float *out [[buffer(0)]],
              primitive_acceleration_structure accel [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    ray r;
    r.origin        = float3(0.0f, 0.0f, 0.0f);
    r.direction     = float3(0.0f, 0.0f, 1.0f);
    r.min_distance   = 0.0f;
    r.max_distance   = 100.0f;

    // Pass A: enumerate every candidate without committing, so max_distance
    // is never narrowed and all three triangles surface.
    intersection_query<> qa;
    qa.reset(r, accel);
    float n = 0.0f, sp = 0.0f, sg = 0.0f, sd = 0.0f;
    while (qa.next()) {
        n  += 1.0f;
        sp += float(qa.get_candidate_primitive_id());
        sg += float(qa.get_candidate_geometry_id());
        sd += qa.get_candidate_triangle_distance();
    }

    // Pass B: standard closest-hit -- commit every candidate, which narrows
    // the interval, so the committed result is the nearest triangle.
    intersection_query<> qb;
    qb.reset(r, accel);
    while (qb.next()) {
        qb.commit_triangle_intersection();
    }
    float cp = float(qb.get_committed_primitive_id());
    float cg = float(qb.get_committed_geometry_id());
    float cd = qb.get_committed_distance();
    float ct = (qb.get_committed_intersection_type() ==
                intersection_type::triangle) ? 1.0f : 0.0f;

    if (gid == 0) {
        out[0] = n;  out[1] = sp; out[2] = sg; out[3] = sd;
        out[4] = cp; out[5] = cg; out[6] = cd; out[7] = ct;
    }
}
