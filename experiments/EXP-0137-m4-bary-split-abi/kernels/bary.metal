// bary.metal -- EXP-0129 barycentric-anomaly DISCRIMINATING probe (OWN-SHADER).
//
// EXP-0117 found: a fragment function with 2 outputs {raw=barycentric_coord,
// manual=recombination} gives one raw `b`; adding a THIRD output that simply
// echoes [[position]] back out gives a DIFFERENT `b` (matching this project's
// own perspective-corrected host oracle almost exactly), a disclosed,
// 4x-reproduced, UNRESOLVED anomaly. This file isolates the two conflated
// variables (output COUNT vs POSITION content) with a small factorial matrix,
// all sharing the SAME triangle/w ("CONFIG1", byte-for-byte the geometry
// EXP-0117 used) so every variant's raw `b` is directly comparable.
//
// CONFIG1 geometry (identical to EXP-0117's kernels/barycentric.metal):
//   p = {(-0.6,-0.6), (0.6,-0.6), (0.0,0.6)}, w = {1.0, 2.0, 4.0}.
// tags = (10,20,30) match vertex 0,1,2 in EMISSION order (vid%3).

#include <metal_stdlib>
using namespace metal;

// ------------------------------------------------------------- CONFIG1 VS --
struct VOut { float4 position [[position]]; };

vertex VOut v_bary(uint vid [[vertex_id]]) {
    VOut o;
    float2 p[3] = { float2(-0.6,-0.6), float2(0.6,-0.6), float2(0.0,0.6) };
    float  w[3] = { 1.0, 2.0, 4.0 };
    uint i = vid % 3;
    o.position = float4(p[i] * w[i], 0.0, w[i]);
    return o;
}

// CONFIG1 VS variant that ALSO emits a genuinely NEW interpolated (non-
// position, non-barycentric) per-vertex varying, for the f_count3_vary case
// (isolates "any extra interpolant" from "specifically position").
struct VOutExtra { float4 position [[position]]; float4 vtag [[user(locn0)]]; };

vertex VOutExtra v_bary_extra(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-0.6,-0.6), float2(0.6,-0.6), float2(0.0,0.6) };
    float  w[3] = { 1.0, 2.0, 4.0 };
    float4 vtag[3] = { float4(1,2,3,4), float4(11,12,13,14), float4(21,22,23,24) };
    uint i = vid % 3;
    VOutExtra o;
    o.position = float4(p[i] * w[i], 0.0, w[i]);
    o.vtag = vtag[i];
    return o;
}

// ----------------------------------------------------------- FS variants --

// f_base: the EXP-0117 baseline shape verbatim (2 outputs, no position touched).
struct BaseOut { float4 raw [[color(0)]]; float4 manual [[color(1)]]; };
fragment BaseOut f_base(float3 b [[barycentric_coord]], constant float3 &tags [[buffer(0)]]) {
    BaseOut o;
    o.raw = float4(b, 0.0);
    o.manual = float4(b.x*tags.x + b.y*tags.y + b.z*tags.z, 0.0, 0.0, 0.0);
    return o;
}

// f_pos3: EXP-0117's disclosed-anomaly shape verbatim (3 outputs, position
// consumed AND emitted as a 3rd color output).
struct Pos3Out { float4 raw [[color(0)]]; float4 manual [[color(1)]]; float4 pos [[color(2)]]; };
fragment Pos3Out f_pos3(float3 b [[barycentric_coord]], constant float3 &tags [[buffer(0)]], float4 pos [[position]]) {
    Pos3Out o;
    o.raw = float4(b, 0.0);
    o.manual = float4(b.x*tags.x + b.y*tags.y + b.z*tags.z, 0.0, 0.0, 0.0);
    o.pos = pos;
    return o;
}

// f_count3_const: 3 outputs, but the 3rd is a COMPILE-TIME CONSTANT -- no
// new interpolation, no position. Isolates OUTPUT-COUNT alone.
struct Count3Out { float4 raw [[color(0)]]; float4 manual [[color(1)]]; float4 extra [[color(2)]]; };
fragment Count3Out f_count3_const(float3 b [[barycentric_coord]], constant float3 &tags [[buffer(0)]]) {
    Count3Out o;
    o.raw = float4(b, 0.0);
    o.manual = float4(b.x*tags.x + b.y*tags.y + b.z*tags.z, 0.0, 0.0, 0.0);
    o.extra = float4(7.0, 8.0, 9.0, 1.0);
    return o;
}

