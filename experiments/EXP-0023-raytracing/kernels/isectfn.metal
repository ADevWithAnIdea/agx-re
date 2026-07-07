// EXP-0023 B3: custom intersection functions + ray_data payload (A18 Pro / G17P).
// CLEAN-ROOM: OUR OWN MSL. Probes how a custom [[intersection(bounding_box)]]
// function and its ray_data payload are referenced -- a function table (like the
// visible_function_table / USC binding), a separate linked stage, etc.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

struct BBoxResult {
    bool  accept          [[accept_intersection]];
    bool  continueSearch  [[continue_search]];
    float distance        [[distance]];
};

// A custom bounding-box (procedural primitive) intersection function with a payload.
[[intersection(bounding_box, triangle_data)]]
BBoxResult sphereIsect(float3 origin           [[origin]],
                       float3 direction        [[direction]],
                       uint   primIndex        [[primitive_id]],
                       float  minD             [[min_distance]],
                       float  maxD             [[max_distance]],
                       ray_data float2 &payload [[payload]]) {
    float t = minD + 0.5f * (maxD - minD);
    payload += float2(1.0f, 2.0f);
    return { true, false, t };
}

// Caller: an intersector that invokes the custom intersection function via a
// bound intersection_function_table, passing a ray_data payload.
kernel void trace_custom(primitive_acceleration_structure accel [[buffer(0)]],
                         intersection_function_table<triangle_data> ftab [[buffer(1)]],
                         device float *o [[buffer(2)]],
                         device float3 *dir [[buffer(3)]],
                         uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin       = float3(0.0f, 0.0f, 0.0f);
    r.direction    = dir[i];
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersector<triangle_data> isect;
    float2 payload = float2(0.0f);
    intersection_result<triangle_data> res = isect.intersect(r, accel, ftab, payload);
    o[i] = (res.type != intersection_type::none) ? (res.distance + payload.x + payload.y) : -1.0f;
}
