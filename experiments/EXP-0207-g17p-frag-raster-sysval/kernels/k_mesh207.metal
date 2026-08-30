// k_mesh207.metal -- EXP-0207 MESH-stage carriers for mesh_out_src.sel.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// `mesh_out_src` is the 2-byte mesh-stage compact source op `04 <sel>` that
// feeds the immediately-following 14-byte device store of a mesh vertex or
// primitive output.  It was declined on a measured 0-occurrence census across 24
// carriers -- every one of which was a COMPUTE kernel, for a MESH-STAGE-ONLY op.
// EXP-0187 found the first carrier that emits it, `mesh_wide`, but only censused
// it: the field has never been dispatched at all.
//
// `mesh_wide` below is the same shape as our own
// experiments/EXP-0187-g17p-rtword-census/kernels/k_mesh187.metal:mesh_wide and
// is retained verbatim in shape as the CENSUS CONTROL -- it is the occurrence
// EXP-0187 walk-confirmed.  Its geometry is degenerate, though: its vertex
// positions are float4(f, 2f, 0, 1) for f = lane*0.1, i.e. every vertex lies on
// the line y = 2x, so every triangle has zero area and nothing rasterises.  A
// sweep against a black frame would measure nothing.
//
// `mesh_wide2` therefore keeps the wide per-vertex + per-primitive payload
// structure (12 vertices, 4 primitives, the same VWide/PWide structs) and only
// replaces the positions with four non-degenerate, viewport-covering triangles,
// so the mesh output path is actually observable in the frame.  `mesh_wide3`
// varies it once more: the per-primitive payload is what the fragment reads, so
// a re-selected source shows in the colour rather than in the geometry.

#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VWide { float4 position [[position]]; float4 c0; float4 c1;
               float4 c2; float3 n; float u; };
struct PWide { float3 pnormal [[flat]]; float4 pcolor; uint pid [[flat]]; };
struct Payload { float scale; float pad0; float pad1; float pad2; };

using tri_wide = metal::mesh<VWide, PWide, 12, 4, metal::topology::triangle>;

[[object, max_total_threadgroups_per_mesh_grid(4)]]
void obj_main(object_data Payload &pl [[payload]], mesh_grid_properties mgp,
              uint tid [[thread_position_in_grid]]) {
    pl.scale = 1.0f;
    mgp.set_threadgroups_per_grid(uint3(1, 1, 1));
}

// CONTROL: the exact shape EXP-0187 walk-confirmed (degenerate geometry).
[[mesh, max_total_threads_per_threadgroup(12)]]
void mesh_wide(tri_wide out, const object_data Payload &pl [[payload]],
               uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(4);
    float f = float(lane) * 0.1f * pl.scale;
    VWide v;
    v.position = float4(f, f * 2.0f, 0.0, 1.0);
    v.c0 = float4(f, 0, 0, 1); v.c1 = float4(0, f, 0, 1);
    v.c2 = float4(0, 0, f, 1); v.n = float3(0, 0, 1); v.u = f;
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane < 4) {
        PWide p; p.pnormal = float3(0, 0, 1);
        p.pcolor = float4(float(lane), 0, 0, 1); p.pid = lane;
        out.set_primitive(lane, p);
    }
}

// SWEEPABLE: same payload structure, four non-degenerate covering triangles.
[[mesh, max_total_threads_per_threadgroup(12)]]
void mesh_wide2(tri_wide out, const object_data Payload &pl [[payload]],
                uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(4);
    uint t = lane / 3u, k = lane % 3u;
    float2 corner[3] = { float2(0.0, 0.0), float2(0.95, 0.0), float2(0.0, 0.95) };
    float2 base = float2(-1.0 + 1.0 * float(t & 1u), -1.0 + 1.0 * float(t >> 1));
    float f = float(lane) * 0.1f * pl.scale;
    VWide v;
    v.position = float4(base + corner[k], 0.0, 1.0);
    v.c0 = float4(1.0f + f, 2.0f, 3.0f, 1.0f);
    v.c1 = float4(0, f, 0, 1); v.c2 = float4(0, 0, f, 1);
    v.n = float3(0, 0, 1); v.u = f;
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane < 4) {
        PWide p; p.pnormal = float3(0, 0, 1);
        p.pcolor = float4(10.0f * float(lane + 1u), 20.0f, 30.0f, 1.0f);
        p.pid = lane;
        out.set_primitive(lane, p);
    }
}

