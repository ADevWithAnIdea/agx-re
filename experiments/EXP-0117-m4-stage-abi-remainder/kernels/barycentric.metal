// barycentric.metal -- EXP-0117 barycentric_coord / primitive_id VALUE
// correctness probes (OWN-SHADER). EXP-0109 confirmed both compile; this
// file HW-validates the actual VALUES against a host-computable oracle.
//
// Barycentric method: an asymmetric triangle with a DELIBERATELY non-
// uniform per-vertex w (1.0 / 2.0 / 4.0, screen position independent of w
// via the same p*w,w trick used throughout this project), so the linear
// (screen-space) and perspective-correct barycentric weights are
// numerically DIFFERENT at a given pixel -- letting the readback determine
// which convention the hardware's `[[barycentric_coord]]` follows. The
// fragment shader reports the raw (bx,by,bz) AND an in-shader manual
// recombination of known per-vertex "tag" values (10/20/30) using b, so the
// harness/analysis can check both b's raw numeric plausibility (sums to 1,
// nonnegative inside the triangle) and whether manual recombination with b
// reproduces a host-computed oracle.

#include <metal_stdlib>
using namespace metal;

struct VOut { float4 position [[position]]; };

vertex VOut v_bary(uint vid [[vertex_id]]) {
    VOut o;
    float2 p[3] = { float2(-0.6,-0.6), float2(0.6,-0.6), float2(0.0,0.6) };
    float  w[3] = { 1.0, 2.0, 4.0 };
    uint i = vid % 3;
    o.position = float4(p[i] * w[i], 0.0, w[i]);
    return o;
}

struct BaryOut { float4 raw [[color(0)]]; float4 manual [[color(1)]]; };
// tags[0..2] = per-vertex known scalar tags (v0,v1,v2), in the SAME vertex
// order the vertex shader emits them (vid%3 == 0,1,2).
fragment BaryOut f_bary(float3 b [[barycentric_coord]], constant float3 &tags [[buffer(0)]]) {
    BaryOut o;
    o.raw = float4(b, 0.0);
    float m = b.x * tags.x + b.y * tags.y + b.z * tags.z;
    o.manual = float4(m, 0.0, 0.0, 0.0);
    return o;
}

// ---- primitive_id correctness across multi-primitive / indexed / instanced
// draws. R32Uint target (exact integer readback, no float rounding). Four
// triangles tile the viewport left-to-right (columns 0..3 of a W4 x H1
// NDC split); a real drawPrimitives/drawIndexedPrimitives call assembles
// them, and each covered pixel reports its primitive_id + instance_id
// directly.
// NOTE: [[instance_id]] is a VERTEX-stage-only builtin in MSL -- it is not a
// valid fragment-function input attribute (own-compiler diagnostic:
// "invalid 'instance_id' attribute for input declaration in a fragment
// function", captured verbatim during harness development). instance_id
// must be relayed as an ordinary [[flat]] varying if a fragment shader
// needs it.
struct VOutPid { float4 position [[position]]; uint iid [[flat]]; };
vertex VOutPid v_pidquad(uint vid [[vertex_id]], uint iid [[instance_id]]) {
    // 4 triangles, each a thin column: column k spans NDC x in
    // [-1 + k*0.5, -1 + (k+1)*0.5], k=0..3. Y range is INSTANCE-dependent
    // (instance 0 -> NDC y in [-1,0], instance 1 -> [0,1], each
    // over-covered on the far side) so a 2-instance draw's two instances
    // land in disjoint screen regions and are BOTH independently readable
    // (rather than the second instance overdrawing the first).
    uint tri = vid / 3;
    uint corner = vid % 3;
    float x0 = -1.0 + float(tri) * 0.5;
    float x1 = x0 + 0.5;
    float ybase = -1.0 + float(iid) * 1.0;
    float yapex = ybase + 3.0; // over-cover this instance's own half only
    float2 p3[3] = { float2(x0, ybase), float2(x1, ybase), float2(x0, yapex) };
    VOutPid o; o.position = float4(p3[corner], 0.0, 1.0); o.iid = iid; return o;
}
fragment uint4 f_pid(VOutPid in [[stage_in]], uint pid [[primitive_id]]) {
    return uint4(pid, in.iid, 0, 1);
}
