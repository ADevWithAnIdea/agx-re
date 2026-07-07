// EXP-O2C RT-from-render probe (extends EXP-0023). A fragment shader that traces
// a ray (supportsRaytracingFromRender). Extract the FRAGMENT stage bytes and
// compare the RT lowering to the compute path. CLEAN-ROOM: OUR OWN MSL.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

struct VOut { float4 pos [[position]]; float2 uv; };

vertex VOut v_main(uint vid [[vertex_id]]) {
    // full-screen triangle
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid], 0, 1); o.uv = p[vid]*0.5+0.5; return o;
}

// Fragment shader traces a ray using the INLINE intersection_query API
// (no function table binding needed at pipeline-build time), reading the AS
// from a fragment-stage argument buffer.
fragment float4 f_rt(VOut in [[stage_in]],
                     primitive_acceleration_structure accel [[buffer(0)]]) {
    ray r;
    r.origin       = float3(in.uv*2.0-1.0, 0.0);
    r.direction    = float3(0,0,1);
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersection_query<triangle_data> q;
    q.reset(r, accel);
    while (q.next()) {
        if (q.get_candidate_intersection_type()==intersection_type::triangle)
            q.commit_triangle_intersection();
    }
    float t = (q.get_committed_intersection_type()==intersection_type::triangle)
            ? q.get_committed_distance() : -1.0f;
    return float4(t, t*0.1, 0, 1);
}

// Control: same fragment shape without RT (plain gradient) -- diff to isolate
// the RT-specific ops in the fragment stage.
fragment float4 f_plain(VOut in [[stage_in]]) {
    return float4(in.uv, 0, 1);
}

// Intersector-object variant from render (if it lowers differently than inline).
fragment float4 f_rt_isect(VOut in [[stage_in]],
                           primitive_acceleration_structure accel [[buffer(0)]]) {
    ray r;
    r.origin       = float3(in.uv*2.0-1.0, 0.0);
    r.direction    = float3(0,0,1);
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersector<triangle_data> isect;
    isect.assume_geometry_type(geometry_type::triangle);
    auto res = isect.intersect(r, accel);
    float t = (res.type==intersection_type::triangle) ? res.distance : -1.0f;
    return float4(t, 0, 0, 1);
}
