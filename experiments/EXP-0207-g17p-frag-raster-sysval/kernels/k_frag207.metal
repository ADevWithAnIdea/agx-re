// k_frag207.metal -- EXP-0207 FRAGMENT-stage carriers.  OUR OWN MSL.
// Clean-room: OWN-SHADER.  No Apple binary is disassembled or introspected.
//
// Two field targets live in this file, and each carrier exists to differ from
// every carrier already tried in the ONE dimension the field plausibly controls.
//
// (1) frag_color_store.store_mode -- byte+2, 0x54 in 130/130 of the corpus and
//     INERT across EXP-0163's cent4 / ibhalf / layer / mrt3 / tileread /
//     tilerw2 / vflat, all of which are ordinary single- or multi-attachment
//     colour stores.  byte+2 is the same slot the memory family uses for the
//     ADDRESS/STORE MODE (device_store.addr_mode 0x54 ALU-data / 0x56 direct
//     load-result data / 0x64 mesh-extended), so the untried dimension is the
//     store's DESTINATION KIND and DATA PATH, not the attachment count:
//       f_dual  -- DUAL-SOURCE blend: a second colour output to the SAME render
//                  target at index(1).  That is not an rt_index change, so if it
//                  is encoded at all it must be encoded elsewhere in the store.
//       f_blend -- fixed-function blending on (the store feeds the blender).
//       f_samp  -- PER-SAMPLE invocation ([[sample_id]]) at 4 samples.
//       f_mask  -- a [[sample_mask]] output alongside the colour, 4 samples.
//       f_u32   -- an INTEGER (RGBA32Uint) attachment: a different store data path.
//       f_depth -- a fragment that also writes [[depth(any)]].
//       f_r8    -- a packed 8-bit (RGBA8Unorm) attachment.
//
// (2) iter.b9 -- byte+9, the byte adjacent to the documented interpolation
//     LOCATION field `loc` (byte+8).  `loc` is known to move at 4 samples and
//     not at 1 (EXP-0163 vs EXP-0155).  iter.b9 was swept on atoff1, cent4,
//     mrt3, vflat, vhalf and vmany -- every one of them PER-PIXEL shading.  The
//     untried dimension is INVOCATION FREQUENCY:
//       f_ps    -- [[sample_id]] forces PER-SAMPLE execution; each sample's own
//                  interpolated values go to a device buffer with no resolve
//                  average to hide a permutation.
//       f_atsamp-- interpolate_at_sample() with a DYNAMIC index, per-sample.
//     The same MSL is also built at 1 sample as the CONTROL arm, where every
//     sample location collapses to one point.
//
// EVERY fragment here also writes an INTEGRITY SENTINEL to a device buffer at
// [[buffer(1)]] through a path the instruction under test cannot name, so
// "the store did not land" and "the fragment never ran" stay distinguishable
// (FIELD-SWEEP-PROTOCOL section 7, instruments 1 and 2).  The harness poisons
// that buffer with 0xDEADBEEF before every dispatch.

#include <metal_stdlib>
using namespace metal;

constant uint SENT_BASE = 0x5A5A0000u;

