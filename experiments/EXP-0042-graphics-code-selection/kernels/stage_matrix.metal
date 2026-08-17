#include <metal_stdlib>
using namespace metal;

// Change-one-stage matrix used to separate VS and FS resource fields. All four
// combinations share exactly the same interface and host resources.
struct MatrixOut {
    float4 position [[position]];
    float2 uv;
};

vertex MatrixOut vs_small(uint vertex_id [[vertex_id]],
                          const device float2 *positions [[buffer(0)]],
                          const device float4 *params [[buffer(1)]])
{
    MatrixOut out;
    out.position = float4(positions[vertex_id], 0.0f, 1.0f);
    out.uv = params[1].xy;
    return out;
}

vertex MatrixOut vs_large(uint vertex_id [[vertex_id]],
                          const device float2 *positions [[buffer(0)]],
                          const device float4 *params [[buffer(1)]])
{
    float2 q = positions[vertex_id];
    for (uint i = 0; i < 11; ++i)
        q = fma(q, params[0].xy, params[1].xy);
    MatrixOut out;
    out.position = float4(q, 0.0f, 1.0f);
    out.uv = q * params[1].zw;
    return out;
}

fragment float4 fs_small(MatrixOut in [[stage_in]],
                         const device float4 *params [[buffer(0)]])
{
    return params[2] + in.uv.xyxy * params[1];
}

fragment float4 fs_large(MatrixOut in [[stage_in]],
                         const device float4 *params [[buffer(0)]])
{
    float4 c = params[0] + in.uv.xyxy * params[1];
    for (uint i = 0; i < 15; ++i)
        c = fma(c, params[1], params[3]);
    return c;
}

// Equal-shape pair: intended to compile to equal extents while producing
// different output. This falsifies "fragment block size alone selects FS".
fragment float4 fs_equal_a(MatrixOut in [[stage_in]],
                           const device float4 *params [[buffer(0)]])
{
    return params[2] + in.uv.xyxy * params[1];
}

fragment float4 fs_equal_b(MatrixOut in [[stage_in]],
                           const device float4 *params [[buffer(0)]])
{
    return params[3] + in.uv.xyxy * params[1];
}