// f_count3_vary: 3 outputs, 3rd echoes a genuinely NEW interpolated varying
// (v_bary_extra's vtag) -- NOT position. Isolates "any extra interpolant"
// from "specifically position". NOTE (own-compiler finding, disclosed in
// PROGRESS.md): a bare `float4 vtag [[user(locn0)]]` fragment PARAMETER
// (not wrapped in a [[stage_in]] struct) silently fails to connect to the
// vertex shader's output -- readback is the untouched clear value, not an
// error. MSL requires a [[stage_in]]-tagged struct for a plain user varying
// (barycentric_coord/position/front_facing are exempt, being true builtins).
struct FSInExtra { float4 vtag [[user(locn0)]]; };
fragment Count3Out f_count3_vary(float3 b [[barycentric_coord]], constant float3 &tags [[buffer(0)]],
                                  FSInExtra in [[stage_in]]) {
    Count3Out o;
    o.raw = float4(b, 0.0);
    o.manual = float4(b.x*tags.x + b.y*tags.y + b.z*tags.z, 0.0, 0.0, 0.0);
    o.extra = in.vtag;
    return o;
}

// f_pos2: 2 outputs {raw,pos} -- position consumed+emitted but count STAYS
// at 2 (no "manual"). Isolates position-content WITHOUT a count increase.
struct Pos2Out { float4 raw [[color(0)]]; float4 pos [[color(1)]]; };
fragment Pos2Out f_pos2(float3 b [[barycentric_coord]], float4 pos [[position]]) {
    Pos2Out o;
    o.raw = float4(b, 0.0);
    o.pos = pos;
    return o;
}

// f_posread_noout: 2 outputs {raw,manual} (SAME struct shape as f_base), but
// [[position]] is read and stored to a device buffer as a real, non-
// foldable side effect -- NOT emitted as a color output at all. Isolates
// "position materialized somewhere" from "position is an output".
fragment BaseOut f_posread_noout(float3 b [[barycentric_coord]], constant float3 &tags [[buffer(0)]],
                                  float4 pos [[position]], device float4 *dbg [[buffer(1)]]) {
    dbg[0] = pos;
    BaseOut o;
    o.raw = float4(b, 0.0);
    o.manual = float4(b.x*tags.x + b.y*tags.y + b.z*tags.z, 0.0, 0.0, 0.0);
    return o;
}

// ------------------------------------------------------------- CONFIG2 VS --
// Independent geometry/w/sample-weights (same fixed sample texel (32.5,32.5)
// on a 64x64 target, different triangle/w so the predicted linear/perspective
// -numerator/perspective-normalized values are all numerically distinct from
// CONFIG1 and from each other -- an independent cross-check, not a re-fit).
//   p = {(-0.5,-0.3), (0.55,-0.2), (0.0925,0.6975)}, w = {1.0, 3.0, 2.5}.
//   host lin (screen-space) at (32.5,32.5) = (0.4, 0.35, 0.25) exactly.
struct VOut2 { float4 position [[position]]; };
vertex VOut2 v_bary2(uint vid [[vertex_id]]) {
    VOut2 o;
    float2 p[3] = { float2(-0.5,-0.3), float2(0.55,-0.2), float2(0.0925,0.6975) };
    float  w[3] = { 1.0, 3.0, 2.5 };
    uint i = vid % 3;
    o.position = float4(p[i] * w[i], 0.0, w[i]);
    return o;
}

// f_base2 / f_pos3_2: same two decisive shapes as f_base/f_pos3, CONFIG2 tags.
fragment BaseOut f_base2(float3 b [[barycentric_coord]], constant float3 &tags [[buffer(0)]]) {
    BaseOut o;
    o.raw = float4(b, 0.0);
    o.manual = float4(b.x*tags.x + b.y*tags.y + b.z*tags.z, 0.0, 0.0, 0.0);
    return o;
}
fragment Pos3Out f_pos3_2(float3 b [[barycentric_coord]], constant float3 &tags [[buffer(0)]], float4 pos [[position]]) {
    Pos3Out o;
    o.raw = float4(b, 0.0);
    o.manual = float4(b.x*tags.x + b.y*tags.y + b.z*tags.z, 0.0, 0.0, 0.0);
    o.pos = pos;
    return o;
}
