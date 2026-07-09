// EXP-M4-13 R2 (own-MSL, clean-room): provoke the 0x?b RAY register-marshalling
// MOVE runs (byte+2 0x40/0x41/0x80/0x81) + intersection-query state move (0x09)
// emitted around a ray_intersect. COMPILE-ONLY extraction (shdump never dispatches).
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;

kernel void rt_marshal(
    device float *out            [[buffer(0)]],
    device const float3 *origins [[buffer(1)]],
    device const float3 *dirs    [[buffer(2)]],
    instance_acceleration_structure accel [[buffer(3)]],
    uint tid [[thread_position_in_grid]])
{
    // Build a ray from device-loaded origin/direction (forces copy-form 0x41/0x81
    // marshalling of origin.xyz / dir.xyz / tmin / tmax into the contiguous block).
    ray r;
    r.origin = origins[tid];
    r.direction = dirs[tid];
    r.min_distance = 0.0f;      // const -> zero-init form (0x40/0x80)
    r.max_distance = 1e30f;

    intersector<instancing, triangle_data> isect;
    isect.assume_geometry_type(geometry_type::triangle);

    // intersection_query state read (0x09 rtq_state_move) via the query API.
    intersection_query<instancing, triangle_data> q;
    q.reset(r, accel);
    float t = 1e30f;
    while (q.next()) {
        t = min(t, q.get_candidate_triangle_distance());
        q.commit_triangle_intersection();
    }
    out[tid] = t;
}
