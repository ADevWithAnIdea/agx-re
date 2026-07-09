#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// world_space_data: object<->world transforms available in the intersect result.
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersector<triangle_data, instancing, world_space_data> it;
    auto res = it.intersect(r, accel);
    float4x3 m = res.object_to_world_transform;
    float4x3 n = res.world_to_object_transform;
    o[i] = res.distance + m[0].x + m[3].z + n[0].x + n[3].z;
}
