// k_fimm.metal -- EXP-0172 falu2i MINIFLOAT-IMMEDIATE carrier (positive
// immediates, whole minifloat exponent range).  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  `falu2i.imm_flag` is byte+1 bit0, and db.json's own semantics line puts
// it INSIDE the immediate decode: "K = imm_decode(b1, sign). exp(bits12:16,
// bias11) mant(bits9:12) flag(bit8) sign(bit19)".  So the dimension it controls
// is the DECODED IMMEDIATE.  EXP-0138 swept its 2 values on one carrier and
// EXP-0164 withheld it because nothing moved on that single carrier -- but a
// mantissa/scale bit whose contribution is exponent-dependent can be invisible
// at one exponent and load-bearing at another.
//
// This carrier therefore spans the immediate domain deliberately: the minimum
// magnitude the encoding can express (1/32), a power of two (0.5), small
// integers, and the maximum (30.0), under both fadd and fmul, each result
// consumed separately so any one of them changing is visible.  k_fimm2.metal is
// the structurally different sibling: negative immediates, fma, and immediates
// applied straight to a loaded value (the mods==0xC0 load-sourced form of
// EXP-0101).
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out       [[buffer(0)]],
                   device const uint *in  [[buffer(1)]],
                   uint tid  [[thread_position_in_grid]],
                   uint lane [[thread_index_in_simdgroup]])
{
    float x = as_type<float>(in[32u + (tid & 31u)]);

    float a = x + 0.03125f;   // minimum expressible magnitude, exp = 8
    float b = x + 0.5f;       // power of two
    float c = x + 1.0f;
    float d = x + 3.0f;       // mantissa != 0
    float e = x + 30.0f;      // maximum expressible magnitude, exp = 15
    float f = x * 0.03125f;
    float g = x * 3.0f;
    float h = x * 30.0f;

    device uint *o = out + lane * 16u;
    o[0]  = as_type<uint>(a);  o[1]  = as_type<uint>(b);
    o[2]  = as_type<uint>(c);  o[3]  = as_type<uint>(d);
    o[4]  = as_type<uint>(e);  o[5]  = as_type<uint>(f);
    o[6]  = as_type<uint>(g);  o[7]  = as_type<uint>(h);
    o[8]  = as_type<uint>(a + e);
    o[9]  = as_type<uint>(b * g);
    o[10] = as_type<uint>(c - d);
    o[11] = as_type<uint>(f + h);
    o[12] = as_type<uint>(a * b * c * d);
    o[13] = as_type<uint>(e + f + g + h);
    o[14] = in[tid & 31u] ^ as_type<uint>(d);
    o[15] = as_type<uint>(x);
}
