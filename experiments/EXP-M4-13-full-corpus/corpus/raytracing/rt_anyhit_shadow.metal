#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Shadow ray: accept_any_intersection -> early-out traversal mode.
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,1,0), 0.01f, 100.0f);
    intersector<triangle_data, instancing> it;
    it.accept_any_intersection(true);
    auto res = it.intersect(r, accel);
    o[i] = (res.type == intersection_type::none) ? 1.0f : 0.0f;
}
