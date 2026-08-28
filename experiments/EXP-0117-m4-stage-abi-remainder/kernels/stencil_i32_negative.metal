// stencil_i32_negative.metal -- EXP-0117 isolated negative control:
// `int` (signed 32-bit) is NOT a valid MSL type for [[stencil]] (own-
// compiler diagnostic, captured verbatim: "type 'int' is not valid for
// attribute 'stencil'"). Kept in its OWN translation unit so this
// deliberate rejection does not poison kernels/stencil.metal's working
// uint/ushort forms (Metal compiles a whole source file as one unit; one
// bad declaration fails the entire file).

#include <metal_stdlib>
using namespace metal;

vertex float4 v_full(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid % 3], 0.0, 1.0);
}

struct SOutI32 { float4 c0 [[color(0)]]; int s [[stencil]]; };
fragment SOutI32 f_stencil_i32(constant int &sval [[buffer(0)]]) {
    SOutI32 o; o.c0 = float4(1,1,1,1); o.s = sval; return o;
}
