// EXP-O2C RT intersector-tag / custom-primitive / motion-blur probes
// (extends EXP-0023 -- decodes the 0x5f companion op + ray-move ops + intersect
// op variants across primitive tags). CLEAN-ROOM: OUR OWN MSL.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

// ---- baseline: triangle intersector (reference) ----------------------------
kernel void tag_tri(primitive_acceleration_structure accel [[buffer(0)]],
                    device float *o [[buffer(1)]], device float3 *dir [[buffer(2)]],
                    uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data> isect;
    auto res = isect.intersect(r, accel);
    o[i] = (res.type==intersection_type::triangle) ? res.distance : -1.0f;
}

// ---- bounding-box (procedural) primitives ---------------------------------
kernel void tag_bbox(primitive_acceleration_structure accel [[buffer(0)]],
                     intersection_function_table<> ftab [[buffer(1)]],
                     device float *o [[buffer(2)]], device float3 *dir [[buffer(3)]],
                     uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<> isect;
    isect.assume_geometry_type(geometry_type::bounding_box);
    auto res = isect.intersect(r, accel, ftab);
    o[i] = (res.type!=intersection_type::none) ? res.distance : -1.0f;
}

// ---- curve primitives (if supported) --------------------------------------
kernel void tag_curve(primitive_acceleration_structure accel [[buffer(0)]],
                      device float *o [[buffer(1)]], device float3 *dir [[buffer(2)]],
                      uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<curve_data> isect;
    isect.assume_geometry_type(geometry_type::curve);
    auto res = isect.intersect(r, accel);
    o[i] = (res.type==intersection_type::curve)
         ? (res.distance + res.curve_parameter) : -1.0f;
}

// ---- world-space data (world_space_data tag, needs instancing) ------------
kernel void tag_world(instance_acceleration_structure accel [[buffer(0)]],
                      device float *o [[buffer(1)]], device float3 *dir [[buffer(2)]],
                      uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data, instancing, world_space_data> isect;
    auto res = isect.intersect(r, accel);
    o[i] = (res.type==intersection_type::triangle) ? res.distance : -1.0f;
}

// ---- PRIMITIVE MOTION BLUR: time parameter to intersect -------------------
kernel void mb_prim(acceleration_structure<primitive_motion> accel [[buffer(0)]],
                    device float *o [[buffer(1)]], device float3 *dir [[buffer(2)]],
                    device float *tm [[buffer(3)]],
                    uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data, primitive_motion> isect;
    auto res = isect.intersect(r, accel, tm[i]);   // <-- time parameter
    o[i] = (res.type==intersection_type::triangle) ? res.distance : -1.0f;
}

// ---- constant time (folded) motion blur -----------------------------------
kernel void mb_const(acceleration_structure<primitive_motion> accel [[buffer(0)]],
                     device float *o [[buffer(1)]], device float3 *dir [[buffer(2)]],
                     uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data, primitive_motion> isect;
    auto res = isect.intersect(r, accel, 0.5f);    // constant time 0.5
    o[i] = (res.type==intersection_type::triangle) ? res.distance : -1.0f;
}

// ---- INSTANCE motion blur -------------------------------------------------
kernel void mb_inst(acceleration_structure<instancing, instance_motion> accel [[buffer(0)]],
                    device float *o [[buffer(1)]], device float3 *dir [[buffer(2)]],
                    device float *tm [[buffer(3)]],
                    uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data, instancing, instance_motion> isect;
    auto res = isect.intersect(r, accel, tm[i]);
    o[i] = (res.type==intersection_type::triangle) ? res.distance : -1.0f;
}

// ---- max_levels / opaque-triangle tuning (does it change intersect mode?) --
kernel void tag_opaque(primitive_acceleration_structure accel [[buffer(0)]],
                       device float *o [[buffer(1)]], device float3 *dir [[buffer(2)]],
                       uint i [[thread_position_in_grid]]) {
    ray r; r.origin=0; r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;
    intersector<triangle_data> isect;
    isect.force_opacity(forced_opacity::opaque);
    isect.assume_geometry_type(geometry_type::triangle);
    auto res = isect.intersect(r, accel);
    o[i] = (res.type==intersection_type::triangle) ? res.distance : -1.0f;
}
