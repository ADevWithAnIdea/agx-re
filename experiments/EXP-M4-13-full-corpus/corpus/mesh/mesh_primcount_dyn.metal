// mesh_primcount_dyn — the emitted PRIMITIVE COUNT is data-dependent (read from a
// payload value the object stage computed), and each lane's primitive emission is
// predicated on lane < count. Isolates a dynamic set_primitive_count and
// predicated per-primitive stores. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { uint pid [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 16, 5, metal::topology::triangle>;
struct Payload { uint nprim; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp,
              device const uint* ctrl [[buffer(0)]]) {
    pl.nprim = (ctrl[0] % 5u) + 1u;             // dynamic 1..5
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(16)]]
void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    uint n = pl.nprim;
    if (lane == 0) out.set_primitive_count(n);
    float a = float(lane) * 0.3926991f;
    VOut v;
    v.position = float4(cos(a) * 0.6f, sin(a) * 0.6f, 0.0, 1.0);
    v.color    = float4(float(lane) / 16.0f, 0.0, 1.0, 1.0);
    out.set_vertex(lane, v);
    if (lane < n) {
        out.set_index(lane * 3 + 0, uchar(lane));
        out.set_index(lane * 3 + 1, uchar(lane + 1));
        out.set_index(lane * 3 + 2, uchar(lane + 2));
        POut p; p.pid = lane;
        out.set_primitive(lane, p);
    }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(float(in.p.pid) * 0.05f);
}
