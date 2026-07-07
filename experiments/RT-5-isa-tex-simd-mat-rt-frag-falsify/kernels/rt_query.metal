#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

// One ray traced against a PRIMITIVE acceleration structure (a triangle at z=3).
// out = [hit, distance, primitive_id, geometry_id]. rays buffer supplies origin+dir.
kernel void k(primitive_acceleration_structure accel [[buffer(0)]],
              device float* out [[buffer(1)]],
              device const float* rin [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    ray r;
    r.origin = float3(rin[0], rin[1], rin[2]);
    r.direction = float3(rin[3], rin[4], rin[5]);
    r.min_distance = 0.001f;
    r.max_distance = 1000.0f;
    intersector<triangle_data> isect;
    intersection_result<triangle_data> res = isect.intersect(r, accel);
    out[0] = (res.type == intersection_type::triangle) ? 1.0f : 0.0f;
    out[1] = res.distance;
    out[2] = (float)res.primitive_id;
    out[3] = res.type == intersection_type::triangle ? res.triangle_barycentric_coord.x : -1.0f;
}
