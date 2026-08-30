// k_texcube.metal -- EXP-0163 CUBE / ARRAY / 3D coordinate-setup carrier.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  `tex_coord_setup.idx` is a plausible INDEX -- an array slice, a cube
// face, a coefficient or slot number.  On EXP-0155's only carrier there was
// nothing to index: a single 2D sampled texture with one coordinate setup.  Here
// four DIFFERENT texture shapes are sampled in one program (2D, 3D, cube and 2D
// array), each with its own coordinate setup, and the array sample uses a
// NON-ZERO slice and the cube sample a face that is not +X, so an index really
// has distinct things to select between.
//
// Harness texture contents (see harness/gfrun2.m, ours):
//   texture(0) 2D    R32Float texel(x,y)     = x + 100*y
//   texture(2) 3D    R32Float texel(x,y,z)   = x + 10*y + 100*z
//   texture(3) cube  R32Float texel(x,y,face)= x + 10*y + 100*face
//   texture(4) 2Darr R32Float texel(x,y,slice)=x + 10*y + 100*slice
// so every sample result is an exact integer naming its own texel AND slice.
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
                       texture2d<float>       t2 [[texture(0)]],
                       texture3d<float>       t3 [[texture(2)]],
                       texturecube<float>     tc [[texture(3)]],
                       texture2d_array<float> ta [[texture(4)]],
                       const device float    *u [[buffer(0)]])
{
    constexpr sampler s(coord::normalized, filter::nearest,
                        address::clamp_to_edge);
    float a = t2.sample(s, float2(u[0], u[1])).x;
    float b = t3.sample(s, float3(u[2], u[3], u[4])).x;
    float c = tc.sample(s, float3(u[5], u[6], -1.0f)).x;   // a -Z face
    float d = ta.sample(s, float2(u[0], u[1]), 3).x;       // NON-ZERO slice
    return float4(a, b, c, d + in.v0 * 0.0f + in.v1 * 0.0f);
}
