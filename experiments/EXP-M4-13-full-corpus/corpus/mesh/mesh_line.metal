// mesh_line — LINE topology. Isolates 2-index-per-primitive stores and a
// per-line primitive record. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { float3 lnormal [[flat]]; };
using ln_mesh = metal::mesh<VOut, POut, 8, 4, metal::topology::line>;  // 4 lines => 8 indices
struct Payload { float r; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp) {
    pl.r = 0.6f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(8)]]
void mesh_main(ln_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(4);
    float a = float(lane) * 0.78539816f;
    VOut v;
    v.position = float4(cos(a) * pl.r, sin(a) * pl.r, 0.0, 1.0);
    v.color    = float4(1.0, float(lane) / 8.0f, 0.0, 1.0);
    out.set_vertex(lane, v);
    if (lane < 4) {
        out.set_index(lane * 2 + 0, ushort(lane * 2 + 0));
        out.set_index(lane * 2 + 1, ushort(lane * 2 + 1));
        POut p; p.lnormal = float3(0.0, 0.0, 1.0);
        out.set_primitive(lane, p);
    }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color * float4(in.p.lnormal, 1.0);
}
