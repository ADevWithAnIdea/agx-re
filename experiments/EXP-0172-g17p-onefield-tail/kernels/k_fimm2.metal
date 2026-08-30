// k_fimm2.metal -- EXP-0172 falu2i carrier, structurally different arm:
// NEGATIVE immediates (imm_sign = 1), fma-shaped uses, and immediates applied
// directly to a freshly LOADED operand (db.json: falu2i "requires mods = 0xC0
// ... when its operand is LOAD-SOURCED (EXP-0101)").  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  See k_fimm.metal.  This sibling changes the sign bit, the operand
// source class and the consumer shape while keeping the same instruction, so
// that an `imm_flag` verdict is not a property of one immediate.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out       [[buffer(0)]],
                   device const uint *in  [[buffer(1)]],
                   uint tid  [[thread_position_in_grid]],
                   uint lane [[thread_index_in_simdgroup]])
{
    uint  i0 = tid & 31u;
    float x  = as_type<float>(in[32u + i0]);
    float y  = as_type<float>(in[32u + ((i0 + 1u) & 31u)]);

    float a = x - 0.03125f;
    float b = x - 7.0f;
    float c = x * -0.25f;
    float d = x * -30.0f;
    float e = fma(y, 2.0f, 3.0f);
    float f = fma(y, -0.5f, 12.0f);
    float g = (x + 5.0f) * (x - 5.0f);
    float h = as_type<float>(in[32u + ((i0 + 2u) & 31u)]) + 24.0f;

    device uint *o = out + lane * 16u;
    o[0]  = as_type<uint>(a);  o[1]  = as_type<uint>(b);
    o[2]  = as_type<uint>(c);  o[3]  = as_type<uint>(d);
    o[4]  = as_type<uint>(e);  o[5]  = as_type<uint>(f);
    o[6]  = as_type<uint>(g);  o[7]  = as_type<uint>(h);
    o[8]  = as_type<uint>(a * b);
    o[9]  = as_type<uint>(c + d);
    o[10] = as_type<uint>(e - f);
    o[11] = as_type<uint>(g + h);
    o[12] = as_type<uint>(fma(a, 3.0f, b));
    o[13] = as_type<uint>(fma(c, -1.0f, d));
    o[14] = in[i0] ^ as_type<uint>(e);
    o[15] = as_type<uint>(x + y);
}
