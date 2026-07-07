// EXP-0030 mesh_variants.metal — OWN-SHADER single-change variants for byte-diff
// field decode of the object/mesh emit path. Each function differs from the
// baseline by exactly one thing so bytediff localizes the moved field.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { float3 pnormal [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;
struct Payload { float scale; float p0; float p1; float p2; };

// ---------- object variants (mesh-grid amplification / payload) --------------
[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_base(object_data Payload &pl [[payload]], mesh_grid_properties mgp, uint tid [[thread_position_in_grid]]) {
    pl.scale = 1.0f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}
[[object, max_total_threadgroups_per_mesh_grid(4)]]
void obj_grid2(object_data Payload &pl [[payload]], mesh_grid_properties mgp, uint tid [[thread_position_in_grid]]) {
    pl.scale = 1.0f;
    mgp.set_threadgroups_per_grid(uint3(2, 1, 1));    // <-- amplify to 2 mesh TGs
}
[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_scale2(object_data Payload &pl [[payload]], mesh_grid_properties mgp, uint tid [[thread_position_in_grid]]) {
    pl.scale = 2.0f;                                  // <-- payload value change
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

// ---------- mesh variants (emit ops) -----------------------------------------
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_base(tri_mesh out, const object_data Payload &pl [[payload]], uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    float2 P[3] = { float2(-0.5,-0.5), float2(0.5,-0.5), float2(0.0,0.5) };
    VOut v; v.position = float4(P[lane]*pl.scale, 0, 1); v.color = float4(0,1,0,1);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pnormal = float3(0,0,1); out.set_primitive(0, p); }
}
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_emit0(tri_mesh out, const object_data Payload &pl [[payload]], uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(0);        // <-- emit NOTHING
}
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_colorR(tri_mesh out, const object_data Payload &pl [[payload]], uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    float2 P[3] = { float2(-0.5,-0.5), float2(0.5,-0.5), float2(0.0,0.5) };
    VOut v; v.position = float4(P[lane]*pl.scale, 0, 1); v.color = float4(1,0,0,1);  // <-- red
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pnormal = float3(0,0,1); out.set_primitive(0, p); }
}
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_idxrev(tri_mesh out, const object_data Payload &pl [[payload]], uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    float2 P[3] = { float2(-0.5,-0.5), float2(0.5,-0.5), float2(0.0,0.5) };
    VOut v; v.position = float4(P[lane]*pl.scale, 0, 1); v.color = float4(0,1,0,1);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(2 - lane));             // <-- reversed index value
    if (lane == 0) { POut p; p.pnormal = float3(0,0,1); out.set_primitive(0, p); }
}
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_vslot(tri_mesh out, const object_data Payload &pl [[payload]], uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    float2 P[3] = { float2(-0.5,-0.5), float2(0.5,-0.5), float2(0.0,0.5) };
    VOut v; v.position = float4(P[lane]*pl.scale, 0, 1); v.color = float4(0,1,0,1);
    out.set_vertex(2 - lane, v);                      // <-- reversed destination slot
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pnormal = float3(0,0,1); out.set_primitive(0, p); }
}

// ---------- fragment (shared) -------------------------------------------------
struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) { return in.v.color; }
