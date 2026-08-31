// k_deriv2.metal -- EXP-0204 tex_deriv.dstsrc SECOND carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY A SECOND ONE.  EXP-0172's four dstsrc arms all live in ONE program
// (k_deriv), so the field's cross-run stability has never been measured against
// a different register allocation.  `dstsrc` is a packed destination+source
// operand: the dimension it controls is WHICH REGISTER the derivative reads and
// WHICH REGISTER it writes.  A second program with a different number of live
// values, a different derivative depth (derivatives of ALU results rather than
// of raw varyings) and half-precision derivatives puts the compiler's own
// allocator somewhere else, so the same swept value lands on a different live
// set.  Every derivative is again CONSTANT over the primitive -- the varyings
// are linear in [[position]] -- so each channel has an exact host-computable
// value and a redirect is a numeric change, not noise.
//
// NO buffer and NO device_load: nothing here depends on an asynchronous load
// landing (EXP-0169).
#include <metal_stdlib>
using namespace metal;

struct VO {
    float4 pos [[position]];
    float4 a;
    float2 b;
    half2  h;
};

vertex VO v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VO o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.a = float4(f * 3.0f, f * 5.0f, f * 9.0f, f * 17.0f);
    o.b = float2(f * 33.0f, f * 65.0f);
    o.h = half2(half(f * 2.0f), half(f * 6.0f));
    return o;
}

fragment float4 f_main(VO i [[stage_in]])
{
    // Derivatives of ALU RESULTS, not of raw varyings: the source register the
    // derivative reads is one the compiler chose for a temporary.
    float p = i.a.x * 2.0f + i.a.y;
    float q = i.a.z - i.a.w * 0.5f;
    float dpx = dfdx(p);
    float dpy = dfdy(p);
    float dqx = dfdx(q);
    float dqy = dfdy(q);
    // A derivative of a raw varying, for contrast.
    float dbx = dfdx(i.b.x);
    float dby = dfdy(i.b.y);
    // Half-precision derivatives: a different operand WIDTH.
    half  dhx = dfdx(i.h.x);
    half  dhy = dfdy(i.h.y);

    return float4(dpx * 1000.0f + dpy,
                  dqx * 1000.0f + dqy,
                  dbx * 1000.0f + dby,
                  float(dhx) * 1000.0f + float(dhy));
}
