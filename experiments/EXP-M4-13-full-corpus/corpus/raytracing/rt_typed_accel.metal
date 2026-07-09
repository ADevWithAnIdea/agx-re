#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Typed acceleration_structure<instancing> argument instead of instance_accel.
kernel void kmain(device float* o [[buffer(0)]],
                  acceleration_structure<instancing> accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersector<triangle_data, instancing> it;
    auto res = it.intersect(r, accel);
    o[i] = res.distance + float(res.instance_id);
}
