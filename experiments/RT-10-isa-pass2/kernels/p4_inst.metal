#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// RT-10 Part4: INSTANCE acceleration structure traversal (top-level AS over an instanced
// bottom-level primitive AS). The <instancing> tag + instance_acceleration_structure is the
// ONLY source-level difference vs p4_prim. out adds instance_id.
kernel void k(instance_acceleration_structure accel [[buffer(0)]],
              device float* out [[buffer(1)]],
              device const float* rin [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    ray r;
    r.origin       = float3(rin[0], rin[1], rin[2]);
    r.direction    = float3(rin[3], rin[4], rin[5]);
    r.min_distance = 0.01f;
    r.max_distance = 500.0f;
    intersector<triangle_data, instancing> isect;
    intersection_result<triangle_data, instancing> res = isect.intersect(r, accel);
    bool hit = (res.type == intersection_type::triangle);
    out[0] = hit ? 1.0f : 0.0f;
    out[1] = res.distance;
    out[2] = (float)res.primitive_id;
    out[3] = hit ? (float)res.instance_id : -9.0f;
}
