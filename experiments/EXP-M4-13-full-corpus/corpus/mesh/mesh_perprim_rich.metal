// mesh_perprim_rich — a WIDE per-primitive record: float4 + float3 + uint + int2,
// all [[flat]]. Isolates a spread of per-primitive store widths/types via
// out.set_primitive(). OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float2 uv; };
struct POut {
    float4 pcolor  [[flat]];
    float3 pnormal [[flat]];
    uint   pid     [[flat]];
    int2   pcoord  [[flat]];
};
using tri_mesh = metal::mesh<VOut, POut, 6, 2, metal::topology::triangle>;
struct Payload { uint seed; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp) {
    pl.seed = 0x9E3779B9u;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(6)]]
void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(2);
    const float2 P[6] = { float2(-0.9,-0.9), float2(-0.1,-0.9), float2(-0.5,0.5),
                          float2( 0.1,-0.9), float2( 0.9,-0.9), float2( 0.5,0.5) };
    VOut v;
    v.position = float4(P[lane], 0.0, 1.0);
    v.uv       = P[lane] * 0.5f + 0.5f;
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane < 2) {
        POut p;
        p.pcolor  = float4(float(lane), 1.0 - float(lane), 0.5, 1.0);
        p.pnormal = normalize(float3(float(lane) + 1.0, 0.0, 1.0));
        p.pid     = pl.seed ^ (lane * 2654435761u);
        p.pcoord  = int2(int(lane) - 1, int(lane) * 7);
        out.set_primitive(lane, p);
    }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.p.pcolor * float4(in.p.pnormal, 1.0)
         + float4(float(in.p.pid & 0xFFu) / 255.0f)
         + float4(float(in.p.pcoord.x), float(in.p.pcoord.y), 0.0, 0.0) * 0.001f
         + float4(in.v.uv, 0.0, 0.0);
}
