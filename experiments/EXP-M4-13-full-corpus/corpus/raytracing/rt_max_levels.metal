#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// max_levels<N> multi-level instancing tag (nested BLAS/TLAS traversal).
kernel void kmain(device float* o [[buffer(0)]],
                  instance_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersector<triangle_data, instancing, max_levels<8>> it;
    auto res = it.intersect(r, accel);
    o[i] = res.distance + float(res.primitive_id)
         + res.triangle_barycentric_coord.x;
}
