// k_vhalf.metal -- EXP-0163 HALF-PRECISION / VECTOR varying carrier.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  Every EXP-0155 varying carrier passed 32-bit scalar floats one component
// at a time.  If any of vary_store's byte+2 / byte+6 / byte+7 or iter's byte+9
// encodes a COMPONENT WIDTH, a PACKING, or a run-length ("this is the last
// component of a vector"), a 32-bit-scalar-only program can never move it.  This
// carrier passes half scalars, half4 vectors and float2/float4 vectors together,
// so widths 16 and 32 and vector runs of 1, 2 and 4 are all present.
//
// The values are exactly representable in half (integers < 2048 and exact
// binary fractions), so half quantisation is not a source of noise.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    half   h0;
    half4  h1;
    float2 f2;
    float4 f4;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.h0  = half(1.0f + f);
    o.h1  = half4(half(16.0f + f), half(32.0f - f), half(48.0f + 2.0f * f),
                  half(64.0f - 2.0f * f));
    o.f2  = float2(100.0f - 3.0f * f, 200.0f + 5.0f * f);
    o.f4  = float4(1000.0f + 7.0f * f, 1100.0f - 11.0f * f,
                   1200.0f + 13.0f * f, 1300.0f - 17.0f * f);
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(float(in.h0) + 2.0f * float(in.h1.x) + 3.0f * float(in.h1.y),
                  float(in.h1.z) + 5.0f * float(in.h1.w),
                  in.f2.x + 7.0f * in.f2.y,
                  in.f4.x + 11.0f * in.f4.y + 13.0f * in.f4.z + 17.0f * in.f4.w);
}
