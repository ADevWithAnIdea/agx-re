// k_twdim.metal -- EXP-0163 texture-WRITE carrier across DIMENSIONALITIES.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  `tex_write.amode` (byte+2) and `tex_write.rsv11` (byte+11) were swept on
// EXP-0155's `t_write` only: three writes, all to the SAME plain 2D
// RGBA32Float texture, all with the same uint2 coordinate type and the same
// contiguous float4 data.  db.json calls byte+2 the addressing mode and
// documents byte+9 (coord_dim) as 0x04 2d / 0x08 3d / 0x0c cube, plus byte+4 as
// the array-layer operand -- so the array, 3D and cube destinations, which are
// the cases an addressing mode would have to distinguish, were never emitted.
//
// Four destinations in one program:
//   texture(1) plain 2D    RGBA32Float  -> texel (1,0)
//   texture(6) 2D ARRAY    RGBA32Float  -> texel (3,2) of SLICE 2
//   texture(7) 3D          RGBA32Float  -> texel (5,4,3)
//   texture(1) again       (a second 2D write, the within-shader control)
// The harness resets every writable texture to (-1,-2,-3,-4) before each render
// and reads all of them back, so "wrote here" / "did not write" / "wrote to a
// different texel, slice or texture" are all distinguishable.
#include <metal_stdlib>
using namespace metal;

struct VO { float4 pos [[position]]; };

vertex VO v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VO o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    return o;
}

fragment float4 f_main(VO i [[stage_in]],
                       texture2d<float, access::write>       w2 [[texture(1)]],
                       texture2d_array<float, access::write> wa [[texture(6)]],
                       texture3d<float, access::write>       w3 [[texture(7)]],
                       device const float *in [[buffer(0)]])
{
    float4 c0 = float4(in[ 8], in[ 9], in[10], in[11]);
    float4 c1 = float4(in[12], in[13], in[14], in[15]);
    float4 c2 = float4(in[16], in[17], in[18], in[19]);
    float4 c3 = float4(in[ 8] + 1.0f, in[ 9] + 1.0f, in[10] + 1.0f, in[11] + 1.0f);
    w2.write(c0, uint2(1u, 0u));
    wa.write(c1, uint2(3u, 2u), 2u);          // NON-ZERO array slice
    w3.write(c2, uint3(5u, 4u, 3u));          // 3D, non-zero depth
    w2.write(c3, uint2(7u, 6u));
    return float4(c0.x, c1.x, c2.x, in[6] * in[7]);
}
