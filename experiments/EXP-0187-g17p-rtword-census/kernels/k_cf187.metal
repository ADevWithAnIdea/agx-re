// EXP-0187 DIVERGENT-CONTROL-FLOW / BARRIER / RAY-QUERY census candidates
// (AUTHORED BY US; OWN-SHADER).
//
// CENSUS QUESTION (target 2): which MSL constructs make the G17P compiler emit
// `n4_cf_word` -- the 4-byte compact control word `04 01 00 <b3>` that `db.json`
// says precedes a `pop_reconverge` / `rt_ray_mem` / `threadgroup_barrier`?
//
// `n4_cf_word.b3` was DECLINED on a measured basis: EXP-0172 dispatched all 256
// values and found the WHOLE 4-byte word had no detection power -- "no
// observable effect at all, not merely b3" (its DEF-0172-4). So the census here
// asks the prior question and bounds it: which constructs emit the opcode at
// all, and how many occurrences, so a future dispatch knows whether a carrier
// exists to build on and what EXP-0172's null was measured against.
//
// CLEAN-ROOM: our own MSL only. No Apple binary is disassembled.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;

// 1. simple divergent if
kernel void k_cf_if(device float *out [[buffer(0)]],
                    device const float *a [[buffer(1)]],
                    uint t [[thread_position_in_grid]]) {
    float v = a[t];
    out[t] = (t & 1u) ? (v * 2.0f + 1.0f) : (v + 100.0f);
}
// 2. nested divergent if
kernel void k_cf_if3(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    float v = a[t], r;
    if (t & 1u) { r = (t & 2u) ? ((t & 4u) ? v * 2.0f + 1.0f : v + 100.0f)
                              : ((t & 4u) ? v * 4.0f + 2.0f : v + 200.0f); }
    else        { r = (t & 2u) ? ((t & 4u) ? v * 8.0f + 3.0f : v + 300.0f)
                              : ((t & 4u) ? v * 16.0f + 4.0f : v + 400.0f); }
    out[t] = r;
}
// 3. data-dependent loop (divergent trip count)
kernel void k_cf_loop(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    float r = a[t];
    for (uint i = 0; i <= (t & 3u); ++i) r = r * 2.0f + 1.0f;
    out[t] = r;
}
// 4. threadgroup barrier with threadgroup memory
kernel void k_cf_barrier(device float *out [[buffer(0)]],
                         device const float *a [[buffer(1)]],
                         threadgroup float *sh [[threadgroup(0)]],
                         uint t [[thread_position_in_threadgroup]],
                         uint g [[thread_position_in_grid]]) {
    sh[t] = a[g];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[g] = sh[(t + 1u) & 31u] * 2.0f;
}
// 5. divergent region CONTAINING a barrier-synchronised reduction
kernel void k_cf_divbar(device float *out [[buffer(0)]],
                        device const float *a [[buffer(1)]],
                        threadgroup float *sh [[threadgroup(0)]],
                        uint t [[thread_position_in_threadgroup]],
                        uint g [[thread_position_in_grid]]) {
    sh[t] = (t & 1u) ? a[g] * 2.0f : a[g] + 1.0f;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    float s = 0.0f;
    for (uint i = 0; i < 32u; ++i) s += sh[i];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[g] = (t & 2u) ? s : -s;
}
// 6. ray query with a divergent commit (the RT shape db.json cites)
kernel void k_cf_rq(device float *out [[buffer(0)]],
                    primitive_acceleration_structure accel [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0.0f); r.direction = float3(0.0f, 0.0f, 1.0f);
    r.min_distance = 0.0f; r.max_distance = 100.0f;
    intersection_query<> q; q.reset(r, accel);
    float v = 0.0f;
    while (q.next()) {
        if (q.get_candidate_triangle_distance() < 2.5f) {
            q.commit_triangle_intersection();
        } else { v += 1.0f; }
    }
    out[gid] = q.get_committed_distance() + v;
}
// 7. divergent early return
kernel void k_cf_ret(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    if (a[t] < 0.0f) { out[t] = -1.0f; return; }
    float r = a[t];
    for (uint i = 0; i < 4u; ++i) { if (r > 100.0f) break; r = r * 3.0f + 1.0f; }
    out[t] = r;
}
// 8. simdgroup reduction inside a divergent region
kernel void k_cf_simd(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    float v = a[t];
    if (t & 1u) v = simd_sum(v) * 2.0f;
    else        v = simd_max(v) + 1.0f;
    out[t] = v;
}
