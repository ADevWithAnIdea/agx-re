// c_bary.metal -- EXP-0143 carrier for the EXP-0137 barycentric anomaly, as an
// EMISSION question.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// EXP-0137 (HW-VALIDATED) established:
//   * a fragment shader that reads [[barycentric_coord]] but NOT [[position]]
//     compiles to 2 `iter` and ZERO `fspecial` -- raw perspective NUMERATORS
//     with the third component derived as 1-b0-b1, i.e. NOT normalized
//     ("Model B");
//   * reading [[position]] pulls in the W-denominator `iter` + `fspecial` (rcp)
//     + normalizing multiply, giving the correct perspective-correct result
//     ("Model C");
//   * `[[barycentric_coord, center_perspective]]` is a COMPLETE NO-OP -- byte
//     for byte identical to the unqualified form.  There is no MSL-level
//     escape hatch.
//
// The open EMISSION question this carrier asks: can a driver's own backend
// select the normalized form from the `iter` encoding itself -- i.e. is there
// an interpolation-MODE value that turns a Model-B numerator iter into a
// normalized one -- or is normalization irreducibly a multi-instruction
// lowering the backend must emit itself?  A dense sweep of iter.mode / .loc /
// .coeff_sel on this carrier answers it directly on hardware.
//
// The triangle carries strongly DIFFERING per-vertex w (1, 2, 4), so Model B
// and Model C give numerically very different answers at every covered pixel.

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    float w = (vid == 0) ? 1.0f : ((vid == 1) ? 2.0f : 4.0f);
    VOut o;
    // Pre-multiply by w so the post-divide NDC position is the same triangle as
    // every other carrier, while the interpolator sees three different w values.
    o.pos = float4(((f - 1.0f) * 0.75f) * w, ((f * f - f) * 0.5f - 0.375f) * w, 0.0f, w);
    return o;
}

fragment float4 f_main(float3 bc [[barycentric_coord]])
{
    return float4(bc, 1.0f);
}
