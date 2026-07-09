// mesh_barrier — mesh stage uses THREADGROUP memory + a threadgroup barrier to
// exchange data between lanes before emitting vertices. Isolates the barrier op
// and threadgroup load/store inside the mesh stage. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { float pavg [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 32, 10, metal::topology::triangle>;
struct Payload { float phase; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp) {
    pl.phase = 0.3f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(32)]]
void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    threadgroup float sh[32];
    sh[lane] = sin(float(lane) * 0.2f + pl.phase);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    float neighbor = sh[(lane + 1u) & 31u] + sh[(lane + 31u) & 31u];
    threadgroup_barrier(mem_flags::mem_threadgroup);

    if (lane == 0) out.set_primitive_count(10);
    float a = float(lane) * 0.19634954f;
    VOut v;
    v.position = float4(cos(a) * 0.7f, sin(a) * 0.7f, 0.0, 1.0);
    v.color    = float4(neighbor * 0.5f + 0.5f, 0.0, 1.0, 1.0);
    out.set_vertex(lane, v);
    if (lane < 10) {
        out.set_index(lane * 3 + 0, uchar(lane));
        out.set_index(lane * 3 + 1, uchar(lane + 1));
        out.set_index(lane * 3 + 2, uchar((lane + 2) & 31u));
        POut p; p.pavg = neighbor; out.set_primitive(lane, p);
    }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(in.p.pavg * 0.1f);
}
