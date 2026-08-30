// k_twrt.metal -- EXP-0163 ADDENDUM carrier: texture writes with RUNTIME
// coordinates, a loop, and read-then-write data.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY THIS EXISTS.  After run01, `tex_write.amode` and `tex_write.rsv11` were
// inert on all six arms — but those six arms came from only TWO source programs
// (`twdim`, `twtype`), one short of the pre-registered "≥3 structurally
// different carriers" bar for an INERT-ROBUST verdict.  Rather than relax the
// bar, this adds a third program that differs in the one dimension the other
// two share: both of them write CONSTANT, compile-time coordinates, straight
// out of a uniform buffer, with no control flow.
//
// Here every write differs in exactly that respect:
//   * write 0 uses a coordinate computed at RUNTIME from the fragment position;
//   * write 1 writes data that was READ BACK from a texture, not loaded from a
//     buffer, so the store's data operand has a texture-unit provenance;
//   * write 2 happens inside a LOOP, so the same store executes repeatedly with
//     a varying coordinate and a varying value;
//   * write 3 targets the 3D texture with a runtime depth.
//
// Coordinates are clamped into range so the writes stay deterministic and land
// at addresses the host knows, and every fragment computes the SAME clamped
// coordinate, so the result is order-independent (the EXP-0155 t_write lesson).
#include <metal_stdlib>
using namespace metal;

struct VO { float4 pos [[position]]; float v0; };

vertex VO v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VO o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0 = 1.0f + f;
    return o;
}

fragment float4 f_main(VO i [[stage_in]],
                       texture2d<float>                      t  [[texture(0)]],
                       texture2d<float, access::write>       w2 [[texture(1)]],
                       texture2d_array<float, access::write> wa [[texture(6)]],
                       texture3d<float, access::write>       w3 [[texture(7)]],
                       device const float *in [[buffer(0)]])
{
    constexpr sampler s(coord::normalized, filter::nearest, address::clamp_to_edge);

    // Runtime coordinate: derived from a uniform, not a literal, and clamped so
    // every fragment agrees on it.
    uint2 rc = uint2(min(uint(in[0] * 2.0f), 7u), min(uint(in[1] + 3.0f), 7u));
    w2.write(float4(in[8], in[9], in[10], in[11]), rc);

    // Data with a TEXTURE-UNIT provenance rather than a buffer load.
    float4 red = float4(t.sample(s, float2(in[0], in[1])).x,
                        t.sample(s, float2(in[2], in[3])).x,
                        t.sample(s, float2(in[4], in[5])).x,
                        in[6] * in[7]);
    wa.write(red, uint2(3u, 2u), 1u);

    // The same store executed repeatedly inside a loop.
    for (uint k = 0u; k < 3u; ++k)
        w2.write(float4(in[12] + float(k), in[13], in[14], in[15]),
                 uint2(4u + k, 6u));

    // 3D destination with a runtime depth.
    w3.write(float4(in[16], in[17], in[18], in[19]),
             uint3(5u, 4u, min(uint(in[0] + 1.0f), 3u)));

    return float4(red.x, red.y, red.z, in[6] * in[7]);
}
