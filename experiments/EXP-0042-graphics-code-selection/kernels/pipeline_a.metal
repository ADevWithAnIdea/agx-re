#include <metal_stdlib>
using namespace metal;

// Authored pipeline A: deliberately small, with a host-provided colour.
struct AOut {
    float4 position [[position]];
};

vertex AOut vs_main(uint vertex_id [[vertex_id]],
                    const device float2 *positions [[buffer(0)]])
{
    AOut out;
    out.position = float4(positions[vertex_id], 0.0f, 1.0f);
    return out;
}

fragment float4 fs_main(const device float4 *colour [[buffer(0)]])
{
    return colour[0];
}
