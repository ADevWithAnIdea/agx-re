// mesh_tri — TRIANGLE topology baseline (3 verts / 1 prim), 3-index-per-prim
// stores + a per-vertex color + a per-primitive normal. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { float3 pnormal [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;
struct Payload { float scale; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp) {
    pl.scale = 0.8f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    const float2 P[3] = { float2(-0.5, -0.5), float2(0.5, -0.5), float2(0.0, 0.5) };
    VOut v;
    v.position = float4(P[lane] * pl.scale, 0.0, 1.0);
    v.color    = float4(P[lane] * 0.5f + 0.5f, 0.0, 1.0);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pnormal = float3(0.0, 0.0, 1.0); out.set_primitive(0, p); }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color * float4(in.p.pnormal, 1.0);
}
