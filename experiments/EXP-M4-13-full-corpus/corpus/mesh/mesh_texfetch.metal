// mesh_texfetch — EXTRAPOLATION probe: sample a texture INSIDE the mesh stage to
// displace vertices. Texture sampling in a non-fragment stage requires an explicit
// LOD. If the mesh stage cannot bind/sample textures, this is a first-class
// NEGATIVE result. OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { uint pid [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;
struct Payload { float amp; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp) {
    pl.amp = 0.1f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main(tri_mesh out,
               texture2d<float> tex [[texture(0)]],
               const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    constexpr sampler s(coord::normalized, address::clamp_to_edge, filter::linear);
    const float2 P[3] = { float2(-0.5,-0.5), float2(0.5,-0.5), float2(0.0,0.5) };
    float2 uv = P[lane] * 0.5f + 0.5f;
    float disp = tex.sample(s, uv, level(0.0)).r * pl.amp;
    if (lane == 0) out.set_primitive_count(1);
    VOut v;
    v.position = float4(P[lane] + float2(disp, disp), 0.0, 1.0);
    v.color    = tex.sample(s, uv, level(0.0));
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) { POut p; p.pid = 1u; out.set_primitive(0, p); }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(float(in.p.pid) * 0.01f);
}
