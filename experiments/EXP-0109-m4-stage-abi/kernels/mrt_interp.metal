// mrt_interp.metal — EXP-0109 fragment-input/output structural probe (OWN-SHADER).
// Every function here is authored by us and compiled through the public Metal
// runtime (harness/mrt_extract.m). Covers: interpolation qualifiers (default
// perspective / noperspective / centroid / sample / flat), multiple-render-
// target output counts, dual-source blend outputs, an explicit fragment-
// barycentric-coordinate read, and a deliberately-invalid fragment-stencil-
// output attempt (negative-result probe for GLIO/DRV-ABI-01's "stencil
// output" question — MSL's public grammar does not document such an
// attribute; this file records the compiler's own diagnostic rather than
// assuming absence).

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position [[position]];
    float4 c0;
    float4 c1;
};

// Plain (non-entry-point) helper: MSL forbids calling a [[vertex]]-qualified
// function from another vertex function, so the shared per-vertex data is
// computed here and each v_* entry point wraps it.
static VOut common_vertex_data(uint vid) {
    VOut out;
    // A single triangle covering the target, with a non-trivial w so
    // perspective vs. no-perspective interpolation are distinguishable.
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    float w[3]  = { 1.0, 2.0, 4.0 };
    out.position = float4(p[vid % 3] * w[vid % 3], 0.0, w[vid % 3]);
    float3 base[3] = { float3(1,0,0), float3(0,1,0), float3(0,0,1) };
    out.c0 = float4(base[vid % 3], 1.0);
    out.c1 = float4(1.0 - base[vid % 3], 0.5);
    return out;
}

vertex VOut v_common(uint vid [[vertex_id]]) {
    return common_vertex_data(vid);
}

// ---- interpolation-qualifier family ----------------------------------------
struct VOutPersp   { float4 position [[position]]; float4 c0; };
struct VOutNoPersp { float4 position [[position]]; float4 c0 [[center_no_perspective]]; };
struct VOutCentroidP  { float4 position [[position]]; float4 c0 [[centroid_perspective]]; };
struct VOutCentroidNP { float4 position [[position]]; float4 c0 [[centroid_no_perspective]]; };
struct VOutSampleP  { float4 position [[position]]; float4 c0 [[sample_perspective]]; };
struct VOutSampleNP { float4 position [[position]]; float4 c0 [[sample_no_perspective]]; };
struct VOutFlat { float4 position [[position]]; float4 c0 [[flat]]; };

vertex VOutPersp v_persp(uint vid [[vertex_id]]) {
    VOut b = common_vertex_data(vid); VOutPersp o; o.position = b.position; o.c0 = b.c0; return o;
}
vertex VOutNoPersp v_nopersp(uint vid [[vertex_id]]) {
    VOut b = common_vertex_data(vid); VOutNoPersp o; o.position = b.position; o.c0 = b.c0; return o;
}
vertex VOutCentroidP v_centroid_p(uint vid [[vertex_id]]) {
    VOut b = common_vertex_data(vid); VOutCentroidP o; o.position = b.position; o.c0 = b.c0; return o;
}
vertex VOutCentroidNP v_centroid_np(uint vid [[vertex_id]]) {
    VOut b = common_vertex_data(vid); VOutCentroidNP o; o.position = b.position; o.c0 = b.c0; return o;
}
vertex VOutSampleP v_sample_p(uint vid [[vertex_id]]) {
    VOut b = common_vertex_data(vid); VOutSampleP o; o.position = b.position; o.c0 = b.c0; return o;
}
vertex VOutSampleNP v_sample_np(uint vid [[vertex_id]]) {
    VOut b = common_vertex_data(vid); VOutSampleNP o; o.position = b.position; o.c0 = b.c0; return o;
}
vertex VOutFlat v_flat(uint vid [[vertex_id]]) {
    VOut b = common_vertex_data(vid); VOutFlat o; o.position = b.position; o.c0 = b.c0; return o;
}

