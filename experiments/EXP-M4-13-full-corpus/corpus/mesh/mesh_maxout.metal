// mesh_maxout — a LARGE mesh: 64 vertices / 32 triangles (96 indices). One lane
// per vertex writes set_vertex; the first 32 lanes each emit one primitive with 3
// set_index + set_primitive. Isolates high-count store loops and the register
// pressure of a big mesh threadgroup. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { uint pid [[flat]]; };
using big_mesh = metal::mesh<VOut, POut, 64, 32, metal::topology::triangle>;
struct Payload { float radius; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp) {
    pl.radius = 0.9f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(64)]]
void mesh_main(big_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(32);
    float a = float(lane) * 0.09817477f;      // 2*pi/64
    VOut v;
    v.position = float4(cos(a) * pl.radius, sin(a) * pl.radius, 0.0, 1.0);
    v.color    = float4(float(lane) / 64.0f, 1.0 - float(lane) / 64.0f, 0.0, 1.0);
    out.set_vertex(lane, v);
    if (lane < 32) {
        uint b = lane * 3u;
        out.set_index(b + 0u, uchar((lane * 2u) & 63u));
        out.set_index(b + 1u, uchar((lane * 2u + 1u) & 63u));
        out.set_index(b + 2u, uchar((lane * 2u + 2u) & 63u));
        POut p; p.pid = lane;
        out.set_primitive(lane, p);
    }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(float(in.p.pid) / 32.0f);
}
