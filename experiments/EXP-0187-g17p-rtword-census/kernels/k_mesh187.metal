// EXP-0187 MESH-stage census candidates (AUTHORED BY US; OWN-SHADER).
//
// CENSUS QUESTION (target 2): can ANY MSL we author make the G17P compiler emit
// `mesh_out_src` -- the 2-byte MESH-stage compact source op `04 <sel>`
// (byte+1 < 0x80) that `db.json` says feeds the immediately-following 14-byte
// device store `e7 02 54|64 ..` of a mesh vertex/primitive output?
//
// It has been DECLINED on a measured basis before (EXP-0184: 0 occurrences over
// 24 carriers) -- but every one of those carriers was a COMPUTE kernel, and this
// op is mesh-stage-only. This file is the first mesh-stage attempt at it, dumped
// through the mesh pipeline path (`pinned/shdump_mesh.m` + `pinned/mesh_extract.py`,
// EXP-0135's own tools) rather than the compute path that cannot see the stage.
//
// Six output shapes, spanning what `sel` could plausibly select: per-vertex only,
// per-primitive only, both, wide per-vertex payloads, line topology, and a
// dynamic (data-dependent) primitive count.
//
// CLEAN-ROOM: our own MSL only. No Apple binary is disassembled.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct VWide { float4 position [[position]]; float4 c0; float4 c1;
               float4 c2; float3 n; float u; };
struct POut { float3 pnormal [[flat]]; };
struct PWide { float3 pnormal [[flat]]; float4 pcolor; uint pid [[flat]]; };
struct Payload { float scale; float pad0; float pad1; float pad2; };

using tri_mesh   = metal::mesh<VOut,  POut,  3, 1, metal::topology::triangle>;
using tri_vonly  = metal::mesh<VOut,  void,  3, 1, metal::topology::triangle>;
using tri_wide   = metal::mesh<VWide, PWide, 12, 4, metal::topology::triangle>;
using line_mesh  = metal::mesh<VOut,  POut,  4, 2, metal::topology::line>;

[[object, max_total_threadgroups_per_mesh_grid(4)]]
void obj_main(object_data Payload &pl [[payload]], mesh_grid_properties mgp,
              uint tid [[thread_position_in_grid]]) {
    pl.scale = 1.0f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

// 1. per-vertex + per-primitive, one triangle
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_tri(tri_mesh out, const object_data Payload &pl [[payload]],
              uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    float2 P[3] = { float2(-0.5, -0.5), float2(0.5, -0.5), float2(0.0, 0.5) };
    VOut v; v.position = float4(P[lane] * pl.scale, 0.0, 1.0);
    v.color = float4(0.0, 1.0, 0.0, 1.0);
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pnormal = float3(0, 0, 1); out.set_primitive(0, p); }
}
// 2. per-vertex ONLY (no primitive struct)
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_vonly(tri_vonly out, const object_data Payload &pl [[payload]],
                uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    float2 P[3] = { float2(-0.5, -0.5), float2(0.5, -0.5), float2(0.0, 0.5) };
    VOut v; v.position = float4(P[lane] * pl.scale, 0.0, 1.0);
    v.color = float4(1.0, 0.0, 0.0, 1.0);
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
}
// 3. WIDE per-vertex and per-primitive payloads, 4 primitives
[[mesh, max_total_threads_per_threadgroup(12)]]
void mesh_wide(tri_wide out, const object_data Payload &pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(4);
    float f = float(lane) * 0.1f * pl.scale;
    VWide v;
    v.position = float4(f, f * 2.0f, 0.0, 1.0);
    v.c0 = float4(f, 0, 0, 1); v.c1 = float4(0, f, 0, 1);
    v.c2 = float4(0, 0, f, 1); v.n = float3(0, 0, 1); v.u = f;
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane < 4) {
        PWide p; p.pnormal = float3(0, 0, 1);
        p.pcolor = float4(float(lane), 0, 0, 1); p.pid = lane;
        out.set_primitive(lane, p);
    }
}
// 4. LINE topology
[[mesh, max_total_threads_per_threadgroup(4)]]
void mesh_line(line_mesh out, const object_data Payload &pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(2);
    VOut v; v.position = float4(float(lane) * 0.25f * pl.scale, 0.0, 0.0, 1.0);
    v.color = float4(0.0, 0.0, 1.0, 1.0);
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane < 2) { POut p; p.pnormal = float3(0, 1, 0); out.set_primitive(lane, p); }
}
// 5. DYNAMIC primitive count from the payload (divergent output)
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_dyn(tri_mesh out, const object_data Payload &pl [[payload]],
              uint lane [[thread_index_in_threadgroup]]) {
    uint n = (pl.scale > 0.5f) ? 1u : 0u;
    if (lane == 0) out.set_primitive_count(n);
    if (lane < 3u * n) {
        VOut v; v.position = float4(float(lane) * pl.scale, 0.0, 0.0, 1.0);
        v.color = float4(pl.scale, 0.0, 0.0, 1.0);
        out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    }
    if (lane == 0 && n) { POut p; p.pnormal = float3(1, 0, 0); out.set_primitive(0, p); }
}
// 6. mesh WITHOUT an object stage (mesh-only pipeline)
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_noobj(tri_mesh out, uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    float2 P[3] = { float2(-0.5, -0.5), float2(0.5, -0.5), float2(0.0, 0.5) };
    VOut v; v.position = float4(P[lane], 0.0, 1.0);
    v.color = float4(1.0, 1.0, 0.0, 1.0);
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pnormal = float3(0, 1, 1); out.set_primitive(0, p); }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) { return in.v.color; }
struct FragInV { VOut v; };
fragment float4 frag_vonly(FragInV in [[stage_in]]) { return in.v.color; }
struct FragInW { VWide v; PWide p; };
fragment float4 frag_wide(FragInW in [[stage_in]]) { return in.v.c0 + in.p.pcolor; }
