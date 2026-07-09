// mesh_pervertex_wide — WIDE per-vertex record: 3x float4 + half4 + float2, all
// interpolated. Isolates wide per-vertex stores via out.set_vertex() and half
// packing in the mesh stage. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut {
    float4 position [[position]];
    float4 c0;
    float4 c1;
    float4 c2;
    half4  h;
    float2 uv;
};
struct POut { uint pid [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;
struct Payload { float t; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp) {
    pl.t = 0.5f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    const float2 P[3] = { float2(-0.5,-0.5), float2(0.5,-0.5), float2(0.0,0.5) };
    float f = float(lane);
    VOut v;
    v.position = float4(P[lane], 0.0, 1.0);
    v.c0 = float4(f, f + 1.0, f + 2.0, 1.0);
    v.c1 = float4(sin(f), cos(f), tan(f * 0.25f), pl.t);
    v.c2 = float4(P[lane] * pl.t, f * 0.1f, 1.0);
    v.h  = half4(half(f), half(0.5), half(-1.0), half(pl.t));
    v.uv = P[lane] * 0.5f + 0.5f;
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pid = 7u; out.set_primitive(0, p); }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.c0 + in.v.c1 + in.v.c2 + float4(in.v.h) + float4(in.v.uv, 0.0, 0.0)
         + float4(float(in.p.pid) * 0.01f);
}
