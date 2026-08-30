// k_deriv.metal -- EXP-0172 tex_deriv.dstsrc carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  `tex_deriv` (byte0 0x37, 10 bytes) is the quad-difference derivative op
// -- dfdx / dfdy / fwidth -- and its ONLY remaining non-emitter-grade field is
// `dstsrc`, a 24-bit packed destination+source operand at byte+2..+4, currently
// `untested`.  db.json's provenance for the whole instruction is byte-diff
// (EXP-0016 render_deriv), never a splice of this field, and the ISA database
// has never had a carrier authored specifically for it: every previous
// derivative appearance was incidental to implicit-LOD sampling.
//
// tex_deriv is FRAGMENT-ONLY (it needs the 2x2 quad helper lanes), so this is a
// render carrier.  Six independent derivatives are taken of three DIFFERENT
// varyings, each result stored into a separate output channel, so redirecting
// either half of `dstsrc` -- destination register or source register -- shows up
// as a changed channel rather than being masked by another derivative writing
// the same place.
//
// Both axes are present (0x92 dfdx / 0x90 dfdy per db.json `axis`) and `fwidth`
// contributes the abs+add form, so the arm list spans the axis dimension without
// needing a second program.
//
// The varyings are linear in [[position]], so each derivative is a CONSTANT over
// the primitive and every probe pixel has the same host-computable expected
// value -- a wrong source register or a wrong destination is therefore visible
// as an exact numeric change, not as noise.  NO buffer, NO device_load: nothing
// here depends on an asynchronous load landing (EXP-0169).
#include <metal_stdlib>
using namespace metal;

struct VO {
    float4 pos [[position]];
    float2 uv;
    float3 w;
    float  s;
};

vertex VO v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VO o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    // Deliberately different gradients per varying, so a source-register
    // redirect lands on a numerically DISTINGUISHABLE value.
    o.uv = float2(f * 4.0f, f * f * 8.0f);
    o.w  = float3(f * 16.0f, f * 32.0f, f * 64.0f);
    o.s  = f * 128.0f;
    return o;
}

fragment float4 f_main(VO i [[stage_in]])
{
    float ax = dfdx(i.uv.x);
    float ay = dfdy(i.uv.y);
    float bx = dfdx(i.w.x);
    float by = dfdy(i.w.y);
    float fw = fwidth(i.uv.y);
    float fz = fwidth(i.w.z);
    float sx = dfdx(i.s);
    float sy = dfdy(i.s);

    return float4(ax * 1000.0f + ay,
                  bx * 1000.0f + by,
                  fw * 1000.0f + fz,
                  sx * 1000.0f + sy + i.uv.x);
}
