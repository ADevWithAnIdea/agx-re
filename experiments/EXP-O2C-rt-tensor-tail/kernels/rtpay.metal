// EXP-O2C RT ray_data payload copy-in/out ABI probes (extends EXP-0023 B3).
// How is a custom-intersection-function payload passed & returned across the
// intersect() call boundary? Vary payload size/shape and diff how the caller
// marshals it and how the callee reads/writes it (address space, registers,
// scratch). CLEAN-ROOM: OUR OWN MSL.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

struct BBoxResult {
    bool  accept          [[accept_intersection]];
    bool  continueSearch  [[continue_search]];
    float distance        [[distance]];
};

// ---- payload = float2 (small) ---------------------------------------------
[[intersection(bounding_box, triangle_data)]]
BBoxResult isect_p2(float3 o [[origin]], float3 dr [[direction]],
                    uint pid [[primitive_id]], float mn [[min_distance]],
                    float mx [[max_distance]], ray_data float2 &pl [[payload]]) {
    float t = mn + 0.5f*(mx-mn);
    pl += float2(1.0f, 2.0f);
    return { true, false, t };
}
kernel void call_p2(primitive_acceleration_structure accel [[buffer(0)]],
                    intersection_function_table<triangle_data> ftab [[buffer(1)]],
                    device float *o [[buffer(2)]], device float3 *dir [[buffer(3)]],
                    uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data> isect;
    float2 pl = float2(0.0f);
    auto res = isect.intersect(r, accel, ftab, pl);
    o[i] = (res.type!=intersection_type::none) ? (res.distance+pl.x+pl.y) : -1.0f;
}

// ---- payload = a bigger struct (8 floats) ---------------------------------
struct BigPayload { float4 a; float4 b; };
[[intersection(bounding_box, triangle_data)]]
BBoxResult isect_pbig(float3 o [[origin]], float3 dr [[direction]],
                      uint pid [[primitive_id]], float mn [[min_distance]],
                      float mx [[max_distance]], ray_data BigPayload &pl [[payload]]) {
    float t = mn + 0.5f*(mx-mn);
    pl.a += float4(1,2,3,4);
    pl.b += float4(5,6,7,8);
    return { true, false, t };
}
kernel void call_pbig(primitive_acceleration_structure accel [[buffer(0)]],
                      intersection_function_table<triangle_data> ftab [[buffer(1)]],
                      device float *o [[buffer(2)]], device float3 *dir [[buffer(3)]],
                      uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data> isect;
    BigPayload pl; pl.a=0; pl.b=0;
    auto res = isect.intersect(r, accel, ftab, pl);
    o[i] = (res.type!=intersection_type::none)
         ? (res.distance+pl.a.x+pl.a.w+pl.b.x+pl.b.w) : -1.0f;
}

// ---- no payload (function table but no ray_data arg) ----------------------
[[intersection(bounding_box, triangle_data)]]
BBoxResult isect_pnone(float3 o [[origin]], float3 dr [[direction]],
                       uint pid [[primitive_id]], float mn [[min_distance]],
                       float mx [[max_distance]]) {
    return { true, false, mn + 0.5f*(mx-mn) };
}
kernel void call_pnone(primitive_acceleration_structure accel [[buffer(0)]],
                       intersection_function_table<triangle_data> ftab [[buffer(1)]],
                       device float *o [[buffer(2)]], device float3 *dir [[buffer(3)]],
                       uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data> isect;
    auto res = isect.intersect(r, accel, ftab);
    o[i] = (res.type!=intersection_type::none) ? res.distance : -1.0f;
}

// ---- payload read-only (in only) vs write-only (out only) -----------------
[[intersection(bounding_box, triangle_data)]]
BBoxResult isect_pin(float3 o [[origin]], float3 dr [[direction]],
                     uint pid [[primitive_id]], float mn [[min_distance]],
                     float mx [[max_distance]], ray_data float2 &pl [[payload]]) {
    // reads payload, does NOT write it (copy-in only path)
    float t = mn + 0.5f*(mx-mn) + pl.x*0.0f + pl.y*0.0f;
    return { true, false, t };
}
kernel void call_pin(primitive_acceleration_structure accel [[buffer(0)]],
                     intersection_function_table<triangle_data> ftab [[buffer(1)]],
                     device float *o [[buffer(2)]], device float3 *dir [[buffer(3)]],
                     uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data> isect;
    float2 pl = float2(3.0f, 4.0f);
    auto res = isect.intersect(r, accel, ftab, pl);
    o[i] = (res.type!=intersection_type::none) ? res.distance : -1.0f;
}
