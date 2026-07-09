// mesh_transform — the mesh stage reads a constant float4x4 [[buffer(0)]] and
// transforms each vertex position by it. Isolates matrix-vector FMA chains
// (constant-buffer loads) inside the mesh stage. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { uint pid [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;
struct Payload { float3 base; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp) {
    pl.base = float3(0.0, 0.0, 0.0);
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main(tri_mesh out,
               constant float4x4& mvp [[buffer(0)]],
               const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    const float3 P[3] = { float3(-0.5,-0.5,0.0), float3(0.5,-0.5,0.0), float3(0.0,0.5,0.0) };
    VOut v;
    v.position = mvp * float4(P[lane] + pl.base, 1.0);
    v.color    = float4(P[lane] * 0.5f + 0.5f, 1.0);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pid = 3u; out.set_primitive(0, p); }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(float(in.p.pid) * 0.01f);
}