fragment float4 f_persp(VOutPersp in [[stage_in]]) { return in.c0; }
fragment float4 f_nopersp(VOutNoPersp in [[stage_in]]) { return in.c0; }
fragment float4 f_centroid_p(VOutCentroidP in [[stage_in]]) { return in.c0; }
fragment float4 f_centroid_np(VOutCentroidNP in [[stage_in]]) { return in.c0; }
fragment float4 f_sample_p(VOutSampleP in [[stage_in]]) { return in.c0; }
fragment float4 f_sample_np(VOutSampleNP in [[stage_in]]) { return in.c0; }
fragment float4 f_flat(VOutFlat in [[stage_in]]) { return in.c0; }

// Pull-model interpolation, for structural comparison against the qualifier
// forms. The vertex-output struct stays a plain float4 (v_persp/VOutPersp,
// already declared with default/perspective interpolation); the FRAGMENT
// side redeclares the matching [[stage_in]] member as interpolant<> to
// expose the .interpolate_at_*() pull API — [[stage_in]] pairs VS-output to
// FS-input by member name, so the two struct types may legally differ here.
struct FInPull { float4 position [[position]]; interpolant<float4, interpolation::perspective> c0; };
fragment float4 f_pullmodel_center(FInPull in [[stage_in]]) {
    return in.c0.interpolate_at_center();
}
fragment float4 f_pullmodel_centroid(FInPull in [[stage_in]]) {
    return in.c0.interpolate_at_centroid();
}
fragment float4 f_pullmodel_sample(FInPull in [[stage_in]], uint sid [[sample_id]]) {
    return in.c0.interpolate_at_sample(sid);
}
fragment float4 f_pullmodel_offset(FInPull in [[stage_in]]) {
    return in.c0.interpolate_at_offset(float2(0.25, -0.25));
}

// ---- barycentric-coordinate read -------------------------------------------
fragment float4 f_barycentric(VOutPersp in [[stage_in]],
                               float3 bary [[barycentric_coord]]) {
    return float4(bary, 1.0) * in.c0;
}

// ---- MRT output count family ------------------------------------------------
struct MRT1 { float4 c0 [[color(0)]]; };
struct MRT2 { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; };
struct MRT4 { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; float4 c2 [[color(2)]]; float4 c3 [[color(3)]]; };

fragment MRT1 f_mrt1(VOut in [[stage_in]]) {
    MRT1 o; o.c0 = in.c0; return o;
}
fragment MRT2 f_mrt2(VOut in [[stage_in]]) {
    MRT2 o; o.c0 = in.c0; o.c1 = in.c1; return o;
}
fragment MRT4 f_mrt4(VOut in [[stage_in]]) {
    MRT4 o; o.c0 = in.c0; o.c1 = in.c1; o.c2 = in.c0 * 0.5; o.c3 = in.c1 * 0.5; return o;
}

// ---- dual-source blend outputs ---------------------------------------------
struct DualSrc {
    float4 c0 [[color(0), index(0)]];
    float4 c1 [[color(0), index(1)]];
};
fragment DualSrc f_dualsource(VOut in [[stage_in]]) {
    DualSrc o; o.c0 = in.c0; o.c1 = in.c1; return o;
}

// ---- depth output -----------------------------------------------------------
struct DepthOut {
    float4 c0 [[color(0)]];
    float d [[depth(any)]];
};
fragment DepthOut f_depth_any(VOut in [[stage_in]], constant float &dval [[buffer(0)]]) {
    DepthOut o; o.c0 = in.c0; o.d = dval; return o;
}
struct DepthOutLess {
    float4 c0 [[color(0)]];
    float d [[depth(less)]];
};
fragment DepthOutLess f_depth_less(VOut in [[stage_in]], constant float &dval [[buffer(0)]]) {
    DepthOutLess o; o.c0 = in.c0; o.d = dval; return o;
}
struct DepthOutGreater {
    float4 c0 [[color(0)]];
    float d [[depth(greater)]];
};
fragment DepthOutGreater f_depth_greater(VOut in [[stage_in]], constant float &dval [[buffer(0)]]) {
    DepthOutGreater o; o.c0 = in.c0; o.d = dval; return o;
}

