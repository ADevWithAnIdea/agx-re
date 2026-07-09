#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// curve_data tag + curve_parameter result field.
kernel void kmain(device float* o [[buffer(0)]],
                  primitive_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersector<triangle_data, curve_data> it;
    auto res = it.intersect(r, accel);
    o[i] = res.distance + res.curve_parameter;
}
