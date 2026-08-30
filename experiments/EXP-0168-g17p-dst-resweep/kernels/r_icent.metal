// r_icent.metal -- EXP-0168 carrier source for the `itr` family: eight
// CENTROID-qualified scalar varyings, so the fragment stage is forced to emit
// `iter_at` rather than plain `iter`.
//
// WHY THIS FILE EXISTS, measured rather than assumed.  The first attempt at an
// `iter_at` carrier reused r_v8.metal (default, i.e. centre-perspective,
// interpolation).  The on-device census
// (work/render_census_g17p_20260830_rcensus.json) found `vary_store` in its
// vertex program and **NO `iter_at` at all** in its fragment program: plain
// smooth interpolation lowers to the location-implicit form, and `iter_at` --
// "interpolate AT a location" -- is the form the compiler emits when the
// location is explicit.  That is why EXP-0155's carrier for this instruction
// was called `c_cent1`.  A carrier that cannot make the compiler emit the
// instruction is not a weak carrier, it is no carrier, and it would have been
// reported as an inert field.
//
// [[centroid_perspective]] is used on both members of the sample-count pair, so
// the two carriers differ in EXACTLY ONE dimension -- rasterSampleCount -- which
// is the dimension EXP-0163 showed matters for this instruction:
// `iter_at.loc` is inert at 1 sample and moves 128/256 at 4, because at one
// sample the centroid, the sample point and the pixel centre are the same point.
// Choosing `sample_perspective` for the 4x member instead would have confounded
// the interpolation qualifier with the sample count and reproduced EXP-0155's
// own mistake in a new place.
//
// Observables are r_v8's, unchanged and for the same reasons: eight DISTINCT
// POWERS OF TWO, so any subset-sum is unique and a read-back channel says
// exactly which slot(s) reached it (swapped, duplicated, merged or lost), with
// 0.0 distinguishable from every legal value; two RGBA32Float targets so all
// eight are read back individually; and the vertex stage additionally writing
// its own outputs to the `--out-buf` device buffer, which separates
//
//   * "the vertex stage ran and computed X"      (buffer moves)
//   * "X was routed/interpolated to channel k"   (pixel moves, buffer does not)
//   * "the program never ran"                    (buffer still 0xDEADBEEF)
//
// three cases that are otherwise indistinguishable.  Buffer stride is 32 floats
// per vertex, matching every other EXP-0168 vertex carrier; slots 16..31 are
// written by nothing and are a TAIL POISON REGION.
//
// Values come from a runtime uniform so they cannot be constant-folded, and are
// identical at all three vertices, so the interpolated value is exact at every
// covered pixel regardless of which vertex the hardware treats as provoking --
// and, importantly here, regardless of WHERE inside the pixel the interpolation
// is evaluated.  That is deliberate: it means a `grp`/`loc` change cannot be
// mistaken for an ordinary interpolation-position difference in the value
// itself, so any movement is attributable to the field.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOutC {
    float4 pos [[position]];
    float v0 [[centroid_perspective]]; float v1 [[centroid_perspective]];
    float v2 [[centroid_perspective]]; float v3 [[centroid_perspective]];
    float v4 [[centroid_perspective]]; float v5 [[centroid_perspective]];
    float v6 [[centroid_perspective]]; float v7 [[centroid_perspective]];
};

struct FOut2 {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
};

vertex VOutC v_main(uint vid [[vertex_id]],
                    constant float4 &u [[buffer(0)]],
                    device float *o [[buffer(1)]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    float uu[4] = { u.x, u.y, u.z, u.w };
    float v[8];
    for (uint k = 0; k < 8; ++k) {
        v[k] = uu[k & 3u] * ((k < 4u) ? 1.0f : 16.0f);
    }

    VOutC r;
    r.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    r.v0 = v[0]; r.v1 = v[1]; r.v2 = v[2]; r.v3 = v[3];
    r.v4 = v[4]; r.v5 = v[5]; r.v6 = v[6]; r.v7 = v[7];

    uint b = vid * 32u;
    o[b + 0] = r.pos.x; o[b + 1] = r.pos.y; o[b + 2] = r.pos.z; o[b + 3] = r.pos.w;
    for (uint k = 0; k < 8; ++k) {
        o[b + 4u + k] = v[k];
    }
    o[b + 12] = float(vid);
    o[b + 13] = -1.0f;
    o[b + 14] = -2.0f;
    o[b + 15] = -3.0f;
    return r;
}

fragment FOut2 f_main(VOutC in [[stage_in]])
{
    FOut2 o;
    o.c0 = float4(in.v0, in.v1, in.v2, in.v3);
    o.c1 = float4(in.v4, in.v5, in.v6, in.v7);
    return o;
}
