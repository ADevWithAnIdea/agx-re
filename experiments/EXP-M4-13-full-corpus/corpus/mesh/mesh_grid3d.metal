// mesh_grid3d — object stage amplifies into a 3D mesh grid (uint3(2,2,2)); the
// mesh stage uses threadgroup_position_in_grid (x,y,z) to place its output.
// Isolates 3D grid-id arithmetic across the object->mesh amplification. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { uint cell [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;
struct Payload { uint3 dims; };

[[object, max_total_threadgroups_per_mesh_grid(8)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp) {
    pl.dims = uint3(2, 2, 2);
    mgp.set_threadgroups_per_grid(pl.dims);
}

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]],
               uint3 g [[threadgroup_position_in_grid]]) {
    if (lane == 0) out.set_primitive_count(1);
    uint linear = g.x + g.y * pl.dims.x + g.z * pl.dims.x * pl.dims.y;
    float2 off = float2(float(g.x), float(g.y)) * 0.4f - 0.4f + float(g.z) * 0.02f;
    const float2 P[3] = { float2(-0.15,-0.15), float2(0.15,-0.15), float2(0.0,0.15) };
    VOut v;
    v.position = float4(P[lane] + off, float(g.z) * 0.1f, 1.0);
    v.color    = float4(float(g.x) / 2.0f, float(g.y) / 2.0f, float(g.z) / 2.0f, 1.0);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.cell = linear; out.set_primitive(0, p); }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(float(in.p.cell) * 0.01f);
}
