// k_fimm.metal -- EXP-0172 falu2i MINIFLOAT-IMMEDIATE carrier (positive
// immediates, whole minifloat exponent range).  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  `falu2i.imm_flag` is byte+1 bit0, and db.json's own semantics line puts
// it INSIDE the immediate decode: "K = imm_decode(b1, sign). exp(bits12:16,
// bias11) mant(bits9:12) flag(bit8) sign(bit19)".  Bits 8..15 are therefore ONE
// byte holding an 8-bit minifloat, and `imm_flag` is the LOW bit of its 4-bit
// mantissa field (mantissa4 = (mant << 1) | flag).  The dimension the field
// controls is the DECODED IMMEDIATE, and the prediction is exact:
//
//     K   = (-1)^sign * 2^(exp-11) * (1 + mantissa4/16)
//     dK  = 2^(exp-11) / 16                  <- one flag step
//
// EXP-0138 swept its 2 values on one carrier and EXP-0164 withheld it because
// nothing moved there -- but a mantissa LSB whose absolute contribution scales
// with the exponent is invisible at a small exponent and load-bearing at a
// large one, so a single-exponent carrier cannot see it.  This carrier spans
// the minifloat domain deliberately: the minimum expressible magnitude (1/32),
// a power of two (0.5), small integers with a non-zero mantissa, and the
// maximum (30.0), under both fadd and fmul, each result stored separately so
// any one of them changing is visible.
//
// NO DEVICE LOAD.  `device_load` on G17P is ASYNCHRONOUS (EXP-0169: 0..8 of 8
// seed registers landed depending only on filler length), and a diff-based
// movement oracle over a load-seeded operand can FABRICATE movement.  Every
// operand here is seeded from a special register through ALU only, so nothing
// this carrier observes depends on a load completing.  `in` is bound by the
// runner and deliberately never read.  k_fimm2.metal is the structurally
// different sibling that DOES use the load-sourced form (mods==0xC0, EXP-0101)
// and carries that hazard knowingly.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out       [[buffer(0)]],
                   device const uint *in  [[buffer(1)]],
                   uint tid  [[thread_position_in_grid]],
                   uint lane [[thread_index_in_simdgroup]])
{
    (void)in;
    // ALU/SR-seeded operand: deterministic, load-free, and not constant.
    float x = float(lane) * 0.125f + float(tid & 3u) + 1.0f;

    float a = x + 0.03125f;   // minimum expressible magnitude
    float b = x + 0.5f;       // power of two (mantissa4 == 0)
    float c = x + 1.0f;
    float d = x + 3.0f;       // mantissa4 != 0
    float e = x + 30.0f;      // maximum expressible magnitude
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
    o[14] = (tid * 2654435761u) ^ as_type<uint>(d);
    o[15] = as_type<uint>(x);
}
