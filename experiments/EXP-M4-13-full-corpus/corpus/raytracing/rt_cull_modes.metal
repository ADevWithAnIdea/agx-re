#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// triangle_cull_mode + opacity_cull_mode + assume_geometry_type config.
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersector<triangle_data, instancing> it;
    it.set_triangle_cull_mode(triangle_cull_mode::back);
    it.set_opacity_cull_mode(opacity_cull_mode::opaque);
    it.assume_geometry_type(geometry_type::triangle);
    auto res = it.intersect(r, accel);
    o[i] = res.distance;
}