// ---------------------------------------------------------------- vertex ----
// One full-screen triangle, built from an indexed constant array so the vertex
// program is the same shape across every fragment carrier in this file.
//
// NON-AFFINE BY CONSTRUCTION (RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 5,
// Phase 3): each corner carries a DIFFERENT w, so perspective-correct
// interpolation is a rational function of screen position while linear
// interpolation is affine.  With w == 1 everywhere the two are the SAME
// function and every competing interpolation model -- centre, centroid, sample,
// perspective, no-perspective -- produces identical numbers, which would make an
// interpolation-location field indistinguishable no matter how it is swept.
// fs_tri returns clip-space xy ALREADY MULTIPLIED by w, so pos.xy/pos.w is the
// intended NDC and the triangle still covers the whole 8x8 target.
constant float FS_W[3] = { 1.0f, 2.5f, 0.625f };
static float2 fs_ndc(uint vid) {
    float2 p[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    return p[vid];
}
static float4 fs_tri4(uint vid) {
    float w = FS_W[vid];
    return float4(fs_ndc(vid) * w, 0.0f, w);
}

struct VPlain { float4 pos [[position]]; float4 vc; };
vertex VPlain v_plain(uint vid [[vertex_id]], constant float4 &vp [[buffer(0)]]) {
    VPlain o;
    o.pos = fs_tri4(vid);
    o.vc  = vp * float(vid + 1u) + float4(0.25, 0.5, 0.75, 1.0);
    return o;
}

// Location-sensitive varyings: one per interpolation location MSL can name, all
// with LARGE gradients so a sub-pixel change in where they are sampled is
// numerically large in the read-back.
struct VLoc {
    float4 pos [[position]];
    float  a [[center_perspective]];
    float  b [[centroid_perspective]];
    float  c [[sample_perspective]];
    float  d [[sample_no_perspective]];
};
vertex VLoc v_loc(uint vid [[vertex_id]]) {
    float f = float(vid);
    VLoc o;
    o.pos = fs_tri4(vid);
    o.a = 3000.0f * f;
    o.b = 1700.0f - 900.0f * f * f;
    o.c = 40.0f + 610.0f * f;
    o.d = 7.0f + 1300.0f * (f * f - f);
    return o;
}

// Pull-model varyings, for interpolate_at_sample with a dynamic index.
// The `interpolant<>` type is legal ONLY in the FRAGMENT stage_in struct -- a
// vertex function may not return it ("invalid return type ... field of illegal
// type __metal_interpolant_t", recorded in raw/prefreeze/census01).  So the
// vertex side declares plain floats and the fragment side re-declares the same
// slots as interpolants, which is the same shape EXP-0163's k_atoff1 uses.
struct VPull {
    float4 pos [[position]];
    float p0;
    float p1;
};
struct FPull {
    float4 pos [[position]];
    interpolant<float, interpolation::perspective> p0;
    interpolant<float, interpolation::no_perspective> p1;
};
vertex VPull v_pull(uint vid [[vertex_id]]) {
    float f = float(vid);
    VPull o;
    o.pos = fs_tri4(vid);
    o.p0 = 2500.0f * f - 30.0f;
    o.p1 = 90.0f + 1450.0f * f * f;
    return o;
}

// -------------------------------------------------- frag_color_store arms ----

// DUAL-SOURCE blend: two colour outputs, both to render target 0, at source
// index 0 and 1.  The pipeline binds Source1Color / OneMinusSource1Color.
struct DualOut {
    float4 s0 [[color(0), index(0)]];
    float4 s1 [[color(0), index(1)]];
};
fragment DualOut f_dual(VPlain in [[stage_in]], constant float4 &u [[buffer(0)]],
                        device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    DualOut o;
    o.s0 = in.vc + u;
    o.s1 = float4(0.25, 0.5, 0.125, 0.75) * (in.vc.x + 1.0);
    return o;
}

// Fixed-function alpha blending on a single attachment.
fragment float4 f_blend(VPlain in [[stage_in]], constant float4 &u [[buffer(0)]],
                        device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    return in.vc * 0.5 + u;
}

// PER-SAMPLE invocation: [[sample_id]] forces the fragment stage to run once
// per sample, so the colour store is a per-sample store.
fragment float4 f_samp(VPlain in [[stage_in]], uint sid [[sample_id]],
                       constant float4 &u [[buffer(0)]],
                       device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    return in.vc + u * float(sid + 1u);
}

// A [[sample_mask]] output alongside the colour.
struct MaskOut { float4 c [[color(0)]]; uint m [[sample_mask]]; };
fragment MaskOut f_mask(VPlain in [[stage_in]], constant float4 &u [[buffer(0)]],
                        device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    MaskOut o;
    o.c = in.vc + u;
    o.m = 0xDu;                    // samples 0,2,3 -- an asymmetric mask
    return o;
}

// INTEGER attachment (RGBA32Uint): a different store data path entirely.
fragment uint4 f_u32(VPlain in [[stage_in]], constant float4 &u [[buffer(0)]],
                     device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    return uint4(uint(in.vc.x * 16.0) + 7u, x + 100u, y + 200u, uint(u.x) + 3u);
}

// A fragment that also writes depth.
struct DepthOut { float4 c [[color(0)]]; float z [[depth(any)]]; };
fragment DepthOut f_depth(VPlain in [[stage_in]], constant float4 &u [[buffer(0)]],
                          device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    DepthOut o;
    o.c = in.vc + u;
    o.z = 0.25 + 0.5 * fract(in.vc.x);
    return o;
}

// Packed 8-bit attachment.
fragment float4 f_r8(VPlain in [[stage_in]], constant float4 &u [[buffer(0)]],
                     device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    return saturate(in.vc * 0.25 + u * 0.125);
}

// ------------------------------------------------------------- iter arms ----

// PER-SAMPLE interpolation, observed per sample with no resolve average.
// out[(y*8+x)*4 + sid] receives that sample's four interpolated values.
fragment float4 f_ps(VLoc in [[stage_in]], uint sid [[sample_id]],
                     device float4 *out [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    out[(y * 8u + x) * 4u + sid] = float4(in.a, in.b, in.c, in.d);
    return float4(in.a, in.b, in.c, in.d);
}

// Pull model with a DYNAMIC sample index: interpolate_at_sample(sid).
fragment float4 f_atsamp(FPull in [[stage_in]], uint sid [[sample_id]],
                         device float4 *out [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    float q0 = in.p0.interpolate_at_sample(sid);
    float q1 = in.p1.interpolate_at_sample(sid ^ 1u);
    float q2 = in.p0.interpolate_at_centroid();
    float q3 = in.p1.interpolate_at_center();
    out[(y * 8u + x) * 4u + sid] = float4(q0, q1, q2, q3);
    return float4(q0, q1, q2, q3);
}
