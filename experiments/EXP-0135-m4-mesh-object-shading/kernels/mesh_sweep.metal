// EXP-0135 mesh_sweep.metal — OWN-SHADER parametrized object+mesh+fragment pipeline.
//
// A single template kernel whose object-to-mesh payload size, mesh output
// (max vertices / max primitives) declaration, and object-stage grid
// amplification count are all controlled by preprocessor macros supplied at
// compile time via MTLCompileOptions.preprocessorMacros (public Metal API).
// This lets the harness sweep every finite field named in the DRV-P2-03
// dispatch (payload size, vertices/meshlet, primitives/meshlet, threadgroups
// per mesh grid) by recompiling the SAME source with ONE macro changed per
// case, rather than hand-writing one .metal file per data point.
//
// Shape follows EXP-0030's A18 mesh_tri.metal (object stage amplifies +
// fills a payload; mesh stage emits vertices/indices/primitives via
// set_vertex/set_index/set_primitive/set_primitive_count; fragment consumes
// the mesh's per-vertex color) so the M4 re-validation (Group R) is a
// like-for-like comparison, extended with the macro knobs Groups B/C/D need.
//
// Clean-room: OUR OWN MSL only. We compile it via the public runtime API and
// inspect/execute only the resulting compiled output. No Apple binary is
// disassembled or introspected.

#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

#ifndef NV
#define NV 3
#endif
#ifndef NP
#define NP 1
#endif
#ifndef PAYLOAD_BYTES
#define PAYLOAD_BYTES 16
#endif
#ifndef AMP_COUNT
#define AMP_COUNT 1
#endif
#ifndef MESH_TG_THREADS
#define MESH_TG_THREADS 32
#endif

struct VOut {
    float4 position [[position]];
    float4 color;
};
struct POut {
    float3 pnormal [[flat]];
};

using tri_mesh = metal::mesh<VOut, POut, NV, NP, metal::topology::triangle>;

struct Payload {
    uchar data[PAYLOAD_BYTES];
};

// No max_total_threadgroups_per_mesh_grid attribute and no descriptor override:
// per MTLRenderPipeline.h this means "the device's maximum supported value is
// used instead" -- we want the harness's AMP_COUNT sweep to probe that actual
// device ceiling, not an artificially chosen attribute value.
[[object, max_total_threads_per_threadgroup(1)]]
void obj_main(object_data Payload &pl [[payload]],
              mesh_grid_properties mgp,
              uint tid [[thread_position_in_grid]]) {
    for (uint i = 0; i < PAYLOAD_BYTES; i++) pl.data[i] = uchar(i);
    mgp.set_threadgroups_per_grid(uint3(AMP_COUNT, 1, 1));
}

[[mesh, max_total_threads_per_threadgroup(MESH_TG_THREADS)]]
void mesh_main(tri_mesh out,
               const object_data Payload &pl [[payload]],
               uint lane [[thread_index_in_threadgroup]],
               uint tgid [[threadgroup_position_in_grid]]) {
    if (lane == 0)
        out.set_primitive_count(NP);

    // Every amplified threadgroup offsets its geometry by its own tgid so
    // multiple threadgroups' output is independently distinguishable in the
    // rendered image (Group D raster-linkage check). Wrapped into an 8x8 grid
    // of small cells inside NDC space.
    float2 off = float2(float(tgid % 8u) * 0.22f - 0.85f,
                         float((tgid / 8u) % 8u) * 0.22f - 0.85f);

    for (uint i = lane; i < NV; i += MESH_TG_THREADS) {
        VOut v;
        float2 base;
        if (i == 0) base = float2(-0.08, -0.08);
        else if (i == 1) base = float2(0.08, -0.08);
        else if (i == 2) base = float2(0.0, 0.08);
        else base = float2(-0.08, -0.08); // degenerate extras collapse onto vertex 0
        v.position = float4(base + off, 0.0, 1.0);
        v.color = float4(0.0, 1.0, 0.0, 1.0);
        out.set_vertex(i, v);
    }
    for (uint p = lane; p < NP; p += MESH_TG_THREADS) {
        // set_index() takes a uchar (0-255): indices >255 truncate mod 256,
        // which is fine here (see PRE_REGISTRATION.md/RESULTS.md -- this is a
        // load-bearing observation about the index addressing width, not a
        // harness bug) -- these sweeps only need "compiles/creates/renders
        // without fault", not exact per-primitive correctness beyond NV<=256.
        uint i0 = (3u * p + 0u) % NV;
        uint i1 = (3u * p + 1u) % NV;
        uint i2 = (3u * p + 2u) % NV;
        out.set_index(3u * p + 0u, uchar(i0));
        out.set_index(3u * p + 1u, uchar(i1));
        out.set_index(3u * p + 2u, uchar(i2));
        POut po;
        po.pnormal = float3(0.0, 0.0, 1.0);
        out.set_primitive(p, po);
    }
}

fragment float4 frag_main(VOut in [[stage_in]]) {
    return in.color;
}
