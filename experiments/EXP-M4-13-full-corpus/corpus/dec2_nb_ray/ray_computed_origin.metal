#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Ray with COMPUTED origin/direction loaded from device memory: provokes COPY
// (b2=0x41) marshalling moves (GPR-source) instead of zero-init.
kernel void k(device float* o [[buffer(0)]],
              device const float3* src [[buffer(2)]],
              primitive_acceleration_structure accel [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    float3 org = src[i*2+0];
    float3 dir = src[i*2+1];
    ray r(org, dir, 0.0f, 1000.0f);
    intersector<triangle_data> it;
    intersection_result<triangle_data> res = it.intersect(r, accel);
    o[i] = res.distance;
}
