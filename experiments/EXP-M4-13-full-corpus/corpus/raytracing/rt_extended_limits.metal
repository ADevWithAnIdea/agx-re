#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// extended_limits tag (large accel structures).
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersector<triangle_data, instancing, extended_limits> it;
    auto res = it.intersect(r, accel);
    o[i] = res.distance + float(res.primitive_id);
}
