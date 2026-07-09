#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Ray with CONST origin (0,0,0) and CONST direction (0,0,1): provokes zero-init
// (b2=0x80) marshalling moves for the origin/direction block.
kernel void k(device float* o [[buffer(0)]],
              primitive_acceleration_structure accel [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1), 0.0f, 1000.0f);
    intersector<triangle_data> it;
    intersection_result<triangle_data> res = it.intersect(r, accel);
    o[i] = res.distance;
}
