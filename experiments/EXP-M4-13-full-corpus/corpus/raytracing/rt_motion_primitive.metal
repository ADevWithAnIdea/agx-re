#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// primitive_motion (vertex motion blur) + time param on intersect().
kernel void kmain(device float* o [[buffer(0)]],
                  primitive_acceleration_structure accel [[buffer(1)]],
                  device const float* t [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersector<triangle_data, primitive_motion> it;
    auto res = it.intersect(r, accel, t[i]);
    o[i] = res.distance;
}
