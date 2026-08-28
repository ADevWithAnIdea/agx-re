// stencil.metal -- EXP-0117 [[stencil]] value-range/overflow probe (OWN-SHADER).
//
// EXP-0109 §3.4 HW-validated that a shader [[stencil]] output (type uint)
// overrides the fixed-function stencilReferenceValue for in-range values
// (5, 9). This file feeds the stencil value from a BUFFER (not baked into
// the shader) so ONE compiled pipeline per MSL type serves the entire
// overflow sweep (0 .. 2^32-1), and adds two alternative MSL source types
// (ushort, int) to determine which are even ACCEPTED for [[stencil]].

#include <metal_stdlib>
using namespace metal;

vertex float4 v_full(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid % 3], 0.0, 1.0);
}

struct SOut32 { float4 c0 [[color(0)]]; uint s [[stencil]]; };
fragment SOut32 f_stencil_u32(constant uint &sval [[buffer(0)]]) {
    SOut32 o; o.c0 = float4(1,1,1,1); o.s = sval; return o;
}

struct SOut16 { float4 c0 [[color(0)]]; ushort s [[stencil]]; };
fragment SOut16 f_stencil_u16(constant ushort &sval [[buffer(0)]]) {
    SOut16 o; o.c0 = float4(1,1,1,1); o.s = sval; return o;
}

// NOTE: a THIRD variant using `int s [[stencil]]` was tried and REJECTED at
// compile time ("type 'int' is not valid for attribute 'stencil'") -- since
// Metal compiles a whole source file as one translation unit, that failing
// declaration would poison this entire file (including the two working
// forms above), so the negative control lives in its own file,
// kernels/stencil_i32_negative.metal, compiled in ISOLATION.