// SWEEPABLE: the same geometry with per-vertex payloads that differ strongly
// between the four float4 slots, so a re-selected output source is a large,
// unmistakable colour change rather than a subtle one.
[[mesh, max_total_threads_per_threadgroup(12)]]
void mesh_wide3(tri_wide out, const object_data Payload &pl [[payload]],
                uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(4);
    uint t = lane / 3u, k = lane % 3u;
    float2 corner[3] = { float2(0.0, 0.0), float2(0.95, 0.0), float2(0.0, 0.95) };
    float2 base = float2(-1.0 + 1.0 * float(t & 1u), -1.0 + 1.0 * float(t >> 1));
    float f = float(lane + 1u) * pl.scale;
    VWide v;
    v.position = float4(base + corner[k], 0.0, 1.0);
    v.c0 = float4(100.0f * f, 101.0f, 102.0f, 1.0f);
    v.c1 = float4(200.0f * f, 201.0f, 202.0f, 1.0f);
    v.c2 = float4(300.0f * f, 301.0f, 302.0f, 1.0f);
    v.n  = float3(400.0f, 401.0f, 402.0f);
    v.u  = 500.0f * f;
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane < 4) {
        PWide p; p.pnormal = float3(600.0f, 601.0f, 602.0f);
        p.pcolor = float4(700.0f * float(lane + 1u), 701.0f, 702.0f, 1.0f);
        p.pid = lane + 7u;
        out.set_primitive(lane, p);
    }
}

// MINIMAL-DELTA VARIANTS.  The census (raw/prefreeze/census01) measured that
// mesh_wide2 and mesh_wide3 emit NO `mesh_out_src` at all, while mesh_wide --
// whose geometry is degenerate -- emits exactly one.  That is a first-class
// result about how fragile the op's emission is, and it says the earlier
// rewrites changed too much at once.  These three change ONLY the position
// expression, keeping every payload assignment byte-for-byte as mesh_wide has
// it, so a carrier that both emits the op and covers pixels can be found by
// bisection rather than by guessing.

// P1: the same `float4(<float expr>, <float expr>, 0, 1)` shape, with the two
// expressions chosen so the four triangles have real area and cover the frame.
[[mesh, max_total_threads_per_threadgroup(12)]]
void mesh_wideP1(tri_wide out, const object_data Payload &pl [[payload]],
                 uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(4);
    float f = float(lane) * 0.1f * pl.scale;
    float ax = ((lane % 3u) == 1u) ? 0.9f : -0.9f;
    float ay = ((lane % 3u) == 2u) ? 0.9f : -0.9f;
    VWide v;
    v.position = float4(ax + f * 0.01f, ay + f * 0.01f, 0.0, 1.0);
    v.c0 = float4(f, 0, 0, 1); v.c1 = float4(0, f, 0, 1);
    v.c2 = float4(0, 0, f, 1); v.n = float3(0, 0, 1); v.u = f;
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane < 4) {
        PWide p; p.pnormal = float3(0, 0, 1);
        p.pcolor = float4(float(lane), 0, 0, 1); p.pid = lane;
        out.set_primitive(lane, p);
    }
}

// P2: mesh_wide with ONLY the y expression changed (x untouched), so the
// triangles stop being collinear with the smallest possible edit.
[[mesh, max_total_threads_per_threadgroup(12)]]
void mesh_wideP2(tri_wide out, const object_data Payload &pl [[payload]],
                 uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(4);
    float f = float(lane) * 0.1f * pl.scale;
    VWide v;
    v.position = float4(f * 4.0f - 1.5f, f * f * 30.0f - 1.2f, 0.0, 1.0);
    v.c0 = float4(f, 0, 0, 1); v.c1 = float4(0, f, 0, 1);
    v.c2 = float4(0, 0, f, 1); v.n = float3(0, 0, 1); v.u = f;
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane < 4) {
        PWide p; p.pnormal = float3(0, 0, 1);
        p.pcolor = float4(float(lane), 0, 0, 1); p.pid = lane;
        out.set_primitive(lane, p);
    }
}

// P3: mesh_wide verbatim except that ONE primitive count is used and the
// positions are scaled up so the (still collinear) line becomes a wide fan --
// the smallest edit that can put a covered pixel on screen without touching the
// payload assignments at all.
[[mesh, max_total_threads_per_threadgroup(12)]]
void mesh_wideP3(tri_wide out, const object_data Payload &pl [[payload]],
                 uint lane [[thread_index_in_threadgroup]]) {
    if (lane == 0) out.set_primitive_count(4);
    float f = float(lane) * 0.1f * pl.scale;
    float g = (lane % 3u == 0u) ? -0.9f : ((lane % 3u == 1u) ? 0.9f : -0.9f);
    float h = (lane % 3u == 2u) ? 0.9f : -0.9f;
    VWide v;
    v.position = float4(g, h * 2.0f - f, 0.0, 1.0);
    v.c0 = float4(f, 0, 0, 1); v.c1 = float4(0, f, 0, 1);
    v.c2 = float4(0, 0, f, 1); v.n = float3(0, 0, 1); v.u = f;
    out.set_vertex(lane, v); out.set_index(lane, uchar(lane));
    if (lane < 4) {
        PWide p; p.pnormal = float3(0, 0, 1);
        p.pcolor = float4(float(lane), 0, 0, 1); p.pid = lane;
        out.set_primitive(lane, p);
    }
}

struct FragInW { VWide v; PWide p; };
fragment float4 frag_wide(FragInW in [[stage_in]]) {
    return in.v.c0 + in.p.pcolor * 0.5f
         + float4(in.v.c1.y, in.v.c2.z, in.v.u, float(in.p.pid)) * 0.25f;
}
