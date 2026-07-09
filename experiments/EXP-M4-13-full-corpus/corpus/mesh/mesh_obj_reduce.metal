// mesh_obj_reduce — OBJECT stage does a threadgroup reduction (shared mem +
// barriers) over a device buffer, writes the result to the payload, and derives
// a DYNAMIC amplification factor from it. Isolates object-stage threadgroup
// reduction + barriers + data-dependent set_threadgroups_per_grid. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { float total [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;
struct Payload { float total; uint count; };

[[object, max_total_threadgroups_per_mesh_grid(8)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp,
              device const float* src [[buffer(0)]],
              uint lane [[thread_index_in_threadgroup]]) {
    threadgroup float sh[32];
    sh[lane] = src[lane];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint s = 16u; s > 0u; s >>= 1) {
        if (lane < s) sh[lane] += sh[lane + s];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    uint cnt = uint(clamp(sh[0], 1.0f, 8.0f));
    if (lane == 0) { pl.total = sh[0]; pl.count = cnt; }
    mgp.set_threadgroups_per_grid(uint3(cnt, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]],
               uint3 mgpos [[threadgroup_position_in_grid]]) {
    if (lane == 0) out.set_primitive_count(1);
    const float2 P[3] = { float2(-0.3,-0.3), float2(0.3,-0.3), float2(0.0,0.3) };
    VOut v;
    v.position = float4(P[lane] + float2(float(mgpos.x) * 0.1f, 0.0), 0.0, 1.0);
    v.color    = float4(pl.total * 0.01f, float(pl.count) / 8.0f, 1.0, 1.0);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.total = pl.total; out.set_primitive(0, p); }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(in.p.total * 0.001f);
}
