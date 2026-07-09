// mesh_amplify_dyn — object stage computes a DYNAMIC amplification factor from a
// device buffer and fills a payload ARRAY consumed by the mesh stage. Isolates
// mgp.set_threadgroups_per_grid() with a non-constant operand and object_data
// array stores/loads. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { uint pid [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;
struct Payload { float base; uint arr[4]; };

[[object, max_total_threadgroups_per_mesh_grid(64)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp,
              device const uint* ctrl [[buffer(0)]],
              uint3 tgpos [[threadgroup_position_in_grid]]) {
    uint n = (ctrl[0] & 7u) + 1u;               // dynamic 1..8
    pl.base = float(tgpos.x) * 0.1f;
    for (uint i = 0; i < 4; ++i) pl.arr[i] = ctrl[i] + i;
    mgp.set_threadgroups_per_grid(uint3(n, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]],
               uint3 mgpos [[threadgroup_position_in_grid]]) {
    if (lane == 0) out.set_primitive_count(1);
    const float2 P[3] = { float2(-0.4,-0.4), float2(0.4,-0.4), float2(0.0,0.4) };
    float ox = pl.base + float(mgpos.x) * 0.05f;
    VOut v;
    v.position = float4(P[lane] + float2(ox, 0.0), 0.0, 1.0);
    v.color    = float4(float(pl.arr[lane % 4]) * 0.001f, 0.0, 1.0, 1.0);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pid = pl.arr[0]; out.set_primitive(0, p); }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(float(in.p.pid & 0xFFu) / 255.0f);
}
