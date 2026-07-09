// mesh_point — POINT topology. Isolates 1-index-per-primitive stores, the
// [[point_size]] vertex output, and per-point per-primitive data. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float psize [[point_size]]; float4 color; };
struct POut { uint pid [[flat]]; };
using pt_mesh = metal::mesh<VOut, POut, 8, 8, metal::topology::point>;
struct Payload { float spread; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp,
              uint tid [[thread_position_in_grid]]) {
    pl.spread = 0.25f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(8)]]
void mesh_main(pt_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(8);
    float a = float(lane) * 0.78539816f;
    VOut v;
    v.position = float4(cos(a) * pl.spread, sin(a) * pl.spread, 0.0, 1.0);
    v.psize    = 3.0f + float(lane);
    v.color    = float4(float(lane) / 8.0f, 0.0, 1.0, 1.0);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    POut p; p.pid = lane;
    out.set_primitive(lane, p);
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(float(in.p.pid) * 0.01f);
}
