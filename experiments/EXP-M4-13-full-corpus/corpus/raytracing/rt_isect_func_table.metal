#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// intersect() with an intersection_function_table (custom-intersection call path).
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  intersection_function_table<triangle_data, instancing> funcs [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersector<triangle_data, instancing> it;
    auto res = it.intersect(r, accel, 0xFFu, funcs);
    o[i] = res.distance;
}
