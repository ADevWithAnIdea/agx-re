#include <metal_stdlib>
using namespace metal;
// FS-02 (helper-invocation position stability) + FS-06 (derivative correctness for
// lanes OUTSIDE primitive coverage) + GLFS-A03 remainder (original-helper status,
// distinct from EXP-0091's demoted-lane-only coverage).
//
// Geometry: a single huge triangle covers exactly NDC x < -0.5 (vertices chosen so the
// edge sits exactly on the boundary between pixel column 0 and column 1 of a W=4,H=4
// target -- i.e. pixel column 0 is covered, column 1 is NOT). Column 0 and column 1
// share a hardware 2x2 quad (quad-columns are (0,1) and (2,3)), so within each such
// quad the x=0 lane is LIVE and the x=1 lane is an ORIGINAL, never-covered HELPER
// invocation (not a demoted one -- EXP-0091 only characterized the demoted case).
//
// The live lane (x=0) retrieves its helper neighbour's (x=1) own values via
// quad_shuffle_xor(v, 1) (XOR of the low bit of the quad lane index swaps x-parity
// within a quad -- same technique EXP-0091 validated for the demoted case).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-0.5, -10), float2(-0.5, 10), float2(-10, 0) };
    VOut o; o.pos = float4(p[vid], 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]], device uint *buf [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    // only the live (x even) lane's writes are meaningful; helper's own writes are
    // suppressed per GLFS-A06, so we relay everything through the live neighbour.
    float neighbour_posx = quad_shuffle_xor(pos.x, 1u);   // FS-02: helper's own pos.x
    float neighbour_posy = quad_shuffle_xor(pos.y, 1u);   // FS-02: helper's own pos.y
    bool neighbour_helper = quad_shuffle_xor(simd_is_helper_thread() ? 1.0f : 0.0f, 1u) != 0.0f;
    float d = dfdx(pos.x);                                 // FS-06: derivative using the
                                                            // helper's contribution
    if ((px & 1u) == 0u) {
        uint idx = py * (dims.x / 2u) + (px / 2u);
        buf[idx*4+0] = as_type<uint>(neighbour_posx);
        buf[idx*4+1] = as_type<uint>(neighbour_posy);
        buf[idx*4+2] = neighbour_helper ? 1u : 0u;
        buf[idx*4+3] = as_type<uint>(d);
    }
    return float4(0,0,0,1);
}
