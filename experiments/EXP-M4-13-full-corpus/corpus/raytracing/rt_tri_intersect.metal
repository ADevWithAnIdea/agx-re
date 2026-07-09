#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
// Bottom-level triangle intersect: implicit traversal, barycentric+ids result.
kernel void kmain(device float* o [[buffer(0)]],
                  primitive_acceleration_structure accel [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1), 0.0f, 1000.0f);
    intersector<triangle_data> it;
    intersection_result<triangle_data> res = it.intersect(r, accel);
    float acc = res.distance;
    acc += float(res.primitive_id) + float(res.geometry_id);
    acc += res.triangle_barycentric_coord.x + res.triangle_barycentric_coord.y;
    acc += res.triangle_front_facing ? 1.0f : 0.0f;
    o[i] = acc;
}
