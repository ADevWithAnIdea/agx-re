// EXP-0184 intersection_query carriers (AUTHORED BY US; OWN-SHADER).
//
// TARGET FIELD: `rt_query_traverse.dst` = byte0's HIGH nibble of the 8-byte
// `?f 80 86 <opA> <sel> 22 82 <opB>`. `validation.json` records it as
// `label: untested, range: "none"` -- it has NEVER been swept, on any target,
// while TWO sibling fields of the SAME instruction (`sel` byte+4 and `opB`
// byte+7) are `hardware-run` and demonstrably load-bearing on A18 (EXP-M4-14:
// opB in {0x42,0x48,0xc8} gives the correct near hit, eight values skip it, four
// HANG the traversal). A destination-register selector on a load-bearing op is
// the strongest prior in the one-field-away list.
//
// Geometry contract (fixed by harness/agxrun_persist_as.m, which is EXP-0157's
// AS-capable runner used verbatim):
//   geometry 0: three NON-OPAQUE triangles at z = 3, 2, 1  (primitive ids 0,1,2)
//   geometry 1: one   NON-OPAQUE triangle  at z = 4        (primitive id 0)
//   ray: origin (0,0,0), direction (0,0,1), t in [0,100] -> all four are hit.
// `opaque = NO` is load-bearing: an opaque hit is committed by the hardware
// without ever surfacing as a candidate, so the candidate getters would be dead.
//
// FOUR CARRIERS, differing in the dimension `dst` controls (which register the
// traversal result lands in) and in query PHASE (candidate vs committed), so
// two arms are never one arm:
//   k_q_mdist   committed distance          oracle 1.0   (closest hit)
//   k_q_mprim   committed primitive id      oracle 2.0
//   k_q_cdist   sum of candidate distances  oracle 10.0  (3+2+1+4)
//   k_q_ccount  number of candidates        oracle 4.0
//
// Every oracle is NON-ZERO by construction: on Apple9 a wrong field value
// usually produces a silent zero, and a zero oracle scores that as a pass.
// out[1] is a query-INDEPENDENT integrity sentinel; out[2..3] are never stored
// to and must stay POISON.
//
// Shape (not results) reused and cited from EXP-0157 kernels/k_rq_getters.metal,
// same project, same rules.
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
    intersection_query<> q;                    \
    q.reset(r, accel);                         \
    float v = 0.0f;                            \
    if (gid == 0) out[1] = 7.5f;

kernel void k_q_mdist(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { q.commit_triangle_intersection(); }
    v = q.get_committed_distance();                       // = 1.0
    if (gid == 0) out[0] = v;
}

kernel void k_q_mprim(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { q.commit_triangle_intersection(); }
    v = float(q.get_committed_primitive_id());            // = 2.0
    if (gid == 0) out[0] = v;
}

kernel void k_q_cdist(device float *out [[buffer(0)]],
                      primitive_acceleration_structure accel [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { v += q.get_candidate_triangle_distance(); }   // 3+2+1+4
    if (gid == 0) out[0] = v;
}

kernel void k_q_ccount(device float *out [[buffer(0)]],
                       primitive_acceleration_structure accel [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    RQ_PROLOGUE
    while (q.next()) { v += 1.0f; }                                  // = 4.0
    if (gid == 0) out[0] = v;
}
