// EXP-0030 mesh_tri.metal — OWN-SHADER minimal object+mesh+fragment pipeline.
// A mesh shader that emits ONE triangle (3 vertices, 1 primitive). This is the
// baseline provocation for hardware mesh shading on Apple9 / G17P.
//
// Clean-room: OUR OWN MSL. We compile it and inspect only OUR OWN compiled bytes.
#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut {
    float4 position [[position]];
    float4 color;
};
struct POut {
    float3 pnormal [[flat]];
};

// mesh<Vertex, Primitive, MaxVerts, MaxPrims, topology>
using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;

struct Payload { float scale; float pad0; float pad1; float pad2; };

// -------- object stage: amplify into a mesh grid, fill the payload ----------
[[object, max_total_threadgroups_per_mesh_grid(1)]]
void obj_main(object_data Payload &pl [[payload]],
              mesh_grid_properties mgp,
              uint tid [[thread_position_in_grid]]) {
    pl.scale = 1.0f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));   // launch one mesh threadgroup
}

// -------- mesh stage: emit vertices + one triangle primitive -----------------
[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main(tri_mesh out,
               const object_data Payload &pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0)
        out.set_primitive_count(1);

    // A triangle in NDC that covers the middle of the target.
    float2 P[3] = { float2(-0.5, -0.5), float2(0.5, -0.5), float2(0.0, 0.5) };
    VOut v;
    v.position = float4(P[lane] * pl.scale, 0.0, 1.0);
    v.color    = float4(0.0, 1.0, 0.0, 1.0);         // solid green
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));

    if (lane == 0) {
        POut p;
        p.pnormal = float3(0.0, 0.0, 1.0);
        out.set_primitive(0, p);
    }
}

// -------- fragment stage: consume the mesh's per-vertex/per-primitive data ---
struct FragIn {
    VOut v;
    POut p;
};
fragment float4 frag_main(FragIn in [[stage_in]]) {
    return in.v.color;
}
