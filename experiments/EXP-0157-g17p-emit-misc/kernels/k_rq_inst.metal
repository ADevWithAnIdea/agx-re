#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;
// EXP-0157 (OWN-SHADER). The INSTANCE-acceleration-structure sibling of
// k_rq_prim.metal, kept because EXP-0146's k_rayquery.metal (the kernel
// EXP-M4-13 identified as the own-MSL producer of sr_read_wide) used
// `instance_acceleration_structure` and `intersection_query<instancing>`,
// and the instancing tag changes which property getters the compiler emits
// (instance_id has no primitive-AS equivalent).
// The runner builds a single identity-transform instance around the same
// 3-triangle primitive structure, so the host oracle is unchanged except for
// out[7] = committed instance id = 0.
kernel void k(device float *out [[buffer(0)]],
              instance_acceleration_structure accel [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    ray r;
    r.origin       = float3(0.0f, 0.0f, 0.0f);
    r.direction    = float3(0.0f, 0.0f, 1.0f);
    r.min_distance = 0.0f;
    r.max_distance = 100.0f;

    intersection_query<instancing> qa;
    qa.reset(r, accel);
    float n = 0.0f, sp = 0.0f, sg = 0.0f, sd = 0.0f;
    while (qa.next()) {
        n  += 1.0f;
        sp += float(qa.get_candidate_primitive_id());
        sg += float(qa.get_candidate_geometry_id());
        sd += qa.get_candidate_triangle_distance();
    }

    intersection_query<instancing> qb;
    qb.reset(r, accel);
    while (qb.next()) {
        qb.commit_triangle_intersection();
    }
    float cp = float(qb.get_committed_primitive_id());
    float cg = float(qb.get_committed_geometry_id());
    float cd = qb.get_committed_distance();
    float ci = float(qb.get_committed_instance_id());

    if (gid == 0) {
        out[0] = n;  out[1] = sp; out[2] = sg; out[3] = sd;
        out[4] = cp; out[5] = cg; out[6] = cd; out[7] = ci;
    }
}
