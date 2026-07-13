// EXP-M5-09: Ray-tracing ISA provocations on M5. Identify RT leaders (accel-structure
// load, traversal/intersect, ray payload) and compare to A18's rt_intersect(0x?4+0xea)/
// rt_as_load(0xdf)/rt_ray_mem(0x5f). CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

// intersector (compiler-generated traversal loop) over an instance AS, triangle data.
kernel void rt_isect(device float *o [[buffer(0)]],
                     instance_acceleration_structure a [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = 1e9;
    intersector<instancing, triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance;
}

// inline intersection_query over a primitive AS.
kernel void rt_query(device float *o [[buffer(0)]],
                     primitive_acceleration_structure a [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = 1e9;
    intersection_query<triangle_data> q;
    q.reset(r, a);
    q.next();
    o[i] = q.get_committed_distance();
}

// primitive-AS intersector (no instancing) -> simplest traversal, isolate core RT ops.
kernel void rt_prim(device float *o [[buffer(0)]],
                    primitive_acceleration_structure a [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = 1e9;
    intersector<triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance;
}

// query that also reads payload-ish fields (primitive id, barycentrics) -> more ray-data ops.
kernel void rt_query2(device float *o [[buffer(0)]],
                      primitive_acceleration_structure a [[buffer(1)]],
                      uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = 1e9;
    intersection_query<triangle_data> q;
    q.reset(r, a);
    while (q.next()) {}
    float d = q.get_committed_distance();
    uint pid = q.get_committed_primitive_id();
    float2 bc = q.get_committed_triangle_barycentric_coord();
    o[i] = d + float(pid) + bc.x + bc.y;
}
