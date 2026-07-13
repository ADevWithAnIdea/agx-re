// EXP-M5-19: M5 ray-tracing AS-load + ray-data field provocations. CLEAN-ROOM: OUR OWN MSL.
// Goal: byte-diff kernels that vary (a) the acceleration-structure BINDING SLOT and (b) the
// ray fields (origin/dir/tmin/tmax const vs device-loaded) to isolate, on M5's split memory
// family, the AS-handle load op and the ray-data read ops. No Apple binary is inspected.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

// ---- AS-handle load: vary the AS binding SLOT (const ray everywhere) ---------------------
// AS at buffer(1). Baseline.
kernel void as_slot1(device float *o [[buffer(0)]],
                     primitive_acceleration_structure a [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = INFINITY;
    intersector<triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance;
}
// AS moved to buffer(3); dummy device buffers occupy 1,2. Same const ray.
kernel void as_slot3(device float *o [[buffer(0)]],
                     device const float *d1 [[buffer(1)]],
                     device const float *d2 [[buffer(2)]],
                     primitive_acceleration_structure a [[buffer(3)]],
                     uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = INFINITY;
    intersector<triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance + d1[i]*0 + d2[i]*0;
}

// ---- ray-data reads: const vs device-loaded origin/dir/tmin/tmax -------------------------
// Fully constant ray (origin=0, dir=+z, tmin=0, tmax=inf). AS at buffer(1).
kernel void ray_const(device float *o [[buffer(0)]],
                      primitive_acceleration_structure a [[buffer(1)]],
                      uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = INFINITY;
    intersector<triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance;
}
// Origin device-loaded, rest const.
kernel void ray_org(device float *o [[buffer(0)]],
                    primitive_acceleration_structure a [[buffer(1)]],
                    device const packed_float3 *org [[buffer(2)]],
                    uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(org[i]); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = INFINITY;
    intersector<triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance;
}
// Direction device-loaded, rest const.
kernel void ray_dir(device float *o [[buffer(0)]],
                    primitive_acceleration_structure a [[buffer(1)]],
                    device const packed_float3 *dir [[buffer(2)]],
                    uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(dir[i]);
    r.min_distance = 0; r.max_distance = INFINITY;
    intersector<triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance;
}
// tmin/tmax device-loaded, rest const.
kernel void ray_trange(device float *o [[buffer(0)]],
                       primitive_acceleration_structure a [[buffer(1)]],
                       device const float *tn [[buffer(2)]],
                       device const float *tx [[buffer(3)]],
                       uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = tn[i]; r.max_distance = tx[i];
    intersector<triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance;
}
// All ray fields device-loaded.
kernel void ray_all(device float *o [[buffer(0)]],
                    primitive_acceleration_structure a [[buffer(1)]],
                    device const packed_float3 *org [[buffer(2)]],
                    device const packed_float3 *dir [[buffer(3)]],
                    device const float *tn [[buffer(4)]],
                    device const float *tx [[buffer(5)]],
                    uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(org[i]); r.direction = float3(dir[i]);
    r.min_distance = tn[i]; r.max_distance = tx[i];
    intersector<triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance;
}

// ---- AS type: primitive vs instance (byte+4 selector in rt_intersect) --------------------
kernel void as_inst(device float *o [[buffer(0)]],
                    instance_acceleration_structure a [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = INFINITY;
    intersector<instancing, triangle_data> it;
    auto res = it.intersect(r, a);
    o[i] = res.distance;
}

// ---- inline intersection_query: const vs dynamic ray -------------------------------------
kernel void rq_const(device float *o [[buffer(0)]],
                     primitive_acceleration_structure a [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(0); r.direction = float3(0,0,1);
    r.min_distance = 0; r.max_distance = INFINITY;
    intersection_query<triangle_data> q;
    q.reset(r, a);
    q.next();
    o[i] = q.get_committed_distance();
}
kernel void rq_dyn(device float *o [[buffer(0)]],
                   primitive_acceleration_structure a [[buffer(1)]],
                   device const packed_float3 *org [[buffer(2)]],
                   device const packed_float3 *dir [[buffer(3)]],
                   uint i [[thread_position_in_grid]]) {
    ray r; r.origin = float3(org[i]); r.direction = float3(dir[i]);
    r.min_distance = 0; r.max_distance = INFINITY;
    intersection_query<triangle_data> q;
    q.reset(r, a);
    q.next();
    o[i] = q.get_committed_distance();
}
