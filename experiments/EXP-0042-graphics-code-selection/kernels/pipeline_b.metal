#include <metal_stdlib>
using namespace metal;

// Authored pipeline B: independently written and intentionally larger than A.
// Host values make the vertex recurrence an identity and the fragment recurrence
// settle on colour[2], but those values are not compiler constants.
struct BOut {
    float4 position [[position]];
    float2 uv;
};

vertex BOut vs_main(uint vertex_id [[vertex_id]],
                    const device float2 *positions [[buffer(0)]],
                    const device float4 *params [[buffer(1)]])
{
    float2 q = positions[vertex_id];
    for (uint i = 0; i < 9; ++i)
        q = fma(q, params[0].xy, params[1].xy);

    BOut out;
    out.position = float4(q, 0.0f, 1.0f);
    out.uv = q * params[3].xy + params[3].zw;
    return out;
}

fragment float4 fs_main(BOut in [[stage_in]],
                        const device float4 *colour [[buffer(0)]])
{
    float4 c = colour[0] + in.uv.xyxy * colour[1];
    for (uint i = 0; i < 13; ++i)
        c = fma(c, colour[1], colour[2]);
    return c;
}
