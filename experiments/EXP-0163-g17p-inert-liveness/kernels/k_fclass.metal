// k_fclass.metal -- EXP-0163 FLOAT-CLASSIFY carrier for the polymorphic 10-byte
// byte+2==0x2f op db.json calls `tex_coord_setup`.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  db.json's own note (EXP-M4-13 R7 CORRECTION) says this op "is
// POLYMORPHIC and NOT texture-specific": across the corpus it appears as
//   (a) vertex attribute-fetch / varying destination-address setup, byte+4==0x42,
//       byte+7 (`idx`) = dst-slot index = dst<<2; and
//   (b) a float-classify / modifier ALU (isnan / isnormal / frexp / modf),
//       byte+3 = srcA, byte+4 in {0x00, 0x10, 0x12, 0x22}.
// EXP-0155 swept its `b5 b6 idx b8 b9` on ONE occurrence -- the fragment
// gather/bias/gradient carrier -- i.e. one `form` value out of the five db.json
// enumerates.  `idx` is documented to carry a real value ONLY in form (a).
//
// This carrier provokes form (b) directly: isnan, isinf, isnormal, isfinite,
// frexp, modf and ldexp on values whose classification is known to the host, so
// each classify result is an exact host-computed expectation and every one of
// them reaches a distinct output channel.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0;
    float  v1;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0  = 1.0f + f;
    o.v1  = 10.0f + f * f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]],
                       const device float *u [[buffer(0)]])
{
    float a = u[0] / u[1];          // host feeds 0/0 -> NaN
    float b = u[2] / u[3];          // host feeds 1/0 -> Inf
    float c = in.v0 * u[4];
    int   e = 0;
    float m = frexp(c, e);
    float ip = 0.0f;
    float fp = modf(in.v1 * u[5], ip);
    float cls = (isnan(a)    ? 1.0f : 0.0f)
              + (isinf(b)    ? 2.0f : 0.0f)
              + (isnormal(c) ? 4.0f : 0.0f)
              + (isfinite(c) ? 8.0f : 0.0f);
    return float4(cls,
                  m * 64.0f + float(e),
                  ip * 4.0f + fp,
                  ldexp(in.v0, 5) + fabs(a * 0.0f));
}
