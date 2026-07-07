// EXP-0023 hardware ray-tracing provocation kernels (A18 Pro / G17P / Apple9).
// CLEAN-ROOM: OUR OWN MSL. Compiled at runtime (newLibraryWithSource:); only our
// own compiled bytes are ever inspected. No Apple binary is disassembled.
//
// Goal: does raytracing::intersector / intersection_query lower to a DEDICATED
// intersect instruction (novel opcode group), or a software BVH-traversal loop?
// Diff against kernels/hand.metal (a hand-written Moller-Trumbore triangle loop).
//
// Spec refs (public Metal Shading Language Specification, Metal 4, PUBLIC):
//   2.17.6 intersector, 6.18.2 intersect funcs, 2.17.4 result,
//   2.17.8 intersection_query, 6.18.5 query funcs.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

// ---------------------------------------------------------------------------
// B2 -- intersection_query (ray_query-style, inline traversal loop)
// The Vulkan rayQuery analog: shader drives next()/commit.
// ---------------------------------------------------------------------------
kernel void rq_trace(primitive_acceleration_structure accel [[buffer(0)]],
                     device float *o [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin       = float3(0.0f, 0.0f, 0.0f);
    r.direction    = float3(0.0f, 0.0f, 1.0f);
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersection_query<triangle_data> q;
    q.reset(r, accel);
    while (q.next()) {
        if (q.get_candidate_intersection_type() == intersection_type::triangle)
            q.commit_triangle_intersection();
    }
    o[i] = (q.get_committed_intersection_type() == intersection_type::triangle)
         ? q.get_committed_distance() : -1.0f;
}

// ---------------------------------------------------------------------------
// B1 -- intersector object API (preferred on Apple9 per WWDC).
// Reads distance, primitive_id, and barycentrics from the result to force the
// compiler to emit every result-extraction path.
// ---------------------------------------------------------------------------
kernel void isect_trace(primitive_acceleration_structure accel [[buffer(0)]],
                        device float *o [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin       = float3(0.0f, 0.0f, 0.0f);
    r.direction    = float3(0.0f, 0.0f, 1.0f);
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersector<triangle_data> isect;
    isect.assume_geometry_type(geometry_type::triangle);
    intersection_result<triangle_data> res = isect.intersect(r, accel);
    if (res.type == intersection_type::triangle) {
        float2 bc = res.triangle_barycentric_coord;
        o[i] = res.distance + float(res.primitive_id) * 100.0f
             + bc.x * 10.0f + bc.y * 1.0f;
    } else {
        o[i] = -1.0f;
    }
}

// ---------------------------------------------------------------------------
// Minimal intersector: distance only (smallest possible intersect provocation).
// Diff isect_dist vs isect_trace to localize the result-field extraction.
// ---------------------------------------------------------------------------
kernel void isect_dist(primitive_acceleration_structure accel [[buffer(0)]],
                       device float *o [[buffer(1)]],
                       device float3 *dir [[buffer(2)]],
                       uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin       = float3(0.0f, 0.0f, 0.0f);
    r.direction    = dir[i];                    // device-loaded direction (defeat DCE)
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersector<triangle_data> isect;
    intersection_result<triangle_data> res = isect.intersect(r, accel);
    o[i] = (res.type == intersection_type::triangle) ? res.distance : -1.0f;
}

// ---------------------------------------------------------------------------
// Variant: ray origin/direction/tmin/tmax all device-loaded (so the ray
// fields cannot be constant-folded); byte-diff vs isect_dist to find which
// registers carry origin / direction / tmin / tmax into the intersect op.
// ---------------------------------------------------------------------------
kernel void isect_dynray(primitive_acceleration_structure accel [[buffer(0)]],
                         device float *o [[buffer(1)]],
                         device float3 *org [[buffer(2)]],
                         device float3 *dir [[buffer(3)]],
                         device float2 *range [[buffer(4)]],
                         uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin       = org[i];
    r.direction    = dir[i];
    r.min_distance = range[i].x;
    r.max_distance = range[i].y;
    intersector<triangle_data> isect;
    intersection_result<triangle_data> res = isect.intersect(r, accel);
    o[i] = (res.type == intersection_type::triangle) ? res.distance : -1.0f;
}

// ---------------------------------------------------------------------------
// Variant: opaque / accept-any-intersection (no closest-hit sort). WWDC notes
// the reorder/sort stage; accept_any_intersection may change the op mode bits.
// ---------------------------------------------------------------------------
kernel void isect_anyhit(primitive_acceleration_structure accel [[buffer(0)]],
                         device float *o [[buffer(1)]],
                         device float3 *dir [[buffer(2)]],
                         uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin       = float3(0.0f, 0.0f, 0.0f);
    r.direction    = dir[i];
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersector<triangle_data> isect;
    isect.accept_any_intersection(true);        // shadow-ray style
    intersection_result<triangle_data> res = isect.intersect(r, accel);
    o[i] = (res.type == intersection_type::triangle) ? 1.0f : -1.0f;
}

// ---------------------------------------------------------------------------
// Variant: instance acceleration structure (top-level AS w/ instancing).
// Diff vs isect_dist to see whether instancing changes the intersect op or
// only the AS descriptor / traversal setup.
// ---------------------------------------------------------------------------
kernel void isect_instance(instance_acceleration_structure accel [[buffer(0)]],
                           device float *o [[buffer(1)]],
                           device float3 *dir [[buffer(2)]],
                           uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin       = float3(0.0f, 0.0f, 0.0f);
    r.direction    = dir[i];
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersector<triangle_data, instancing> isect;
    intersection_result<triangle_data, instancing> res = isect.intersect(r, accel);
    o[i] = (res.type == intersection_type::triangle)
         ? res.distance + float(res.instance_id) : -1.0f;
}
