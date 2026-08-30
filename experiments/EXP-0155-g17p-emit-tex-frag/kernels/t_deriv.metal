// EXP-0142 carrier C -- fragment derivative carrier for tex_deriv (byte0 0x37).
//
// DESIGN (revised pre-freeze; the first version's cross-derivatives were 0,
// which is indistinguishable from the Apple9 silent-zero failure mode, and its
// fragment input was missing [[stage_in]] so it did not compile at all --
// both failures are retained in raw/prefreeze/).
//
// The vertex shader emits TWO varyings that are exact affine functions of the
// SCREEN pixel coordinate, with all four partial derivatives distinct and
// non-zero:
//     u = A*sx + B*sy      -> dfdx(u) = A, dfdy(u) = B
//     v = C*sx + D*sy      -> dfdx(v) = C, dfdy(v) = D
// A,B,C,D and the viewport size arrive in buffer(0), so the host oracle for the
// rendered pixel is exactly (A, B, C, D + S) with no GPU involvement.
//
// LIVENESS (the EXP-0129 trap): each of the four derivative results is routed
// to its OWN channel of an RGBA32Float target that is read back per pixel, and
// A,B,C,D are chosen mutually distinct, non-zero, and different from every
// other constant in the program.  So a derivative that fails to reach the
// rasterised pixel changes a specific, named float, an axis swap shows up as
// one known value appearing in another known channel, and a silently-zeroed
// derivative is distinguishable from all of those.
//
// INTEGRITY SENTINEL (FIELD-SWEEP-PROTOCOL section 7): the alpha channel is
// dfdy(v) + in[7]*in[8], where in[7]*in[8] = S is computed on the plain float
// ALU and never touches the derivative/texture unit.  Alpha therefore reports
// three-way: D+S = both paths ran, D = the sentinel ALU path died, S = the
// derivative died, 0 = the dispatch produced nothing.
//
// Clean-room: our own MSL.
#include <metal_stdlib>
using namespace metal;

struct VO { float4 pos [[position]]; float u; float v; };

vertex VO v_main(uint vid [[vertex_id]], device const float *in [[buffer(0)]]) {
    float2 p[3] = { float2(-1.0f,-1.0f), float2(3.0f,-1.0f), float2(-1.0f,3.0f) };
    float2 ndc = p[vid];
    float W = in[4], H = in[5];
    float sx = (ndc.x + 1.0f) * 0.5f * W;
    float sy = (1.0f - ndc.y) * 0.5f * H;
    VO o;
    o.pos = float4(ndc, 0.0f, 1.0f);
    o.u = in[0] * sx + in[1] * sy;
    o.v = in[2] * sx + in[3] * sy;
    return o;
}

fragment float4 f_main(VO i [[stage_in]], device const float *in [[buffer(0)]]) {
    float a = dfdx(i.u);
    float b = dfdy(i.u);
    float c = dfdx(i.v);
    float d = dfdy(i.v);
    float s = in[7] * in[8];          // sentinel: plain ALU, no derivative unit
    return float4(a, b, c, d + s);
}
