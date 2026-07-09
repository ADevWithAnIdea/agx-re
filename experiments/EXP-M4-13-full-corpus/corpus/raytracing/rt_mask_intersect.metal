#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Instance mask cull param on intersect().
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  device const uint* mask [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersector<triangle_data, instancing> it;
    auto res = it.intersect(r, accel, mask[i]);
    o[i] = res.distance;
}
