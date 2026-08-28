// EXP-0141 mem_fence8 LOCATOR (compile-only). OWN MSL.
// `mem_fence8` is emitted only by intersection_query traversal, and
// tools/agxtest/agxrun_persist cannot bind an acceleration structure, so this
// instruction could NOT be dispatched by this experiment and its two fields
// stay `untested`. This kernel exists so the one fact we DID obtain -- the
// byte+3 `mask` value the compiler emits -- is reproducible by anyone.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;
kernel void k(device float* o [[buffer(0)]], device const float* a [[buffer(1)]],
              instance_acceleration_structure accel [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    ray r; r.origin = float3(a[0], a[1], a[2]); r.direction = float3(0, 0, 1);
    r.min_distance = 0.0f; r.max_distance = 100.0f;
    intersection_query<instancing, triangle_data> q;
    q.reset(r, accel);
    float d = 0.0f;
    while (q.next()) { d += q.get_candidate_triangle_distance(); q.commit_triangle_intersection(); }
    o[tid] = d + q.get_committed_distance();
}
