// mesh_payload_large — a LARGE object_data payload (32-float array). The object
// stage fills it in a loop; the mesh stage reduces it. Isolates bulk object_data
// stores (object stage) and object_data loads + accumulation (mesh stage). OWN MSL.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut { float4 position [[position]]; float4 color; };
struct POut { float psum [[flat]]; };
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;
struct Payload { float data[32]; };

[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp,
              device const float* src [[buffer(0)]]) {
    for (uint i = 0; i < 32; ++i) pl.data[i] = src[i] * float(i) + 1.0f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(1);
    float acc = 0.0f;
    for (uint i = lane; i < 32; i += 3) acc += pl.data[i];
    const float2 P[3] = { float2(-0.5,-0.5), float2(0.5,-0.5), float2(0.0,0.5) };
    VOut v;
    v.position = float4(P[lane], 0.0, 1.0);
    v.color    = float4(acc * 0.001f, 0.0, 1.0, 1.0);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) {
        float total = 0.0f;
        for (uint i = 0; i < 32; ++i) total += pl.data[i];
        POut p; p.psum = total; out.set_primitive(0, p);
    }
}

struct FragIn { VOut v; POut p; };
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color + float4(in.p.psum * 0.0001f);
}
