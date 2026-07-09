#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Top-level (instanced) triangle intersect: instance_id + user_instance_id.
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(1,2,3), normalize(float3(0,0,1)), 0.001f, 500.0f);
    intersector<triangle_data, instancing> it;
    intersection_result<triangle_data, instancing> res = it.intersect(r, accel);
    o[i] = res.distance + float(res.instance_id) + float(res.user_instance_id);
}