// ---- fragment stencil output ------------------------------------------------
// [[stencil]] turned out to be a REAL, recognized MSL fragment output
// attribute (this file originally probed it as a suspected negative — see
// RESULTS.md GLFS-B01). It compiles cleanly and produces additional
// generated code vs. an equivalent shader without it (§ structural, this
// experiment); harness/render_probe.m's "stencil" mode checks whether the
// value it carries actually reaches the hardware stencil attachment.
struct StencilOut {
    float4 c0 [[color(0)]];
    uint s [[stencil]];
};
fragment StencilOut f_stencil_out(VOut in [[stage_in]], constant uint &sval [[buffer(0)]]) {
    StencilOut o; o.c0 = in.c0; o.s = sval; return o;
}

// A deliberately-invalid attribute name, kept as a compile-failure CONTROL so
// the harness's negative-result capture path is proven to actually detect a
// real compiler rejection (distinguishing "attribute recognized" from
// "harness cannot detect rejection").
#if defined(EXP0109_TRY_BOGUS_ATTR)
struct BogusOut {
    float4 c0 [[color(0)]];
    uint s [[not_a_real_attribute_xyz123]];
};
fragment BogusOut f_bogus_negative(VOut in [[stage_in]]) {
    BogusOut o; o.c0 = in.c0; o.s = 1u; return o;
}
#endif

// ---- primitive_id ------------------------------------------------------------
fragment float4 f_primid(VOut in [[stage_in]], uint pid [[primitive_id]]) {
    return float4(float(pid), 0.0, 0.0, 1.0);
}

// ==============================================================================
// HW-PROBE kernels (harness/render_probe.m) — real draws + readback, not just
// structural compile/extract.
// ==============================================================================

// ---- VS attribute-fetch value delivery + out-of-range fetch ----------------
// rasterizationEnabled=NO pipeline (vertex-only / "transform feedback" style):
// the vertex function is the whole probe, writing one record per invocation
// directly to a device buffer via an atomic append index (order-independent,
// mirrors experiments/EXP-0092-m4-sysval-abi's agxvdraw.m pattern).
struct FetchRecord {
    float4 attr;
    uint vid;
    uint iid;
    uint bv;
    uint bi;
};
struct VInF4In { float4 a [[attribute(0)]]; };
vertex void v_fetch_probe(VInF4In in [[stage_in]],
                           uint vid [[vertex_id]], uint iid [[instance_id]],
                           uint bv [[base_vertex]], uint bi [[base_instance]],
                           device FetchRecord *out [[buffer(1)]],
                           device atomic_uint *counter [[buffer(2)]]) {
    uint idx = atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    FetchRecord r;
    r.attr = in.a; r.vid = vid; r.iid = iid; r.bv = bv; r.bi = bi;
    out[idx] = r;
}

// ---- front_facing ------------------------------------------------------------
struct VOutFF { float4 position [[position]]; };
vertex VOutFF v_frontfacing(uint vid [[vertex_id]], uint iid [[instance_id]]) {
    VOutFF o;
    // Two disjoint screen-space triangles selected by instance id: instance 0
    // is CCW (the default Metal front-facing winding), instance 1 is CW —
    // both drawn with an identical, non-culling pipeline (winding/cull state
    // set by the harness).
    float2 ccw[3] = { float2(-0.9,-0.9), float2(-0.1,-0.9), float2(-0.5,-0.1) };
    float2 cw[3]  = { float2(0.1,-0.9), float2(0.5,-0.1), float2(0.9,-0.9) };
    float2 p = (iid == 0) ? ccw[vid % 3] : cw[vid % 3];
    o.position = float4(p, 0.0, 1.0);
    return o;
}
fragment float4 f_frontfacing(VOutFF in [[stage_in]], bool ff [[front_facing]]) {
    return float4(ff ? 1.0 : 0.0, 0.0, 0.0, 1.0);
}

